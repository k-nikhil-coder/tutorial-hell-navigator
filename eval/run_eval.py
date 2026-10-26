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

    # Check that at least one concrete command is provided
    commands = [step.command for step in response.action_plan if step.command]
    if not commands:
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

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "step_count": len(response.action_plan),
        "command_count": len(commands),
    }


async def evaluate_benchmark(
    gold_set_path: str = "eval/gold_set.json",
    limit: int = 5,
    category_filter: str = None,
    output_path: str = "eval/eval_report.json",
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

    batch = questions[:limit]
    print(f"Running evaluation on {len(batch)} questions (out of {len(questions)} total)...")
    print("-" * 60)

    results = []
    passed = 0

    for idx, item in enumerate(batch, 1):
        qid = item.get("id", f"Q{idx}")
        category = item.get("category", "General")
        prompt = item.get("question", "")
        rubric = item.get("expected_rubric", [])
        negatives = item.get("negative_constraints", [])

        print(f"[{idx}/{len(batch)}] {qid} ({category[:25]}):", end=" ", flush=True)

        try:
            model_resp = await generate_structured_response_async(prompt)
            result = score_response(model_resp, rubric, negatives)

            if result["passed"]:
                passed += 1
                print(f"PASS ({result['step_count']} steps, {result['command_count']} commands)")
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

    pass_rate = (passed / len(batch)) * 100 if batch else 0
    print("-" * 60)
    print(f"Summary: {passed}/{len(batch)} passed ({pass_rate:.1f}%)")

    report = {
        "total": len(batch),
        "passed": passed,
        "pass_rate": pass_rate,
        "items": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {output_path}")


def main():
    parser = argparse.ArgumentParser(description="Gold Benchmark Evaluator")
    parser.add_argument("--gold-set", default="eval/gold_set.json", help="Path to gold set json")
    parser.add_argument("-n", "--limit", type=int, default=3, help="Number of questions to test")
    parser.add_argument("-c", "--category", default=None, help="Filter by category substring")
    parser.add_argument("-o", "--output", default="eval/eval_report.json", help="Report output json path")

    args = parser.parse_args()
    asyncio.run(
        evaluate_benchmark(
            gold_set_path=args.gold_set,
            limit=args.limit,
            category_filter=args.category,
            output_path=args.output,
        )
    )


if __name__ == "__main__":
    main()
