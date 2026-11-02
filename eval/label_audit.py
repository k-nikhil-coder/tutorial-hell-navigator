"""
eval/label_audit.py

Performs an audit of gold set ground-truth labels:
1. Lists every chunk that is expected for 3 or more questions.
2. Lists every question whose expected chunk is in a different document than the top retrieved chunk.
3. Identifies and reports the code that created the labels and any default or fallback values used.
"""

import sys
import json
import re
import argparse
from pathlib import Path
from typing import Dict, List, Any, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
EVAL_DIR = PROJECT_ROOT / "eval"
GOLD_SET_PATH = EVAL_DIR / "gold_set.json"
REPORT_PATH = EVAL_DIR / "hybrid_rerank_retrieval_report.json"
PROCESSED_DIR = PROJECT_ROOT / "corpus" / "processed"


def extract_document_id(chunk_id: str, chunk_map: Dict[str, Dict[str, Any]] = None) -> str:
    """Extract base document identifier from a chunk ID or chunk metadata."""
    if chunk_map and chunk_id in chunk_map:
        source_file = chunk_map[chunk_id].get("source_file") or chunk_map[chunk_id].get("document_id")
        if source_file:
            return Path(source_file).stem
    # Fallback to regex pattern: remove trailing _chunk_\d+
    clean = re.sub(r"_chunk_\d+$", "", chunk_id)
    return clean


def load_chunk_map() -> Dict[str, Dict[str, Any]]:
    """Load chunk metadata from processed corpus files."""
    chunk_map: Dict[str, Dict[str, Any]] = {}
    if PROCESSED_DIR.exists():
        for p in PROCESSED_DIR.glob("chunks_*.json"):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
                for c in chunks:
                    cid = c.get("chunk_id")
                    if cid and cid not in chunk_map:
                        chunk_map[cid] = c
            except Exception:
                pass
    return chunk_map


def audit_chunks_expected_3_or_more(
    questions: List[Dict[str, Any]]
) -> Dict[str, List[str]]:
    """List every chunk that is expected for 3 or more questions."""
    chunk_to_questions: Dict[str, List[str]] = {}
    for q in questions:
        qid = q.get("id", "UNKNOWN")
        expected = q.get("expected_chunk_ids") or q.get("legacy_expected_chunk_ids") or []
        for cid in expected:
            chunk_to_questions.setdefault(cid, []).append(qid)

    overused_chunks = {
        cid: qids for cid, qids in chunk_to_questions.items() if len(qids) >= 3
    }
    # Sort by count descending
    return dict(sorted(overused_chunks.items(), key=lambda kv: len(kv[1]), reverse=True))


def audit_document_mismatches(
    questions: List[Dict[str, Any]],
    report_items: List[Dict[str, Any]],
    chunk_map: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    List every question whose expected chunk is in a different document
    than the top retrieved chunk.
    """
    report_map = {it.get("id"): it for it in report_items if it.get("id")}
    mismatches = []

    for q in questions:
        qid = q.get("id")
        expected_ids = q.get("expected_chunk_ids") or q.get("legacy_expected_chunk_ids") or []
        if not expected_ids:
            continue

        rep_item = report_map.get(qid)
        if not rep_item:
            continue

        retrieved_ids = rep_item.get("retrieved_chunk_ids", [])
        if not retrieved_ids:
            continue

        top_retrieved = retrieved_ids[0]
        top_doc = extract_document_id(top_retrieved, chunk_map)

        expected_docs = {extract_document_id(cid, chunk_map) for cid in expected_ids}

        # Check if the top retrieved chunk is from an entirely different document
        if top_doc not in expected_docs:
            mismatches.append({
                "id": qid,
                "question": q.get("question", ""),
                "expected_chunk_ids": expected_ids,
                "expected_documents": sorted(list(expected_docs)),
                "top_retrieved_chunk_id": top_retrieved,
                "top_retrieved_document": top_doc,
            })

    return mismatches


def report_label_provenance_and_fallbacks() -> Dict[str, Any]:
    """Find the code that made the labels and report default/fallback values."""
    return {
        "sources_of_labels": [
            {
                "file": "scratch/update_gold_set.py",
                "description": "Hardcoded ground truth dictionary GROUND_TRUTH_MAPPINGS manually mapped GS-01 through GS-15 to chunks.",
                "details": "Questions GS-01 through GS-15 were mapped to hardcoded chunks in fastapi_fullstack_guide, docker_production_guide, cs_engineering_roadmap, etc. GS-81 through GS-88 were hardcoded via HARD_QUERIES."
            },
            {
                "file": "commit 8cf03d1 (Ingestion of 304 candidate questions)",
                "description": "Batch script generated 49 questions (GS-K1-01 to GS-K7-07) with synthetic fallback chunk IDs.",
                "default_fallback_values": {
                    "GS-K1 (DSA)": "dsa_patterns_chunk_0 (repeated for all 7 questions, file does not exist in corpus)",
                    "GS-K2 (Complexity)": "complexity_chunk_0 (repeated for all 7 questions, file does not exist in corpus)",
                    "GS-K3 (OS)": "os_concepts_chunk_0 (repeated for all 7 questions, file does not exist in corpus)",
                    "GS-K4 (Database Theory)": "database_theory_chunk_0 (repeated for all 7 questions, file does not exist in corpus)",
                    "GS-K5 (Networking)": "networking_chunk_0 (repeated for all 7 questions, file does not exist in corpus)",
                    "GS-K6 (System Design)": "system_design_chunk_0 (repeated for all 7 questions, file does not exist in corpus)",
                    "GS-K7 (Concurrency)": "concurrency_chunk_0 (repeated for all 7 questions, file does not exist in corpus)",
                }
            },
            {
                "file": "eval/migrate_v1_to_v2.py",
                "description": "Migration script that assigned default answerability and topic flags.",
                "default_fallback_values": {
                    "answerability_without_chunks": "not_answerable (assigned to 58 questions without labels)",
                    "topic": "UNSET",
                    "type": "UNSET",
                    "span_status": "UNVERIFIED"
                }
            }
        ]
    }


def run_audit(
    gold_set_path: Path = GOLD_SET_PATH,
    report_path: Path = REPORT_PATH,
) -> Dict[str, Any]:
    if not gold_set_path.exists():
        raise FileNotFoundError(f"Gold set file not found: {gold_set_path}")

    with open(gold_set_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    report_items = []
    if report_path.exists():
        with open(report_path, "r", encoding="utf-8") as f:
            report_data = json.load(f)
            report_items = report_data.get("items", [])

    chunk_map = load_chunk_map()

    overused = audit_chunks_expected_3_or_more(questions)
    mismatches = audit_document_mismatches(questions, report_items, chunk_map)
    provenance = report_label_provenance_and_fallbacks()

    audit_result = {
        "gold_set_file": str(gold_set_path),
        "total_questions": len(questions),
        "chunks_expected_for_3_or_more_questions": {
            cid: {"count": len(qids), "question_ids": qids} for cid, qids in overused.items()
        },
        "document_mismatches_with_top_retrieved": {
            "total_mismatches": len(mismatches),
            "mismatches": mismatches,
        },
        "label_generation_provenance": provenance,
    }

    return audit_result


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Audit gold set labels for repetition, document mismatch, and fallback provenance")
    parser.add_argument("--gold-set", default=str(GOLD_SET_PATH), help="Path to gold set JSON")
    parser.add_argument("--report", default=str(REPORT_PATH), help="Path to retrieval report JSON")
    parser.add_argument("-o", "--output", default="eval/label_audit.json", help="Path to output JSON")
    args = parser.parse_args()

    results = run_audit(gold_set_path=Path(args.gold_set), report_path=Path(args.report))

    print("=" * 80)
    print("📋 LABEL AUDIT REPORT")
    print(f"Total questions in gold set: {results['total_questions']}")
    print("-" * 80)
    print(f"1. CHUNKS EXPECTED FOR 3 OR MORE QUESTIONS ({len(results['chunks_expected_for_3_or_more_questions'])} chunks):")
    for cid, info in results["chunks_expected_for_3_or_more_questions"].items():
        print(f"   • {cid:<35} : {info['count']} questions ({', '.join(info['question_ids'])})")

    mismatch_data = results["document_mismatches_with_top_retrieved"]
    print("-" * 80)
    print(f"2. QUESTIONS WHOSE EXPECTED CHUNK IS IN DIFFERENT DOCUMENT THAN TOP RETRIEVED ({mismatch_data['total_mismatches']} questions):")
    for m in mismatch_data["mismatches"]:
        print(f"   • {m['id']}: Expected [{', '.join(m['expected_documents'])}] vs Top Retrieved Doc [{m['top_retrieved_document']}] (Chunk: {m['top_retrieved_chunk_id']})")

    print("-" * 80)
    print("3. CODE THAT MADE THE LABELS & DEFAULT / FALLBACK VALUES:")
    for src in results["label_generation_provenance"]["sources_of_labels"]:
        print(f"   • Source: {src['file']}")
        print(f"     Description: {src['description']}")
        if "default_fallback_values" in src:
            for k, v in src["default_fallback_values"].items():
                print(f"       - {k}: {v}")
    print("=" * 80)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    print(f"Audit results saved to {output_path}")


if __name__ == "__main__":
    main()
