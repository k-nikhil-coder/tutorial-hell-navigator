"""
tests/test_judge_calibration.py

Unit tests verifying the Day 44 LLM Judge Calibration (eval/judge.py).
Checks:
1. Exact Cohen's kappa and Wilson interval mathematical calculations.
2. Calibration dataset integrity (eval/judge_calibration_data.json): exactly 50 pairs,
   all required fields, realistic pass/fail distribution.
3. Judge calibration execution meets the target threshold (>= 80% agreement).
4. Calibration report (eval/judge_calibration_report.json) structure and provenance.
"""

import json
import pytest
from pathlib import Path
from eval.judge import (
    calculate_cohens_kappa,
    calculate_wilson_interval,
    run_calibration,
    DEFAULT_CALIBRATION_DATA,
    DEFAULT_CALIBRATION_REPORT,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_calculate_wilson_interval():
    low, high = calculate_wilson_interval(42, 50, confidence=0.95)
    assert 70.0 <= low <= 80.0
    assert 85.0 <= high <= 95.0
    assert low < high

    # Edge cases
    assert calculate_wilson_interval(0, 0) == (0.0, 0.0)
    low_zero, high_zero = calculate_wilson_interval(0, 50)
    assert low_zero == 0.0
    assert high_zero > 0.0


def test_calculate_cohens_kappa_perfect_agreement():
    human = ["PASS", "PASS", "FAIL", "FAIL"]
    judge = ["PASS", "PASS", "FAIL", "FAIL"]
    res = calculate_cohens_kappa(human, judge)
    assert res["observed_agreement"] == 100.0
    assert res["cohens_kappa"] == 1.0
    assert "Almost perfect" in res["interpretation"]
    assert res["confusion_matrix"]["true_positives"] == 2
    assert res["confusion_matrix"]["true_negatives"] == 2
    assert res["confusion_matrix"]["false_positives"] == 0
    assert res["confusion_matrix"]["false_negatives"] == 0


def test_calculate_cohens_kappa_imperfect_agreement():
    human = ["PASS", "PASS", "PASS", "FAIL", "FAIL"]
    judge = ["PASS", "PASS", "FAIL", "FAIL", "FAIL"]  # 1 disagreement (FN)
    res = calculate_cohens_kappa(human, judge)
    assert res["observed_agreement"] == 80.0
    assert 0.50 <= res["cohens_kappa"] <= 0.80
    assert res["confusion_matrix"]["true_positives"] == 2
    assert res["confusion_matrix"]["true_negatives"] == 2
    assert res["confusion_matrix"]["false_negatives"] == 1


def test_judge_calibration_dataset_integrity():
    assert DEFAULT_CALIBRATION_DATA.exists(), "judge_calibration_data.json not found"
    with open(DEFAULT_CALIBRATION_DATA, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Exactly 50 hand-graded pairs
    assert len(data) == 50, f"Expected exactly 50 calibration pairs, found {len(data)}"

    # 2. Check structure of each pair
    required_keys = {
        "pair_id", "question_id", "topic", "question", "retrieved_chunks",
        "generated_response", "judge_criteria", "human_grade",
    }
    required_human_keys = {
        "faithfulness", "groundedness", "code_correctness", "adherence",
        "verdict", "graded_by", "grade_notes",
    }

    pass_count = 0
    fail_count = 0

    for pair in data:
        assert required_keys.issubset(set(pair.keys())), f"Missing keys in {pair.get('pair_id')}"
        hg = pair["human_grade"]
        assert required_human_keys.issubset(set(hg.keys())), f"Missing human_grade keys in {pair.get('pair_id')}"
        assert hg["verdict"] in ("PASS", "FAIL")
        if hg["verdict"] == "PASS":
            pass_count += 1
        else:
            fail_count += 1
        assert hg["graded_by"] == "Kumbham Nikhil"
        assert len(hg["grade_notes"]) > 5

    # 3. Label balance: ensure both classes are well represented
    assert pass_count >= 25, "Expected at least 25 PASS pairs"
    assert fail_count >= 10, "Expected at least 10 FAIL pairs"


def test_run_calibration_meets_target_threshold(tmp_path):
    report_file = tmp_path / "test_report.json"
    report = run_calibration(
        calibration_data_path=DEFAULT_CALIBRATION_DATA,
        report_output_path=report_file,
        target_agreement_threshold=80.0,
    )

    assert report["total_pairs"] == 50
    assert report["observed_agreement_percent"] >= 80.0, (
        f"Observed agreement {report['observed_agreement_percent']}% fell below 80% threshold"
    )
    assert report["calibration_status"] == "PASSED"
    assert report["cohens_kappa"] >= 0.50
    assert len(report["detailed_evaluations"]) == 50


def test_production_calibration_report_integrity():
    assert DEFAULT_CALIBRATION_REPORT.exists(), "eval/judge_calibration_report.json not found"
    with open(DEFAULT_CALIBRATION_REPORT, "r", encoding="utf-8") as f:
        rep = json.load(f)

    assert rep["total_pairs"] == 50
    assert rep["observed_agreement_percent"] >= 80.0
    assert rep["calibration_status"] == "PASSED"
    assert rep["cohens_kappa"] > 0.60
    assert rep["evaluator_provenance"]["human_curator"] == "Kumbham Nikhil"
    assert rep["evaluator_provenance"]["hand_labeled_pairs_count"] == 50
