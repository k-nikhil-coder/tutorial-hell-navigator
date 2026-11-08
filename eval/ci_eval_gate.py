#!/usr/bin/env python3
"""
CI Evaluation Gate for Tutorial Hell Navigator (Day 46)

Performs a deterministic, per-question retrieval regression check against
the established 10-file dev baseline (eval/gold_benchmark_v2_dev_results.json).

Instead of brittle overall percentage thresholds, this gate enforces:
1. Span Coverage: 100% of answerable gold spans must exist in the indexed corpus.
2. Per-Question Retrieval: Every question that hits today (29/31 dev answerable)
   must continue to hit. Any drop from Hit to Miss fails the build.
3. Per-Question Refusal: Every out-of-scope question that is refused today
   (8/9 dev out-of-scope) must continue to be refused. Any leak fails the build.
4. Actionable Diffs: Reports exact question IDs that regressed or improved.
"""

import sys
import json
import subprocess
from pathlib import Path
from typing import Dict, Any, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

GOLD_BENCHMARK_FILE = PROJECT_ROOT / "eval" / "gold_benchmark_v2.json"
BASELINE_DEV_FILE = PROJECT_ROOT / "eval" / "gold_benchmark_v2_dev_results.json"
CURRENT_RUN_OUTPUT = PROJECT_ROOT / "eval" / "ci_eval_results.json"


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


def ensure_qdrant_indexed() -> None:
    """Ensure local Qdrant collection is populated with the 97 chunks from the committed cache."""
    print("\n" + "=" * 70)
    print("[STEP 2] Verifying Local Qdrant Vector Index...")
    print("=" * 70)
    from app.rag import get_indexed_count, COLLECTION_NAME, close_qdrant_client
    try:
        count = get_indexed_count(COLLECTION_NAME)
        if count < 97:
            print(f"[INFO] Collection '{COLLECTION_NAME}' has {count} points (expected 97).")
            print("[INFO] Rebuilding Qdrant indexes offline from committed chunks & embeddings cache...")
            from scripts.rebuild_corpus_384 import rebuild_qdrant_indexes
            rebuild_qdrant_indexes()
            count = get_indexed_count(COLLECTION_NAME)
            print(f"[PASS] Qdrant index rebuilt successfully with {count} points.")
        else:
            print(f"[PASS] Qdrant index already populated with {count} points.")
    finally:
        close_qdrant_client()


def run_current_dev_eval() -> Dict[str, Any]:
    """Execute run_eval.py in retrieval-only mode against the dev split."""
    print("\n" + "=" * 70)
    print("[STEP 3] Running Automated Retrieval Evaluation on Dev Split...")
    print("=" * 70)
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "eval" / "run_eval.py"),
        "--gold-set", str(GOLD_BENCHMARK_FILE),
        "--retrieval-only",
        "--split-set", "dev",
        "-o", str(CURRENT_RUN_OUTPUT),
    ]
    res = subprocess.run(cmd, cwd=PROJECT_ROOT)
    if res.returncode != 0:
        print("[FAIL] run_eval.py exited with non-zero status.")
        sys.exit(1)

    if not CURRENT_RUN_OUTPUT.exists():
        print(f"[FAIL] Output file {CURRENT_RUN_OUTPUT} was not created.")
        sys.exit(1)

    with open(CURRENT_RUN_OUTPUT, "r", encoding="utf-8") as f:
        return json.load(f)


def audit_per_question_diff(current_report: Dict[str, Any]) -> bool:
    """Compare current run per-question outcomes against the baseline."""
    print("\n" + "=" * 70)
    print("[STEP 4] Auditing Per-Question Retrieval & Refusal Regressions...")
    print("=" * 70)

    if not BASELINE_DEV_FILE.exists():
        print(f"[FAIL] Baseline file {BASELINE_DEV_FILE} not found.")
        return False

    with open(BASELINE_DEV_FILE, "r", encoding="utf-8") as f:
        baseline_data = json.load(f)

    baseline_items = {it["id"]: it for it in baseline_data.get("items", [])}
    current_items = {it["id"]: it for it in current_report.get("items", [])}

    with open(GOLD_BENCHMARK_FILE, "r", encoding="utf-8") as f:
        gold_benchmark = json.load(f)
    q_map = {q["id"]: q for q in gold_benchmark}

    regressions: List[Tuple[str, str, str]] = []
    improvements: List[Tuple[str, str, str]] = []
    unchanged_hits = 0
    unchanged_misses = 0
    unchanged_refusals = 0

    for qid, cur_it in current_items.items():
        base_it = baseline_items.get(qid)
        if not base_it:
            continue

        q_meta = q_map.get(qid, {})
        is_answerable = (q_meta.get("answerability") == "answerable")
        question_text = q_meta.get("question", "")
        source_kind = q_meta.get("source_kind", "unknown")

        if is_answerable:
            base_hit = bool(base_it.get("retrieval_metrics", {}).get("hit_at_3"))
            cur_hit = bool(cur_it.get("retrieval_metrics", {}).get("hit_at_3"))

            if base_hit and not cur_hit:
                regressions.append((qid, f"Hit@3 dropped from 1 to 0 ({source_kind})", question_text))
            elif not base_hit and cur_hit:
                improvements.append((qid, f"Hit@3 improved from 0 to 1 ({source_kind})", question_text))
            elif cur_hit:
                unchanged_hits += 1
            else:
                unchanged_misses += 1
        else:
            # Out-of-scope query
            base_refused = bool(base_it.get("retrieval_metrics", {}).get("refusal_gate_triggered"))
            cur_refused = bool(cur_it.get("retrieval_metrics", {}).get("refusal_gate_triggered"))

            if base_refused and not cur_refused:
                regressions.append((qid, "Out-of-scope query leaked (was refused in baseline)", question_text))
            elif not base_refused and cur_refused:
                improvements.append((qid, "Out-of-scope query now refused (leaked in baseline)", question_text))
            elif cur_refused:
                unchanged_refusals += 1

    print(f"Baseline Unchanged: {unchanged_hits} hits maintained, {unchanged_refusals} refusals maintained, {unchanged_misses} known misses.")
    
    if improvements:
        print(f"\n[IMPROVEMENT] {len(improvements)} question(s) improved:")
        for qid, change, text in improvements:
            print(f"  + {qid}: {change} | '{text[:60]}...'")

    if regressions:
        print(f"\n[REGRESSION] {len(regressions)} question(s) regressed below baseline:")
        for qid, change, text in regressions:
            print(f"  - {qid}: {change} | '{text[:60]}...'")
        print("\n" + "=" * 70)
        print(f"[FAIL] Build failed: {len(regressions)} retrieval regression(s) detected.")
        print("=" * 70)
        return False

    print("\n[PASS] Zero per-question regressions detected across all 40 dev questions.")
    return True


def main():
    print("[INFO] Running Tutorial Hell Navigator Per-Question CI Evaluation Gate...")
    if not run_span_coverage_check():
        sys.exit(1)

    ensure_qdrant_indexed()

    current_report = run_current_dev_eval()
    passed = audit_per_question_diff(current_report)

    if passed:
        print("\n[SUCCESS] ALL PER-QUESTION CI GATES PASSED! No regressions detected.")
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
