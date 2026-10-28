import sys
import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas import NavigatorResponse
from app.client import generate_structured_response_async

VAGUE_PHRASES = [
    "keep practicing",
    "just practice more",
    "copy and paste this",
    "just google it",
    "don't worry about understanding",
    "here is the complete code for everything",
]


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
    limit: int = 5,
    category_filter: str = None,
    output_path: str = "eval/eval_report.json",
    delay: float = 1.5,
):
    from datetime import datetime, timezone

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

    batch = questions[:limit]
    print(f"Running evaluation on {len(batch)} questions (out of {len(questions)} total)...")
    print("=" * 70)

    results = []
    passed = 0
    total_steps = 0
    total_commands = 0
    total_citations = 0
    refusals = 0

    for idx, item in enumerate(batch, 1):
        qid = item.get("id", f"Q{idx}")
        category = item.get("category", "General")
        prompt = item.get("question", "")
        rubric = item.get("expected_rubric", [])
        negatives = item.get("negative_constraints", [])

        print(f"[{idx:02d}/{len(batch):02d}] {qid} ({category[:24]}):", end=" ", flush=True)

        try:
            model_resp = await generate_structured_response_async(prompt)
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
            })

        # Pacing between queries to avoid hitting rate limits
        if idx < len(batch) and delay > 0:
            await asyncio.sleep(delay)

    pass_rate = (passed / len(batch)) * 100 if batch else 0
    n = len(batch) or 1
    avg_steps = round(total_steps / n, 2)
    avg_commands = round(total_commands / n, 2)
    avg_citations = round(total_citations / n, 2)

    print("=" * 70)
    print("📊 GOLD SET EVALUATION SUMMARY (Day 35 Baseline)")
    print(f"  • Pass Rate:          {passed}/{len(batch)} ({pass_rate:.1f}%)")
    print(f"  • Avg Steps / Plan:   {avg_steps}")
    print(f"  • Avg Commands / Plan:{avg_commands}")
    print(f"  • Avg Citations / Plan:{avg_citations}")
    print(f"  • Refusals Handled:   {refusals}")
    print("=" * 70)

    report = {
        "benchmark": "Tutorial Hell Navigator 80-Question Gold Set",
        "milestone": "Day 35 Naive RAG Baseline",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_evaluated": len(batch),
        "passed": passed,
        "failed": len(batch) - passed,
        "pass_rate": pass_rate,
        "metrics": {
            "avg_steps_per_plan": avg_steps,
            "avg_commands_per_plan": avg_commands,
            "avg_citations_per_plan": avg_citations,
            "total_citations": total_citations,
            "refusals_handled": refusals,
        },
        "items": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Gold Benchmark Evaluator")
    parser.add_argument("--gold-set", default="eval/gold_set.json", help="Path to gold set json")
    parser.add_argument("-n", "--limit", type=int, default=10, help="Number of questions to test")
    parser.add_argument("-c", "--category", default=None, help="Filter by category substring")
    parser.add_argument("-o", "--output", default="eval/eval_report.json", help="Report output json path")
    parser.add_argument("-d", "--delay", type=float, default=1.5, help="Delay in seconds between questions")

    args = parser.parse_args()
    asyncio.run(
        evaluate_benchmark(
            gold_set_path=args.gold_set,
            limit=args.limit,
            category_filter=args.category,
            output_path=args.output,
            delay=args.delay,
        )
    )


if __name__ == "__main__":
    main()
