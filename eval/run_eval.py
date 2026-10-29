import sys
import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas import NavigatorResponse
from app.client import generate_structured_response_async
from app.rag import retrieve_relevant_chunks

VAGUE_PHRASES = [
    "keep practicing",
    "just practice more",
    "copy and paste this",
    "just google it",
    "don't worry about understanding",
    "here is the complete code for everything",
]


def calculate_retrieval_metrics(
    retrieved_chunk_ids: List[str],
    expected_chunk_ids: List[str],
) -> Dict[str, Any]:
    """Calculate Recall@3, Recall@5, and Reciprocal Rank (RR) against ground truth."""
    if not expected_chunk_ids:
        return {
            "has_ground_truth": False,
            "recall_at_3": None,
            "recall_at_5": None,
            "reciprocal_rank": None,
            "first_hit_rank": None,
        }

    expected_set = set(expected_chunk_ids)

    # Recall@3: is any expected chunk in top 3?
    top_3 = set(retrieved_chunk_ids[:3])
    hit_at_3 = len(top_3 & expected_set) > 0
    recall_at_3 = 1.0 if hit_at_3 else 0.0

    # Recall@5: is any expected chunk in top 5?
    top_5 = set(retrieved_chunk_ids[:5])
    hit_at_5 = len(top_5 & expected_set) > 0
    recall_at_5 = 1.0 if hit_at_5 else 0.0

    # Reciprocal Rank (MRR component): 1/rank of first ground truth hit
    first_hit_rank = None
    reciprocal_rank = 0.0
    for rank_idx, cid in enumerate(retrieved_chunk_ids, 1):
        if cid in expected_set:
            first_hit_rank = rank_idx
            reciprocal_rank = round(1.0 / rank_idx, 4)
            break

    return {
        "has_ground_truth": True,
        "recall_at_3": recall_at_3,
        "recall_at_5": recall_at_5,
        "reciprocal_rank": reciprocal_rank,
        "first_hit_rank": first_hit_rank,
    }


def score_response(
    response: NavigatorResponse,
    expected_rubric: List[str],
    negative_constraints: List[str],
) -> Dict[str, Any]:
    issues = []

    # Check that at least one concrete command is provided for in-corpus responses
    commands = [step.command for step in response.action_plan if step.command]
    if not commands and not response.is_refusal:
        issues.append("Action plan is missing CLI commands or code snippets.")

    if not response.anti_patterns_to_avoid:
        issues.append("Missing anti-patterns section.")

    haystack = (
        response.summary
        + " "
        + " ".join(s.explanation for s in response.action_plan)
        + " "
        + " ".join(response.anti_patterns_to_avoid)
    ).lower()

    for phrase in VAGUE_PHRASES:
        if phrase in haystack:
            issues.append(f"Contains generic advice phrase: '{phrase}'")

    for neg in negative_constraints:
        if neg.lower() in haystack:
            issues.append(f"Hit negative constraint: '{neg}'")

    # Count citations across steps
    all_citations = []
    for s in response.action_plan:
        if s.citations:
            all_citations.extend(s.citations)

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "step_count": len(response.action_plan),
        "command_count": len(commands),
        "citation_count": len(all_citations),
        "cited_chunks": list(dict.fromkeys(all_citations)),
        "is_refusal": response.is_refusal,
    }


async def evaluate_benchmark(
    gold_set_path: str = "eval/gold_set.json",
    limit: Optional[int] = None,
    category_filter: Optional[str] = None,
    output_path: str = "eval/eval_report.json",
    search_mode: str = "hybrid",
    retrieval_only: bool = False,
    delay: float = 1.2,
):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    path = Path(gold_set_path)
    if not path.exists():
        print(f"File not found: {gold_set_path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if category_filter:
        questions = [q for q in questions if category_filter.lower() in q.get("category", "").lower()]

    batch = questions[:limit] if limit else questions

    mode_label = search_mode.upper()
    print("=" * 75)
    print(f"🧪 EVALUATION HARNESS: {mode_label} SEARCH")
    print(f"  • Questions to test: {len(batch)} (out of {len(questions)} in gold set)")
    print(f"  • Evaluation mode:   {'Retrieval-Only (Recall@K & MRR)' if retrieval_only else 'End-to-End (Retrieval + LLM Generation)'}")
    print(f"  • Search engine:     {mode_label} (Qdrant)")
    print("=" * 75)

    results = []
    passed = 0
    total_steps = 0
    total_commands = 0
    total_citations = 0
    refusals = 0

    # Retrieval benchmark counters
    queries_with_gt = 0
    recall_3_hits = 0
    recall_5_hits = 0
    rr_sum = 0.0

    for idx, item in enumerate(batch, 1):
        qid = item.get("id", f"Q{idx}")
        category = item.get("category", "General")
        prompt = item.get("question", "")
        rubric = item.get("expected_rubric", [])
        negatives = item.get("negative_constraints", [])
        expected_chunk_ids = item.get("expected_chunk_ids", [])

        # 1. Fetch retrieval candidates (top-5 for Recall@3 and Recall@5 calculation)
        retrieved_raw = retrieve_relevant_chunks(prompt, top_k=5, search_mode=search_mode)
        retrieved_chunk_ids = [c["chunk_id"] for c in retrieved_raw]

        retrieval_metrics = calculate_retrieval_metrics(retrieved_chunk_ids, expected_chunk_ids)

        if retrieval_metrics["has_ground_truth"]:
            queries_with_gt += 1
            if retrieval_metrics["recall_at_3"] == 1.0:
                recall_3_hits += 1
            if retrieval_metrics["recall_at_5"] == 1.0:
                recall_5_hits += 1
            rr_sum += retrieval_metrics["reciprocal_rank"]

        print(f"[{idx:02d}/{len(batch):02d}] {qid} ({category[:22]}):", end=" ", flush=True)

        if retrieval_only:
            # Print retrieval score directly
            if retrieval_metrics["has_ground_truth"]:
                hit_rank = retrieval_metrics["first_hit_rank"]
                r3 = retrieval_metrics["recall_at_3"]
                rr = retrieval_metrics["reciprocal_rank"]
                status = f"HIT (Rank #{hit_rank}, RR={rr:.2f})" if hit_rank else "MISS (Not in top 5)"
                print(f"R@3={r3:.0f} | {status} | Top: {retrieved_chunk_ids[:3]}")
            else:
                print(f"Top: {retrieved_chunk_ids[:3]}")

            results.append({
                "id": qid,
                "category": category,
                "question": prompt,
                "expected_chunk_ids": expected_chunk_ids,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "retrieval_metrics": retrieval_metrics,
            })
            continue

        # 2. End-to-end evaluation with LLM response generation
        try:
            model_resp = await generate_structured_response_async(prompt, search_mode=search_mode)
            result = score_response(model_resp, rubric, negatives)

            step_cnt = result["step_count"]
            cmd_cnt = result["command_count"]
            cit_cnt = result["citation_count"]
            is_ref = result["is_refusal"]

            total_steps += step_cnt
            total_commands += cmd_cnt
            total_citations += cit_cnt
            if is_ref:
                refusals += 1

            if result["passed"]:
                passed += 1
                status_str = f"PASS ({step_cnt} steps, {cmd_cnt} cmds, {cit_cnt} cites"
                if retrieval_metrics["has_ground_truth"]:
                    status_str += f", MRR={retrieval_metrics['reciprocal_rank']:.2f}"
                if is_ref:
                    status_str += ", [REFUSAL]"
                status_str += ")"
                print(status_str)
            else:
                print(f"FAIL -> {'; '.join(result['issues'])}")

            results.append({
                "id": qid,
                "category": category,
                "question": prompt,
                "expected_chunk_ids": expected_chunk_ids,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "retrieval_metrics": retrieval_metrics,
                "score": result,
                "response": model_resp.model_dump(),
            })
        except Exception as e:
            print(f"ERROR: {e}")
            results.append({
                "id": qid,
                "category": category,
                "question": prompt,
                "error": str(e),
                "score": {"passed": False, "issues": [str(e)]},
                "retrieval_metrics": retrieval_metrics,
            })

        # Pacing between queries to avoid hitting rate limits
        if idx < len(batch) and delay > 0:
            await asyncio.sleep(delay)

    # Compute aggregate metrics
    pass_rate = (passed / len(batch)) * 100 if batch and not retrieval_only else None
    n = len(batch) or 1
    avg_steps = round(total_steps / n, 2) if not retrieval_only else None
    avg_commands = round(total_commands / n, 2) if not retrieval_only else None
    avg_citations = round(total_citations / n, 2) if not retrieval_only else None

    mean_recall_3 = round((recall_3_hits / queries_with_gt) * 100, 2) if queries_with_gt else 0.0
    mean_recall_5 = round((recall_5_hits / queries_with_gt) * 100, 2) if queries_with_gt else 0.0
    mrr = round(rr_sum / queries_with_gt, 4) if queries_with_gt else 0.0

    print("=" * 75)
    print(f"📊 BENCHMARK SUMMARY ({mode_label} PIPELINE)")
    print(f"  • Evaluated Questions:       {len(batch)}")
    print(f"  • Ground-Truth Mapped:       {queries_with_gt}")
    print(f"  • Recall@3:                  {recall_3_hits}/{queries_with_gt} ({mean_recall_3:.1f}%)")
    print(f"  • Recall@5:                  {recall_5_hits}/{queries_with_gt} ({mean_recall_5:.1f}%)")
    print(f"  • Mean Reciprocal Rank (MRR):{mrr:.4f}")
    if not retrieval_only:
        print(f"  • LLM Pass Rate:             {passed}/{len(batch)} ({pass_rate:.1f}%)")
        print(f"  • Avg Commands / Plan:       {avg_commands}")
        print(f"  • Avg Citations / Plan:      {avg_citations}")
    print("=" * 75)

    report = {
        "benchmark": "Tutorial Hell Navigator Hardened Gold Set",
        "search_mode": search_mode,
        "retrieval_only": retrieval_only,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_evaluated": len(batch),
        "ground_truth_count": queries_with_gt,
        "retrieval_metrics": {
            "recall_at_3": mean_recall_3,
            "recall_at_5": mean_recall_5,
            "mrr": mrr,
            "recall_3_hits": recall_3_hits,
            "recall_5_hits": recall_5_hits,
        },
        "llm_metrics": {
            "passed": passed,
            "pass_rate": pass_rate,
            "avg_steps_per_plan": avg_steps,
            "avg_commands_per_plan": avg_commands,
            "avg_citations_per_plan": avg_citations,
            "refusals_handled": refusals,
        } if not retrieval_only else None,
        "items": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {output_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Gold Benchmark Evaluator with Recall@K and MRR")
    parser.add_argument("--gold-set", default="eval/gold_set.json", help="Path to gold set json")
    parser.add_argument("-n", "--limit", type=int, default=None, help="Number of questions to test")
    parser.add_argument("-c", "--category", default=None, help="Filter by category substring")
    parser.add_argument("-m", "--mode", choices=["hybrid", "dense", "sparse"], default="hybrid", help="Search engine mode")
    parser.add_argument("--retrieval-only", action="store_true", help="Run retrieval evaluation only (no LLM generation)")
    parser.add_argument("-o", "--output", default="eval/eval_report.json", help="Report output json path")
    parser.add_argument("-d", "--delay", type=float, default=1.2, help="Delay in seconds between questions")

    args = parser.parse_args()
    asyncio.run(
        evaluate_benchmark(
            gold_set_path=args.gold_set,
            limit=args.limit,
            category_filter=args.category,
            output_path=args.output,
            search_mode=args.mode,
            retrieval_only=args.retrieval_only,
            delay=args.delay,
        )
    )


if __name__ == "__main__":
    main()
