"""
eval/error_analysis.py

Performs error analysis on retrieval misses across the evaluation benchmark.
Automated token-overlap classification is removed; assigns 'NEEDS HUMAN' to every cause field.
Allowed causes for human review:
  - 'retrieval failure': The correct chunk exists in the corpus, but the retrieval model failed to rank it in top-K.
  - 'valid alternative': The model retrieved a chunk that answers the query just as well as the expected chunk.
  - 'wrong label': The ground-truth chunk ID does not contain the answer or is erroneous.
  - 'missing chunk': The corpus lacks documentation needed to answer the question.

Outputs are written to eval/error_analysis.json, eval/error_analysis.md, and eval/error_review_sheet.csv.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
PROCESSED_DIR = PROJECT_ROOT / "corpus" / "processed"
GOLD_SET_FILE = EVAL_DIR / "gold_set.json"


def load_corpus_chunk_map() -> Dict[str, Dict[str, Any]]:
    """Map chunk_id -> chunk dictionary across available processed chunks."""
    chunk_map: Dict[str, Dict[str, Any]] = {}
    if PROCESSED_DIR.exists():
        for p in PROCESSED_DIR.glob("chunks_*.json"):
            with open(p, "r", encoding="utf-8") as f:
                chunks = json.load(f)
            for c in chunks:
                cid = c.get("chunk_id")
                if cid and cid not in chunk_map:
                    chunk_map[cid] = c
    return chunk_map


def diagnose_miss(
    question: str,
    expected_chunk_ids: List[str],
    retrieved_chunk_ids: List[str],
    chunk_map: Dict[str, Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Diagnose the root cause of a retrieval miss.
    Automated token-overlap classification removed. Write 'NEEDS HUMAN' in every cause field.
    Allowed causes for human review: retrieval failure, valid alternative, wrong label, missing chunk.
    """
    return {
        "cause": "NEEDS HUMAN",
        "evidence": "Automated token-overlap classification removed. Awaiting human review."
    }


def make_error_review_sheet(
    missed_rows: List[Dict[str, Any]],
    chunk_map: Dict[str, Dict[str, Any]],
    output_csv: Path = EVAL_DIR / "error_review_sheet.csv",
) -> Path:
    """
    Generate eval/error_review_sheet.csv.
    Columns: id, question, expected_chunk_text, retrieved_chunk_1_text,
    retrieved_chunk_2_text, retrieved_chunk_3_text, expected_answers (empty),
    retrieved_answers (empty), cause (empty).
    Show full chunk text. Allowed causes: retrieval failure, valid alternative,
    wrong label, missing chunk.
    """
    import csv

    fieldnames = [
        "id",
        "question",
        "expected_chunk_text",
        "retrieved_chunk_1_text",
        "retrieved_chunk_2_text",
        "retrieved_chunk_3_text",
        "expected_answers",
        "retrieved_answers",
        "cause",
    ]

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    with open(output_csv, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for row in missed_rows:
            qid = row.get("question_id", row.get("id", ""))
            q_text = row.get("question", "")
            exp_ids = row.get("expected_chunk_ids", [])
            ret_ids = row.get("retrieved_chunk_ids", [])

            # Extract full text for expected chunks
            exp_texts = []
            for cid in exp_ids:
                if cid in chunk_map:
                    exp_texts.append(chunk_map[cid].get("text", ""))
                else:
                    exp_texts.append(f"[Chunk {cid} missing from corpus]")
            expected_chunk_text = "\n\n---\n\n".join(exp_texts)

            # Extract full text for top 3 retrieved chunks
            ret_1_text = chunk_map.get(ret_ids[0], {}).get("text", "") if len(ret_ids) > 0 else ""
            ret_2_text = chunk_map.get(ret_ids[1], {}).get("text", "") if len(ret_ids) > 1 else ""
            ret_3_text = chunk_map.get(ret_ids[2], {}).get("text", "") if len(ret_ids) > 2 else ""

            writer.writerow({
                "id": qid,
                "question": q_text,
                "expected_chunk_text": expected_chunk_text,
                "retrieved_chunk_1_text": ret_1_text,
                "retrieved_chunk_2_text": ret_2_text,
                "retrieved_chunk_3_text": ret_3_text,
                "expected_answers": "",
                "retrieved_answers": "",
                "cause": "",
            })

    return output_csv


def perform_error_analysis(
    report_path: Path,
    output_json: Path = EVAL_DIR / "error_analysis.json",
    output_md: Path = EVAL_DIR / "error_analysis.md",
    output_csv: Path = EVAL_DIR / "error_review_sheet.csv",
    k: int = 3,
) -> Dict[str, Any]:
    """Run error analysis on an evaluation report and generate structured findings."""
    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    chunk_map = load_corpus_chunk_map()
    items = report.get("items", [])
    
    missed_rows: List[Dict[str, Any]] = []
    cause_counts = {"NEEDS HUMAN": 0}

    for item in items:
        expected = item.get("expected_chunk_ids", [])
        if not expected:
            # Check nested retrieval metrics if present
            rm = item.get("retrieval_metrics", {})
            if not rm.get("has_ground_truth"):
                continue

        retrieved = item.get("retrieved_chunk_ids", [])
        # Check if ground truth was hit in top K
        hit = any(cid in set(expected) for cid in retrieved[:k])

        if not hit:
            qid = item.get("id", "UNKNOWN")
            q_text = item.get("question", "")
            diagnosis = diagnose_miss(q_text, expected, retrieved, chunk_map)
            cause = diagnosis["cause"]
            cause_counts[cause] = cause_counts.get(cause, 0) + 1

            missed_rows.append({
                "question_id": qid,
                "question": q_text,
                "expected_chunk_ids": expected,
                "retrieved_chunk_ids": retrieved[:k],
                "cause": cause,
                "assigned_cause": cause,
                "evidence_notes": diagnosis["evidence"],
                "human_confirmed": "BLOCKED: HUMAN",
            })

    summary = {
        "report_evaluated": str(report_path),
        "top_k_threshold": k,
        "total_missed_questions": len(missed_rows),
        "cause_breakdown": cause_counts,
        "missed_questions": missed_rows,
    }

    # Save JSON report
    output_json.parent.mkdir(parents=True, exist_ok=True)
    with open(output_json, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    # Save CSV review sheet
    make_error_review_sheet(missed_rows, chunk_map, output_csv=output_csv)

    # Save Markdown table
    cause_breakdown_lines = [f"- **{k_name}:** {count}" for k_name, count in cause_counts.items()]
    md_lines = [
        "# Retrieval Error Analysis Report",
        "",
        f"**Source Report:** `{report_path.name}`  ",
        f"**Top-K Evaluated:** $K={k}$  ",
        f"**Total Misses:** {len(missed_rows)}  ",
        "",
        "## Cause Breakdown",
        "",
    ] + cause_breakdown_lines + [
        "",
        "## Detailed Error Log",
        "",
        "| Question ID | Question | Expected Chunk(s) | Retrieved Top Chunks | Assigned Cause | Evidence Notes | Human Confirmed |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ]

    for row in missed_rows:
        exp_str = ", ".join(row["expected_chunk_ids"])
        ret_str = ", ".join(row["retrieved_chunk_ids"])
        q_trunc = row["question"].replace("|", "\\|")[:60]
        ev_trunc = row["evidence_notes"].replace("|", "\\|")[:70]
        md_lines.append(
            f"| **{row['question_id']}** | {q_trunc} | `{exp_str}` | `{ret_str}` | **{row['assigned_cause']}** | {ev_trunc} | `{row['human_confirmed']}` |"
        )

    with open(output_md, "w", encoding="utf-8") as f:
        f.write("\n".join(md_lines) + "\n")

    return summary


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Analyze retrieval errors on an eval report")
    parser.add_argument("--report", default="eval/hybrid_rerank_retrieval_report.json", help="Path to evaluation report JSON")
    parser.add_argument("-k", type=int, default=3, help="Top-K cutoff for measuring misses (default: 3)")
    parser.add_argument("-o", "--output", default="eval/error_analysis.json", help="Path for JSON output")
    args = parser.parse_args()

    report_path = Path(args.report)
    if not report_path.exists():
        print(f"Error: Report file {report_path} not found.")
        sys.exit(1)

    res = perform_error_analysis(report_path=report_path, output_json=Path(args.output), k=args.k)
    print("=" * 75)
    print("RETRIEVAL ERROR ANALYSIS COMPLETED")
    print(f"  • Source report:     {res['report_evaluated']}")
    print(f"  • Total misses (K={res['top_k_threshold']}): {res['total_missed_questions']}")
    print(f"  • Cause breakdown:   {res['cause_breakdown']}")
    print("  • Human confirmation: BLOCKED: HUMAN (awaiting review)")
    print(f"  • Output JSON:       eval/error_analysis.json")
    print(f"  • Output Markdown:   eval/error_analysis.md")
    print("=" * 75)


if __name__ == "__main__":
    main()
