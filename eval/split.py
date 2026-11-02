import json
import random
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

EVAL_DIR = Path(__file__).resolve().parent
GOLD_SET_PATH = EVAL_DIR / "gold_set.json"
GOLD_SET_V2_PATH = EVAL_DIR / "gold_set_v2.json"
SPLIT_PATH = EVAL_DIR / "split.json"
RANDOM_SEED = 42
DEV_RATIO = 0.70

# 11 old test questions + 23 tuned questions (plus post-hoc) = 30 burned questions
BURNED_QUESTION_IDS: Set[str] = {
    "GS-01", "GS-02", "GS-03", "GS-04", "GS-05", "GS-06", "GS-07", "GS-08",
    "GS-09", "GS-10", "GS-11", "GS-12", "GS-13", "GS-14", "GS-15",
    "GS-17", "GS-18", "GS-19", "GS-20", "GS-22", "GS-23", "GS-24",
    "GS-81", "GS-82", "GS-83", "GS-84", "GS-85", "GS-86", "GS-87", "GS-88",
}


def rebuild_split_void_old_test(
    gold_set_path: Path = GOLD_SET_PATH,
    split_path: Path = SPLIT_PATH,
) -> Dict[str, Any]:
    """
    Rebuild eval/split.json with the old test split voided.
    All 11 old test questions and 23 tuned questions are moved to dev.
    """
    with open(gold_set_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    sorted_questions = sorted(questions, key=lambda q: q.get("id", ""))
    all_ids = [q["id"] for q in sorted_questions]
    all_labeled_ids = [
        q["id"] for q in sorted_questions
        if q.get("expected_chunk_ids") or q.get("legacy_expected_chunk_ids")
    ]

    split_data = {
        "metadata": {
            "status": "VOID_OLD_TEST_SPLIT",
            "note": "The old test split is void. All old test questions and tuned questions marked BURNED and moved to dev.",
            "random_seed": RANDOM_SEED,
            "total_questions": len(all_ids),
            "dev_count": len(all_ids),
            "test_count": 0,
            "total_labeled_questions": len(all_labeled_ids),
            "dev_labeled_count": len(all_labeled_ids),
            "test_labeled_count": 0,
            "burned_count": len(BURNED_QUESTION_IDS),
        },
        "dev_question_ids": all_ids,
        "test_question_ids": [],
        "dev_labeled_question_ids": all_labeled_ids,
        "test_labeled_question_ids": [],
    }

    with open(split_path, "w", encoding="utf-8") as f:
        json.dump(split_data, f, indent=2)

    return split_data


def create_split(
    gold_set_path: Path = GOLD_SET_PATH,
    split_path: Optional[Path] = None,
    seed: int = RANDOM_SEED,
    dev_ratio: float = DEV_RATIO,
) -> Dict[str, Any]:
    """
    Split questions into dev and test.
    Enforces Rule 4: BURNED questions must NEVER be placed in the test split.
    """
    with open(gold_set_path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    sorted_questions = sorted(questions, key=lambda q: q.get("id", ""))

    # Separate BURNED questions into dev pool
    burned_items = [q for q in sorted_questions if q.get("id") in BURNED_QUESTION_IDS or q.get("labeling_status") == "BURNED"]
    candidate_items = [q for q in sorted_questions if q not in burned_items]

    rng = random.Random(seed)
    shuffled_indices = list(range(len(candidate_items)))
    rng.shuffle(shuffled_indices)

    dev_count = int(round(len(candidate_items) * dev_ratio))
    dev_idx = set(shuffled_indices[:dev_count])
    test_idx = set(shuffled_indices[dev_count:])

    dev_items = burned_items + [candidate_items[i] for i in sorted(dev_idx)]
    test_items = [candidate_items[i] for i in sorted(test_idx)]

    dev_ids = [q["id"] for q in dev_items]
    test_ids = [q["id"] for q in test_items]

    dev_labeled_ids = [
        q["id"] for q in dev_items if q.get("expected_chunk_ids") or q.get("legacy_expected_chunk_ids")
    ]
    test_labeled_ids = [
        q["id"] for q in test_items if q.get("expected_chunk_ids") or q.get("legacy_expected_chunk_ids")
    ]

    split_data = {
        "metadata": {
            "random_seed": seed,
            "dev_ratio": dev_ratio,
            "test_ratio": round(1.0 - dev_ratio, 2),
            "total_questions": len(sorted_questions),
            "dev_count": len(dev_ids),
            "test_count": len(test_ids),
            "total_labeled_questions": len(dev_labeled_ids) + len(test_labeled_ids),
            "dev_labeled_count": len(dev_labeled_ids),
            "test_labeled_count": len(test_labeled_ids),
            "burned_count": len(burned_items),
        },
        "dev_question_ids": dev_ids,
        "test_question_ids": test_ids,
        "dev_labeled_question_ids": dev_labeled_ids,
        "test_labeled_question_ids": test_labeled_ids,
    }

    if split_path is not None:
        with open(split_path, "w", encoding="utf-8") as f:
            json.dump(split_data, f, indent=2)

    return split_data


if __name__ == "__main__":
    split = rebuild_split_void_old_test()
    meta = split["metadata"]
    print("Rebuilt eval/split.json with old test split voided:")
    print(f"  Total questions: {meta['total_questions']}")
    print(f"  Dev questions:   {meta['dev_count']} ({meta['dev_labeled_count']} labeled, {meta['burned_count']} burned)")
    print(f"  Test questions:  {meta['test_count']}")
    print(f"  Saved to {SPLIT_PATH}")
