"""
eval/judge.py

Automated LLM Evaluation Judge & Calibration Engine (Day 44):
- Evaluates generated responses for faithfulness, groundedness, code correctness, and rubric adherence.
- Evaluates against hand-graded calibration dataset (eval/judge_calibration_data.json).
- Computes exact Inter-Rater Reliability statistics:
  * Percent Agreement (targeting >= 80% threshold)
  * Cohen's Kappa (kappa) with Landis & Koch interpretation tier
  * Confusion Matrix (TP, TN, FP, FN)
  * Precision, Recall, Specificity, and F1 Score
  * 95% Wilson Score confidence intervals
- Generates eval/judge_calibration_report.json.
"""

import os
import sys
import json
import math
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas import NavigatorResponse
from app.reviewer import ReviewerAgent, audit_response

DEFAULT_CALIBRATION_DATA = PROJECT_ROOT / "eval" / "judge_calibration_data.json"
DEFAULT_CALIBRATION_REPORT = PROJECT_ROOT / "eval" / "judge_calibration_report.json"


def calculate_wilson_interval(successes: int, total: int, confidence: float = 0.95) -> Tuple[float, float]:
    """Calculate the Wilson score confidence interval for a proportion."""
    if total == 0:
        return (0.0, 0.0)
    z = 1.96 if math.isclose(confidence, 0.95, rel_tol=0.01) else 1.96
    p = successes / total
    z2 = z * z
    denom = 1 + z2 / total
    centre = (p + z2 / (2 * total)) / denom
    half_width = (z / denom) * math.sqrt((p * (1 - p) / total) + (z2 / (4 * total * total)))
    low = max(0.0, centre - half_width)
    high = min(1.0, centre + half_width)
    return (round(low * 100, 2), round(high * 100, 2))


def calculate_cohens_kappa(
    human_labels: List[str],
    judge_labels: List[str],
    positive_label: str = "PASS",
    negative_label: str = "FAIL",
) -> Dict[str, Any]:
    """
    Compute exact Cohen's Kappa between human and judge categorical classifications.
    
    Formula:
      P_o = (TP + TN) / N
      P_e = P(human_pos) * P(judge_pos) + P(human_neg) * P(judge_neg)
      kappa = (P_o - P_e) / (1 - P_e)
    """
    n = len(human_labels)
    if n == 0 or len(judge_labels) != n:
        raise ValueError("Human and judge label lists must be non-empty and of equal length.")

    tp = sum(1 for h, j in zip(human_labels, judge_labels) if h == positive_label and j == positive_label)
    tn = sum(1 for h, j in zip(human_labels, judge_labels) if h == negative_label and j == negative_label)
    fp = sum(1 for h, j in zip(human_labels, judge_labels) if h == negative_label and j == positive_label)
    fn = sum(1 for h, j in zip(human_labels, judge_labels) if h == positive_label and j == negative_label)

    p_observed = (tp + tn) / n

    p_human_pos = (tp + fn) / n
    p_human_neg = (tn + fp) / n
    p_judge_pos = (tp + fp) / n
    p_judge_neg = (tn + fn) / n

    p_expected = (p_human_pos * p_judge_pos) + (p_human_neg * p_judge_neg)

    if math.isclose(p_expected, 1.0):
        kappa = 1.0 if math.isclose(p_observed, 1.0) else 0.0
    else:
        kappa = (p_observed - p_expected) / (1.0 - p_expected)

    # Standard Landis & Koch (1977) interpretation tier
    if kappa < 0:
        interpretation = "Poor (Less than chance agreement)"
    elif kappa <= 0.20:
        interpretation = "Slight agreement"
    elif kappa <= 0.40:
        interpretation = "Fair agreement"
    elif kappa <= 0.60:
        interpretation = "Moderate agreement"
    elif kappa <= 0.80:
        interpretation = "Substantial agreement"
    else:
        interpretation = "Almost perfect agreement"

    precision = round(tp / (tp + fp), 4) if (tp + fp) > 0 else 0.0
    recall = round(tp / (tp + fn), 4) if (tp + fn) > 0 else 0.0
    specificity = round(tn / (tn + fp), 4) if (tn + fp) > 0 else 0.0
    f1 = round(2 * precision * recall / (precision + recall), 4) if (precision + recall) > 0 else 0.0

    return {
        "n": n,
        "observed_agreement": round(p_observed * 100, 2),
        "chance_expected_agreement": round(p_expected * 100, 2),
        "cohens_kappa": round(kappa, 4),
        "interpretation": interpretation,
        "confusion_matrix": {
            "true_positives": tp,
            "true_negatives": tn,
            "false_positives": fp,
            "false_negatives": fn,
        },
        "metrics": {
            "precision": precision,
            "recall": recall,
            "specificity": specificity,
            "f1_score": f1,
        },
    }


class LLMJudge:
    """Automated evaluation judge for RAG answers."""

    def __init__(self, reviewer: Optional[ReviewerAgent] = None):
        self.reviewer = reviewer or ReviewerAgent(
            min_faithfulness=0.70,
            min_groundedness=0.70,
            min_code_correctness=0.70,
            pass_threshold=0.80,
        )

    def evaluate_pair(self, pair: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate a single question-response pair.
        Returns judge grade dictionary with scores, verdicts, and reasoning.
        """
        query = pair["question"]
        response = pair["generated_response"]
        retrieved_chunks = pair.get("retrieved_chunks", [])
        judge_criteria = pair.get("judge_criteria", [])

        review_res = self.reviewer.audit(
            query=query,
            response=response,
            retrieved_chunks=retrieved_chunks,
            judge_criteria=judge_criteria,
        )

        # Map scores to binary flags for dimension-level agreement checking
        faithfulness_binary = 1 if review_res.faithfulness_score >= 0.70 else 0
        groundedness_binary = 1 if review_res.groundedness_score >= 0.70 else 0
        code_correctness_binary = 1 if review_res.code_correctness_score >= 0.70 else 0
        adherence_binary = 1 if review_res.adherence_score >= 0.70 else 0

        verdict = review_res.verdict
        # Standardize PASS / FAIL
        if verdict == "WARN":
            verdict = "FAIL"

        return {
            "verdict": verdict,
            "faithfulness": faithfulness_binary,
            "groundedness": groundedness_binary,
            "code_correctness": code_correctness_binary,
            "adherence": adherence_binary,
            "scores": {
                "faithfulness": review_res.faithfulness_score,
                "groundedness": review_res.groundedness_score,
                "code_correctness": review_res.code_correctness_score,
                "adherence": review_res.adherence_score,
                "overall": review_res.overall_score,
            },
            "flagged_claims": review_res.flagged_claims,
            "hallucinated_code": review_res.hallucinated_code,
            "ungrounded_steps": review_res.ungrounded_steps,
            "reasoning": review_res.feedback,
        }


def run_calibration(
    calibration_data_path: Path = DEFAULT_CALIBRATION_DATA,
    report_output_path: Path = DEFAULT_CALIBRATION_REPORT,
    target_agreement_threshold: float = 80.0,
) -> Dict[str, Any]:
    """
    Run automated judge calibration over hand-graded benchmark dataset.
    Computes inter-rater reliability, Cohen's kappa, and records the report.
    """
    if not calibration_data_path.exists():
        raise FileNotFoundError(f"Calibration data not found at {calibration_data_path}")

    with open(calibration_data_path, "r", encoding="utf-8") as f:
        pairs = json.load(f)

    judge = LLMJudge()

    human_verdicts: List[str] = []
    judge_verdicts: List[str] = []
    human_faith: List[int] = []
    judge_faith: List[int] = []
    human_ground: List[int] = []
    judge_ground: List[int] = []
    human_code: List[int] = []
    judge_code: List[int] = []
    human_adhere: List[int] = []
    judge_adhere: List[int] = []

    detailed_evaluations: List[Dict[str, Any]] = []

    for pair in pairs:
        pid = pair["pair_id"]
        human_grade = pair["human_grade"]
        judge_eval = judge.evaluate_pair(pair)

        h_verdict = human_grade["verdict"]
        j_verdict = judge_eval["verdict"]
        is_agreement = (h_verdict == j_verdict)

        human_verdicts.append(h_verdict)
        judge_verdicts.append(j_verdict)

        human_faith.append(human_grade["faithfulness"])
        judge_faith.append(judge_eval["faithfulness"])

        human_ground.append(human_grade["groundedness"])
        judge_ground.append(judge_eval["groundedness"])

        human_code.append(human_grade.get("code_correctness", 1))
        judge_code.append(judge_eval["code_correctness"])

        human_adhere.append(human_grade["adherence"])
        judge_adhere.append(judge_eval["adherence"])

        detailed_evaluations.append({
            "pair_id": pid,
            "question_id": pair.get("question_id"),
            "topic": pair.get("topic"),
            "question": pair["question"],
            "human_grade": human_grade,
            "judge_grade": judge_eval,
            "agreement": is_agreement,
        })

    # Statistical metrics computation
    kappa_results = calculate_cohens_kappa(human_verdicts, judge_verdicts)
    total_pairs = len(pairs)
    matching_verdicts = sum(1 for h, j in zip(human_verdicts, judge_verdicts) if h == j)
    wilson_low, wilson_high = calculate_wilson_interval(matching_verdicts, total_pairs)

    faith_matches = sum(1 for h, j in zip(human_faith, judge_faith) if h == j)
    ground_matches = sum(1 for h, j in zip(human_ground, judge_ground) if h == j)
    code_matches = sum(1 for h, j in zip(human_code, judge_code) if h == j)
    adhere_matches = sum(1 for h, j in zip(human_adhere, judge_adhere) if h == j)

    observed_agreement = kappa_results["observed_agreement"]
    passed_threshold = observed_agreement >= target_agreement_threshold

    report = {
        "benchmark": "Tutorial Hell Navigator LLM Judge Calibration (Day 44)",
        "corpus_version": "LEGACY: corpus v1",
        "total_pairs": total_pairs,
        "calibration_status": "PASSED" if passed_threshold else "FAILED",
        "target_agreement_threshold_percent": target_agreement_threshold,
        "observed_agreement_percent": observed_agreement,
        "agreement_95_ci_percent": [wilson_low, wilson_high],
        "cohens_kappa": kappa_results["cohens_kappa"],
        "kappa_interpretation": kappa_results["interpretation"],
        "dimension_agreements": {
            "faithfulness_agreement_percent": round(faith_matches / total_pairs * 100, 2),
            "groundedness_agreement_percent": round(ground_matches / total_pairs * 100, 2),
            "code_correctness_agreement_percent": round(code_matches / total_pairs * 100, 2),
            "adherence_agreement_percent": round(adhere_matches / total_pairs * 100, 2),
        },
        "confusion_matrix": kappa_results["confusion_matrix"],
        "diagnostic_metrics": kappa_results["metrics"],
        "evaluator_provenance": {
            "human_curator": "Kumbham Nikhil",
            "hand_labeled_pairs_count": 50,
            "topics_covered": ["FastAPI", "Docker", "PostgreSQL", "Pydantic", "Refusal Controls"],
            "label_split": {
                "human_pass_count": sum(1 for v in human_verdicts if v == "PASS"),
                "human_fail_count": sum(1 for v in human_verdicts if v == "FAIL"),
                "judge_pass_count": sum(1 for v in judge_verdicts if v == "PASS"),
                "judge_fail_count": sum(1 for v in judge_verdicts if v == "FAIL"),
            },
        },
        "detailed_evaluations": detailed_evaluations,
    }

    report_output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(report_output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print(f"\n{'='*70}")
    print("=== LLM JUDGE CALIBRATION REPORT (Day 44) ===")
    print(f"{'='*70}")
    print(f"Total Graded Pairs:            {total_pairs}")
    print(f"Human-Judge Agreement:         {observed_agreement}% (95% CI: [{wilson_low}%, {wilson_high}%])")
    print(f"Target Threshold (>= 80%):     {'MET' if passed_threshold else 'FAILED'}")
    print(f"Cohen's Kappa (kappa):         {kappa_results['cohens_kappa']} ({kappa_results['interpretation']})")
    print(f"Faithfulness Agreement:        {report['dimension_agreements']['faithfulness_agreement_percent']}%")
    print(f"Groundedness Agreement:        {report['dimension_agreements']['groundedness_agreement_percent']}%")
    print(f"Code Correctness Agreement:    {report['dimension_agreements']['code_correctness_agreement_percent']}%")
    print(f"Adherence Agreement:           {report['dimension_agreements']['adherence_agreement_percent']}%")
    print(f"Confusion Matrix:              {kappa_results['confusion_matrix']}")
    print(f"Precision / Recall / F1:       {kappa_results['metrics']['precision']} / {kappa_results['metrics']['recall']} / {kappa_results['metrics']['f1_score']}")
    print(f"Saved Report:                  {report_output_path}")
    print(f"{'='*70}\n")

    return report


def main():
    parser = argparse.ArgumentParser(description="LLM Evaluation Judge Calibration")
    parser.add_argument(
        "--data",
        type=Path,
        default=DEFAULT_CALIBRATION_DATA,
        help="Path to hand-graded calibration pairs JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_CALIBRATION_REPORT,
        help="Path to output calibration report JSON",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Target agreement percentage threshold (default: 80.0)",
    )
    args = parser.parse_args()

    run_calibration(
        calibration_data_path=args.data,
        report_output_path=args.output,
        target_agreement_threshold=args.threshold,
    )


if __name__ == "__main__":
    main()
