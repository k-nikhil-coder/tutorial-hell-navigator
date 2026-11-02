"""
eval/make_grading_sheet.py

Generates a blind grading sheet for human or LLM-as-a-judge evaluation:
1. Gathers system responses across multiple mode evaluation reports.
2. Shuffles the system outputs deterministically (seed 42) for each question.
3. Hides the mode name entirely from the grading sheet, using anonymized aliases (e.g. System-A, System-B).
4. Saves the blind grading sheet to eval/grading_sheet.csv.
5. Saves the true mode decryption key to a separate file: eval/grading_key.json.
"""

import sys
import csv
import json
import random
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
DEFAULT_SHEET_PATH = EVAL_DIR / "grading_sheet.csv"
DEFAULT_KEY_PATH = EVAL_DIR / "grading_key.json"


def format_action_plan_for_sheet(action_plan: List[Dict[str, Any]]) -> str:
    """Format step-by-step action plan into a readable string."""
    if not action_plan:
        return ""
    formatted_steps = []
    for idx, step in enumerate(action_plan, 1):
        title = step.get("title", f"Step {idx}")
        cmd = step.get("command", "")
        expl = step.get("explanation", "")
        parts = [f"{idx}. {title}"]
        if cmd:
            parts.append(f"   Command: {cmd}")
        if expl:
            parts.append(f"   Details: {expl}")
        formatted_steps.append("\n".join(parts))
    return "\n\n".join(formatted_steps)


def create_grading_sheet(
    report_paths: List[Path],
    sheet_output_path: Path = DEFAULT_SHEET_PATH,
    key_output_path: Path = DEFAULT_KEY_PATH,
    seed: int = 42,
) -> Dict[str, Any]:
    """
    Generate blind grading sheet CSV and separate key JSON from evaluation reports.
    """
    loaded_reports: List[Dict[str, Any]] = []
    for p in report_paths:
        if not p.exists():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                rep = json.load(f)
                loaded_reports.append({
                    "path": str(p),
                    "filename": p.name,
                    "mode": rep.get("search_mode", p.stem),
                    "items": {it.get("id"): it for it in rep.get("items", []) if it.get("id")},
                })
        except Exception as e:
            print(f"Warning: could not load report {p}: {e}")

    if not loaded_reports:
        raise ValueError("No valid evaluation reports provided.")

    # Find union of all question IDs
    all_qids = []
    for r in loaded_reports:
        for qid in r["items"].keys():
            if qid not in all_qids:
                all_qids.append(qid)

    rng = random.Random(seed)

    sheet_rows: List[Dict[str, Any]] = []
    key_records: List[Dict[str, Any]] = []

    system_labels = ["System-A", "System-B", "System-C", "System-D", "System-E", "System-F"]

    for qid in all_qids:
        # Collect available candidate outputs for this question
        candidates = []
        for rep in loaded_reports:
            if qid in rep["items"]:
                candidates.append({
                    "mode": rep["mode"],
                    "filename": rep["filename"],
                    "item": rep["items"][qid],
                })

        # Shuffle candidates deterministically for this question
        shuffled = list(candidates)
        rng.shuffle(shuffled)

        for idx, cand in enumerate(shuffled):
            alias = system_labels[idx] if idx < len(system_labels) else f"System-{idx+1}"
            it = cand["item"]
            resp = it.get("response", {})
            summary = resp.get("summary", "") if isinstance(resp, dict) else ""
            action_plan = resp.get("action_plan", []) if isinstance(resp, dict) else []
            plan_str = format_action_plan_for_sheet(action_plan)

            citations = resp.get("cited_chunk_ids", []) if isinstance(resp, dict) else []
            if not citations and it.get("retrieved_chunk_ids"):
                citations = it.get("retrieved_chunk_ids", [])[:3]

            q_text = it.get("question", "")

            # Add row to blind sheet (NO mode name)
            sheet_rows.append({
                "question_id": qid,
                "question": q_text,
                "system_id": alias,
                "response_summary": summary,
                "action_plan": plan_str,
                "citations": ", ".join(citations) if isinstance(citations, list) else str(citations),
                "grade": "",
                "notes": "",
            })

            # Add entry to separate key
            key_records.append({
                "question_id": qid,
                "system_id": alias,
                "true_mode": cand["mode"],
                "source_report": cand["filename"],
            })

    # Write CSV blind grading sheet
    sheet_output_path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "question_id",
        "question",
        "system_id",
        "response_summary",
        "action_plan",
        "citations",
        "grade",
        "notes",
    ]
    with open(sheet_output_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(sheet_rows)

    # Write separate JSON key file
    key_output_path.parent.mkdir(parents=True, exist_ok=True)
    key_data = {
        "metadata": {
            "created_at": datetime.now(timezone.utc).isoformat(),
            "random_seed": seed,
            "total_questions": len(all_qids),
            "total_evaluations": len(sheet_rows),
            "reports_evaluated": [r["filename"] for r in loaded_reports],
        },
        "key": key_records,
    }
    with open(key_output_path, "w", encoding="utf-8") as f:
        json.dump(key_data, f, indent=2)

    return {
        "sheet_path": str(sheet_output_path),
        "key_path": str(key_output_path),
        "questions_count": len(all_qids),
        "evaluations_count": len(sheet_rows),
    }


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Generate blind grading sheet with shuffled outputs and hidden mode names")
    parser.add_argument(
        "--reports",
        nargs="+",
        default=[
            str(EVAL_DIR / "hybrid_rerank_retrieval_report.json"),
            str(EVAL_DIR / "hybrid_retrieval_report.json"),
            str(EVAL_DIR / "dense_retrieval_report.json"),
        ],
        help="List of evaluation report JSON paths to blind-grade",
    )
    parser.add_argument("--sheet-out", default=str(DEFAULT_SHEET_PATH), help="Path for output blind CSV grading sheet")
    parser.add_argument("--key-out", default=str(DEFAULT_KEY_PATH), help="Path for output separate JSON key file")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for shuffling (default: 42)")
    args = parser.parse_args()

    report_paths = [Path(p) for p in args.reports]
    res = create_grading_sheet(
        report_paths=report_paths,
        sheet_output_path=Path(args.sheet_out),
        key_output_path=Path(args.key_out),
        seed=args.seed,
    )

    print("=" * 80)
    print("📝 BLIND GRADING SHEET CREATED")
    print(f"  • Total questions:   {res['questions_count']}")
    print(f"  • Total rows:        {res['evaluations_count']}")
    print(f"  • Grading sheet CSV: {res['sheet_path']} (Mode names HIDDEN)")
    print(f"  • Decryption Key:    {res['key_path']} (Saved in SEPARATE file)")
    print("=" * 80)


if __name__ == "__main__":
    main()
