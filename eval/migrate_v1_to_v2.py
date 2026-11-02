"""
eval/migrate_v1_to_v2.py

Migrates legacy v1 gold set (eval/gold_set.json) to v2 schema (eval/gold_set_v2.json).

Migration Specifications:
1. Keeps all 88 v1 rows.
2. Sets corpus_version "v1" and span_status "UNVERIFIED".
3. Sets answerability "not_answerable" for every row without expected_chunk_ids.
4. Rows with expected_chunk_ids are set to "answerable".
5. Does not create spans (required_evidence = [], acceptable_alternatives = []).
6. Does not guess topic or type (topic = "UNSET", type = "UNSET").
7. Marks GS-17, GS-18, GS-19, GS-20, GS-22, GS-23, GS-24 as "LABELED_AFTER_RESULTS".
8. Sets split from eval/split.json; moves any LABELED_AFTER_RESULTS question to "dev"
   to enforce Rule 4 ("A test question must not be BURNED").
9. Validates all 88 migrated rows using eval.schema.validate_dataset.
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from eval.schema import validate_dataset
EVAL_DIR = PROJECT_ROOT / "eval"
V1_GOLD_SET_PATH = EVAL_DIR / "gold_set.json"
V2_GOLD_SET_PATH = EVAL_DIR / "gold_set_v2.json"
SPLIT_PATH = EVAL_DIR / "split.json"

BURNED_QUESTION_IDS = {
    "GS-17",
    "GS-18",
    "GS-19",
    "GS-20",
    "GS-22",
    "GS-23",
    "GS-24",
}


def load_split_map() -> Dict[str, str]:
    """Load question_id -> split mapping from eval/split.json."""
    if not SPLIT_PATH.exists():
        return {}
    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    split_map: Dict[str, str] = {}
    for qid in data.get("dev_question_ids", []):
        split_map[qid] = "dev"
    for qid in data.get("test_question_ids", []):
        split_map[qid] = "test"
    return split_map


def update_split_json_remove_burned():
    """Ensure eval/split.json contains zero burned/post-hoc questions in test split."""
    if not SPLIT_PATH.exists():
        return
    with open(SPLIT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    test_ids = data.get("test_question_ids", [])
    dev_ids = data.get("dev_question_ids", [])

    moved = [qid for qid in test_ids if qid in BURNED_QUESTION_IDS]
    if moved:
        new_test = [qid for qid in test_ids if qid not in BURNED_QUESTION_IDS]
        new_dev = list(dict.fromkeys(dev_ids + moved))

        data["test_question_ids"] = new_test
        data["dev_question_ids"] = new_dev
        data["metadata"]["dev_count"] = len(new_dev)
        data["metadata"]["test_count"] = len(new_test)
        data["metadata"]["dev_labeled_count"] = len([q for q in new_dev if q in data.get("dev_labeled_question_ids", []) or q in moved])
        data["metadata"]["test_labeled_count"] = len([q for q in new_test if q in data.get("test_labeled_question_ids", []) and q not in moved])

        with open(SPLIT_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        print(f"Updated {SPLIT_PATH}: moved burned question(s) {moved} from test to dev split.")


def migrate_v1_to_v2(
    input_path: Path = V1_GOLD_SET_PATH,
    output_path: Path = V2_GOLD_SET_PATH,
) -> List[Dict[str, Any]]:
    """Migrate all 88 rows of v1 gold set to v2 schema."""
    with open(input_path, "r", encoding="utf-8") as f:
        v1_rows = json.load(f)

    update_split_json_remove_burned()
    split_map = load_split_map()

    v2_rows: List[Dict[str, Any]] = []

    for item in v1_rows:
        qid = item.get("id", "")
        expected_chunks = item.get("expected_chunk_ids", [])
        has_chunks = bool(expected_chunks and len(expected_chunks) > 0)

        # 3. Answerability: not_answerable for rows without expected_chunk_ids
        answerability = "answerable" if has_chunks else "not_answerable"

        # 7. Check post-hoc labeled questions
        is_labeled_after_results = qid in BURNED_QUESTION_IDS
        labeling_status = "LABELED_AFTER_RESULTS" if is_labeled_after_results else "CLEAN"

        # 8. Split: ensure test questions are never burned
        assigned_split = split_map.get(qid, "dev")
        if is_labeled_after_results and assigned_split == "test":
            assigned_split = "dev"

        # Provenance: dates reflect historical addition
        labeled_on = "2026-11-01" if is_labeled_after_results else "2026-10-30"

        # Judge criteria preserves original rubric & negative constraints
        judge_criteria = []
        if "expected_rubric" in item:
            judge_criteria.extend(item["expected_rubric"])
        if "negative_constraints" in item:
            judge_criteria.extend([f"Avoid: {c}" for c in item["negative_constraints"]])

        v2_item = {
            "id": qid,
            "topic": "UNSET",
            "type": "UNSET",
            "origin": {
                "kind": "owner",
                "url": "",
                "collected_on": "2026-10-24",
                "license": "proprietary",
            },
            "question": item.get("question", ""),
            "answerability": answerability,
            "required_evidence": [],  # Do not create spans
            "acceptable_alternatives": [],
            "must_include": [],
            "must_not_include": [],
            "judge_criteria": judge_criteria,
            "span_status": "UNVERIFIED",
            "labeled_by": "owner",
            "labeled_on": labeled_on,
            "corpus_version": "v1",
            "split": assigned_split,
            "labeling_status": labeling_status,
            "legacy_expected_chunk_ids": expected_chunks,
        }

        v2_rows.append(v2_item)

    # Validate all 88 rows against v2 schema rules
    print(f"Validating {len(v2_rows)} migrated rows against v2 schema...")
    validate_dataset(v2_rows)
    print(f"All {len(v2_rows)} migrated rows passed schema validation.")

    # Save to output file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(v2_rows, f, indent=2)

    print(f"Saved v2 gold set to {output_path}")
    return v2_rows


if __name__ == "__main__":
    migrate_v1_to_v2()
