"""
eval/bootstrap.py

Calculates bootstrap confidence intervals and paired bootstrap on per-question differences:
- 95% bootstrap confidence intervals with 1,000 resamples and seed 42.
- Paired bootstrap on the per-question difference between two modes.
- If the 95% interval is wider than 30 points, prints "INCONCLUSIVE".
"""

import sys
import json
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional


def bootstrap_ci(
    data: List[float],
    num_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
) -> Dict[str, float]:
    """
    Calculate non-parametric bootstrap confidence interval for a metric.
    
    Args:
        data: List of numeric values (one per question).
        num_resamples: Number of bootstrap iterations (default: 1000).
        ci: Confidence level (default: 0.95 for 95% CI).
        seed: Random seed for deterministic reproducibility.
        
    Returns:
        Dict with mean, ci_lower, ci_upper, and sample_size (n).
    """
    n = len(data)
    if n == 0:
        return {"mean": 0.0, "ci_lower": 0.0, "ci_upper": 0.0, "n": 0}

    point_estimate = sum(data) / n
    if n == 1:
        return {
            "mean": round(point_estimate, 4),
            "ci_lower": round(point_estimate, 4),
            "ci_upper": round(point_estimate, 4),
            "n": 1,
        }

    rng = random.Random(seed)
    resample_means: List[float] = []

    for _ in range(num_resamples):
        sample = [data[rng.randint(0, n - 1)] for _ in range(n)]
        resample_means.append(sum(sample) / n)

    resample_means.sort()

    alpha = 1.0 - ci
    lower_idx = int(round((alpha / 2.0) * num_resamples))
    upper_idx = int(round((1.0 - alpha / 2.0) * num_resamples)) - 1

    lower_idx = max(0, min(lower_idx, num_resamples - 1))
    upper_idx = max(0, min(upper_idx, num_resamples - 1))

    ci_lower = resample_means[lower_idx]
    ci_upper = resample_means[upper_idx]

    return {
        "mean": round(point_estimate, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "n": n,
    }


def paired_bootstrap_difference(
    scores_a: List[float],
    scores_b: List[float],
    num_resamples: int = 1000,
    ci: float = 0.95,
    seed: int = 42,
    max_width_points: float = 30.0,
) -> Dict[str, Any]:
    """
    Calculate paired bootstrap confidence interval on the per-question difference between two modes.
    
    Args:
        scores_a: Per-question scores for mode A.
        scores_b: Per-question scores for mode B (aligned with mode A).
        num_resamples: Number of bootstrap iterations (default: 1000).
        ci: Confidence level (default: 0.95 for 95% CI).
        seed: Random seed for deterministic reproducibility (default: 42).
        max_width_points: Maximum allowable CI width before declaring inconclusive (default: 30.0 points / 0.30).
        
    Returns:
        Dict with mean_diff, ci_lower, ci_upper, width, is_inconclusive, and status.
    """
    if len(scores_a) != len(scores_b):
        raise ValueError(
            f"Input lists must have identical length (got {len(scores_a)} and {len(scores_b)})."
        )

    n = len(scores_a)
    if n == 0:
        return {
            "mean_diff": 0.0,
            "ci_lower": 0.0,
            "ci_upper": 0.0,
            "width": 0.0,
            "threshold": max_width_points,
            "is_wider_than_30_points": True,
            "is_inconclusive": True,
            "status": "INCONCLUSIVE",
            "n": 0,
        }

    # Per-question difference: d_i = score_a_i - score_b_i
    diffs = [float(a) - float(b) for a, b in zip(scores_a, scores_b)]
    point_estimate = sum(diffs) / n

    rng = random.Random(seed)
    resample_diff_means: List[float] = []

    for _ in range(num_resamples):
        sample_diffs = [diffs[rng.randint(0, n - 1)] for _ in range(n)]
        resample_diff_means.append(sum(sample_diffs) / n)

    resample_diff_means.sort()

    alpha = 1.0 - ci
    lower_idx = int(round((alpha / 2.0) * num_resamples))
    upper_idx = int(round((1.0 - alpha / 2.0) * num_resamples)) - 1

    lower_idx = max(0, min(lower_idx, num_resamples - 1))
    upper_idx = max(0, min(upper_idx, num_resamples - 1))

    ci_lower = resample_diff_means[lower_idx]
    ci_upper = resample_diff_means[upper_idx]
    width = ci_upper - ci_lower

    # Scale check: if values are in [0, 1], 30 points corresponds to 0.30.
    # If values are in percentage scale [0, 100], 30 points corresponds to 30.0.
    max_abs_val = max(abs(d) for d in diffs) if diffs else 0.0
    threshold = max_width_points if max_abs_val > 1.0 else (max_width_points / 100.0)

    is_wider = width > threshold
    status = "INCONCLUSIVE" if is_wider else "CONCLUSIVE"

    return {
        "mean_diff": round(point_estimate, 4),
        "ci_lower": round(ci_lower, 4),
        "ci_upper": round(ci_upper, 4),
        "width": round(width, 4),
        "threshold": round(threshold, 4),
        "is_wider_than_30_points": is_wider,
        "is_inconclusive": is_wider,
        "status": status,
        "n": n,
    }


def extract_per_query_metrics(report_data: Dict[str, Any]) -> Tuple[List[float], List[float], List[float]]:
    """
    Extract per-query Recall@3, Recall@5, and MRR (reciprocal rank) values
    from an evaluation report JSON file. Only includes questions that have ground truth.
    """
    items = report_data.get("items", [])
    r3_vals: List[float] = []
    r5_vals: List[float] = []
    mrr_vals: List[float] = []

    for item in items:
        rm = item.get("retrieval_metrics")
        sc = item.get("score")

        if rm and isinstance(rm, dict) and rm.get("has_ground_truth"):
            r3_vals.append(float(rm.get("recall_at_3", 0.0) or 0.0))
            r5_vals.append(float(rm.get("recall_at_5", 0.0) or 0.0))
            mrr_vals.append(float(rm.get("reciprocal_rank", 0.0) or 0.0))
        elif sc and isinstance(sc, dict) and item.get("expected_chunk_ids"):
            retrieved = item.get("retrieved_chunk_ids", [])
            expected = set(item.get("expected_chunk_ids", []))
            r3 = 1.0 if any(cid in expected for cid in retrieved[:3]) else 0.0
            r5 = 1.0 if any(cid in expected for cid in retrieved[:5]) else 0.0
            rr = 0.0
            for rank, cid in enumerate(retrieved, 1):
                if cid in expected:
                    rr = 1.0 / rank
                    break
            r3_vals.append(r3)
            r5_vals.append(r5)
            mrr_vals.append(rr)

    return r3_vals, r5_vals, mrr_vals


def extract_per_question_metric_map(report_data: Dict[str, Any]) -> Dict[str, Dict[str, float]]:
    """Map question_id -> {metric_name: value} from report data."""
    items = report_data.get("items", [])
    metrics_map: Dict[str, Dict[str, float]] = {}

    for item in items:
        qid = item.get("id")
        if not qid:
            continue

        rm = item.get("retrieval_metrics") or {}
        sc = item.get("score") or {}

        has_gt = rm.get("has_ground_truth") or bool(item.get("expected_chunk_ids"))
        r3 = float(rm.get("recall_at_3", 0.0) or 0.0)
        r5 = float(rm.get("recall_at_5", 0.0) or 0.0)
        mrr = float(rm.get("reciprocal_rank", 0.0) or 0.0)

        # Correctness score from LLM evaluation
        correctness = 1.0 if sc.get("passed") else 0.0

        entry = {
            "has_ground_truth": 1.0 if has_gt else 0.0,
            "correctness": correctness,
        }
        if has_gt:
            entry["recall_at_3"] = r3
            entry["recall_at_5"] = r5
            entry["mrr"] = mrr

        metrics_map[qid] = entry

    return metrics_map


def compute_report_bootstraps(
    report_path: Path,
    num_resamples: int = 1000,
    seed: int = 42,
) -> Dict[str, Any]:
    """Load an evaluation report and calculate 95% CIs for Recall@3, Recall@5, and MRR."""
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if "configurations" in data:
        results = {}
        for cfg_name, cfg_data in data["configurations"].items():
            r3, r5, mrr = extract_per_query_metrics(cfg_data)
            results[cfg_name] = {
                "recall_at_3": bootstrap_ci(r3, num_resamples, seed=seed),
                "recall_at_5": bootstrap_ci(r5, num_resamples, seed=seed),
                "mrr": bootstrap_ci(mrr, num_resamples, seed=seed),
            }
        return {"report": str(report_path), "configurations": results}

    r3, r5, mrr = extract_per_query_metrics(data)
    return {
        "report": str(report_path),
        "metrics": {
            "recall_at_3": bootstrap_ci(r3, num_resamples, seed=seed),
            "recall_at_5": bootstrap_ci(r5, num_resamples, seed=seed),
            "mrr": bootstrap_ci(mrr, num_resamples, seed=seed),
        },
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Calculate 95% bootstrap confidence intervals and paired difference between two modes")
    parser.add_argument("--report", help="Path to evaluation report JSON")
    parser.add_argument("--compare", nargs=2, help="Compare two mode reports using paired bootstrap on per-question difference")
    parser.add_argument("--resamples", type=int, default=1000, help="Number of bootstrap resamples (default: 1000)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed (default: 42)")
    args = parser.parse_args()

    if args.compare:
        p1 = Path(args.compare[0])
        p2 = Path(args.compare[1])
        with open(p1, "r", encoding="utf-8") as f:
            data1 = json.load(f)
        with open(p2, "r", encoding="utf-8") as f:
            data2 = json.load(f)

        map1 = extract_per_question_metric_map(data1)
        map2 = extract_per_question_metric_map(data2)

        # Common question IDs
        common_ids = sorted(list(set(map1.keys()) & set(map2.keys())))

        print("=" * 80)
        print("PAIRED BOOTSTRAP: PER-QUESTION DIFFERENCE BETWEEN TWO MODES (1,000 Resamples, Seed 42)")
        print(f"Mode A (Report 1): {p1.name}")
        print(f"Mode B (Report 2): {p2.name}")
        print(f"Questions compared: {len(common_ids)}")
        print("-" * 80)

        metrics_to_test = ["recall_at_3", "recall_at_5", "mrr", "correctness"]
        any_inconclusive = False

        for metric in metrics_to_test:
            vals_a = []
            vals_b = []
            for qid in common_ids:
                if metric in map1[qid] and metric in map2[qid]:
                    vals_a.append(map1[qid][metric])
                    vals_b.append(map2[qid][metric])

            if not vals_a:
                continue

            res = paired_bootstrap_difference(
                vals_a, vals_b, num_resamples=args.resamples, seed=args.seed, max_width_points=30.0
            )

            print(f"Metric: {metric.upper()} (n={res['n']})")
            print(f"  Mean Difference (A - B): {res['mean_diff']:+.4f}")
            print(f"  95% CI on Difference:   [{res['ci_lower']:+.4f}, {res['ci_upper']:+.4f}] (Width: {res['width']:.4f})")

            if res["is_inconclusive"]:
                print("  Status: INCONCLUSIVE (95% interval is wider than 30 points)")
                print("INCONCLUSIVE")
                any_inconclusive = True
            else:
                sig = "Significant" if (res["ci_lower"] > 0 or res["ci_upper"] < 0) else "Not Significant (includes 0)"
                print(f"  Status: CONCLUSIVE ({sig})")
            print()

        print("=" * 80)
        return

    if args.report:
        p = Path(args.report)
        res = compute_report_bootstraps(p, num_resamples=args.resamples, seed=args.seed)
        print(json.dumps(res, indent=2))
        return

    parser.print_help()


if __name__ == "__main__":
    main()
