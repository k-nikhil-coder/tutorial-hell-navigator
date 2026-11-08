#!/usr/bin/env python3
"""
CI Evaluation Gate for Tutorial Hell Navigator (Day 46)

Executes retrieval evaluation and span coverage verification against the
Gold Benchmark v2 DEV split. Fails the build (exit code 1) if any metric
regresses below the defined Phase 1 operational thresholds.

Thresholds:
- Overall Dev Hit@3:        >= 80.0% (Baseline target)
- Official Docs Hit@3:      >= 80.0% (Must not degrade below target)
- Evidence Coverage@3:      >= 80.0%
- Out-of-Scope Refusal:     >= 80.0%
- Span Coverage on Dev:     == 100.0% (All answerable spans present in corpus)
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_BENCHMARK_FILE = PROJECT_ROOT / "eval" / "gold_benchmark_v2.json"
REPORT_OUTPUT_FILE = PROJECT_ROOT / "eval" / "ci_eval_results.json"

THRESHOLDS = {
    "min_overall_hit_at_3": 80.0,
    "min_official_hit_at_3": 80.0,
    "min_evidence_coverage_at_3": 80.0,
    "min_refusal_rate": 80.0,
    "min_hit_at_5": 95.0,
}


def run_span_coverage_check() -> bool:
    """Run check_span_coverage.py to ensure zero missing spans in indexed chunks."""
    print("=" * 70)
    print("[STEP 1] Verifying Gold Benchmark Span Coverage...")
    print("=" * 70)
    cmd = [sys.executable, "-m", "pytest", "eval/check_span_coverage.py", "-v"]
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        print("[FAIL] Span coverage check failed. Answer spans are missing from corpus index.")
        return False
    print("[PASS] 100% of answerable gold spans exist in the indexed corpus.")
    return True


def run_retrieval_dev_eval() -> Dict[str, Any]:
    """Execute run_eval.py in retrieval-only mode against the dev split."""
    print("\n" + "=" * 70)
    print("[STEP 2] Running Automated Retrieval Evaluation on Dev Split...")
    print("=" * 70)
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "eval" / "run_eval.py"),
        "--gold-set", str(GOLD_BENCHMARK_FILE),
        "--retrieval-only",
        "--split-set", "dev",
        "-o", str(REPORT_OUTPUT_FILE),
    ]
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        print("[FAIL] run_eval.py exited with non-zero status.")
        sys.exit(1)

    if not REPORT_OUTPUT_FILE.exists():
        print(f"[FAIL] Output report file {REPORT_OUTPUT_FILE} was not created.")
        sys.exit(1)

    with open(REPORT_OUTPUT_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def audit_results(report: Dict[str, Any]) -> bool:
    """Audit report against regression thresholds."""
    print("\n" + "=" * 70)
    print("[STEP 3] Auditing Metrics Against CI Regression Thresholds...")
    print("=" * 70)

    with open(GOLD_BENCHMARK_FILE, "r", encoding="utf-8") as f:
        gold_benchmark = json.load(f)
    q_map = {q["id"]: q for q in gold_benchmark}

    ret_metrics = report.get("retrieval_metrics", {})
    ref_metrics = report.get("refusal_metrics", {})
    items = report.get("items", [])

    overall_hit3 = ret_metrics.get("hit_at_3", 0.0)
    overall_hit5 = ret_metrics.get("hit_at_5", 0.0)
    evidence_cov3 = ret_metrics.get("evidence_coverage_at_3", 0.0)
    refusal_rate = ref_metrics.get("refusal_rate", 0.0)

    # Calculate Official Docs vs Owner-Authored breakdown
    official_items = [
        it for it in items
        if q_map.get(it["id"], {}).get("source_kind") == "official"
        and q_map.get(it["id"], {}).get("answerability") == "answerable"
    ]
    official_hits3 = sum(1 for it in official_items if it.get("retrieval_metrics", {}).get("hit_at_3"))
    official_hit3_pct = round((official_hits3 / max(1, len(official_items))) * 100.0, 2)

    owner_items = [
        it for it in items
        if q_map.get(it["id"], {}).get("source_kind") == "owner_authored"
        and q_map.get(it["id"], {}).get("answerability") == "answerable"
    ]
    owner_hits3 = sum(1 for it in owner_items if it.get("retrieval_metrics", {}).get("hit_at_3"))
    owner_hit3_pct = round((owner_hits3 / max(1, len(owner_items))) * 100.0, 2)

    checks = [
        ("Overall Dev Hit@3", overall_hit3, THRESHOLDS["min_overall_hit_at_3"], overall_hit3 >= THRESHOLDS["min_overall_hit_at_3"]),
        ("Official Docs Hit@3", official_hit3_pct, THRESHOLDS["min_official_hit_at_3"], official_hit3_pct >= THRESHOLDS["min_official_hit_at_3"]),
        ("Evidence Coverage@3", evidence_cov3, THRESHOLDS["min_evidence_coverage_at_3"], evidence_cov3 >= THRESHOLDS["min_evidence_coverage_at_3"]),
        ("Out-of-Scope Refusal Rate", refusal_rate, THRESHOLDS["min_refusal_rate"], refusal_rate >= THRESHOLDS["min_refusal_rate"]),
        ("Overall Dev Hit@5", overall_hit5, THRESHOLDS["min_hit_at_5"], overall_hit5 >= THRESHOLDS["min_hit_at_5"]),
    ]

    all_passed = True
    print(f"{'Metric':<30} | {'Measured':<12} | {'Target':<10} | {'Status':<10}")
    print("-" * 70)
    for name, measured, target, passed in checks:
        status_str = "[PASS]" if passed else "[REGRESSED]"
        print(f"{name:<30} | {measured:>6.2f}%      | >={target:>5.1f}%   | {status_str}")
        if not passed:
            all_passed = False

    print("-" * 70)
    print(f"Owner-Authored Guides Hit@3: {owner_hit3_pct:.2f}% ({owner_hits3}/{len(owner_items)})")
    print(f"Official Docs Breakdown:     {official_hit3_pct:.2f}% ({official_hits3}/{len(official_items)})")
    print(f"Mean Reciprocal Rank (MRR):  {ret_metrics.get('mrr', 0.0):.4f}")
    print(f"Evaluated Items:             {len(items)} questions (31 answerable, 9 out-of-scope)")

    return all_passed


def main():
    print("[INFO] Running Tutorial Hell Navigator CI Evaluation Gate (Day 46)...")
    span_ok = run_span_coverage_check()
    if not span_ok:
        sys.exit(1)

    report = run_retrieval_dev_eval()
    passed = audit_results(report)

    if passed:
        print("\n[SUCCESS] ALL CI EVALUATION GATES PASSED! No retrieval regressions detected.")
        sys.exit(0)
    else:
        print("\n[FAIL] CI EVALUATION GATE FAILED: One or more metrics regressed below target thresholds.")
        sys.exit(1)


if __name__ == "__main__":
    main()
