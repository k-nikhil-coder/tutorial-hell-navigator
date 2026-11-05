"""
tests/test_schema_v2.py

Unit tests verifying:
1. All five validator rules in eval/schema.py.
2. Integrity of migrated v2 gold set (eval/gold_set_v2.json).
3. Retrieval metrics: Evidence coverage@K, Hit@K, and MRR.
"""

import sys
import json
import pytest
from pathlib import Path
from eval.schema import (
    GoldStandardQuestionV2,
    EvidenceItem,
    Origin,
    validate_question,
    validate_dataset,
)
from eval.run_eval import calculate_retrieval_metrics

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "corpus" / "raw"
V2_GOLD_SET_PATH = PROJECT_ROOT / "eval" / "gold_set_v2.json"


def test_rule_1_not_answerable_must_have_empty_evidence():
    """Rule 1: not_answerable questions have empty evidence."""
    bad_q = {
        "id": "TEST-01",
        "topic": "FastAPI",
        "type": "conceptual",
        "origin": {"kind": "student", "url": "", "collected_on": "2026-11-02"},
        "question": "What is life?",
        "answerability": "not_answerable",
        "required_evidence": [{"source_file": "fastapi_cors.md", "span": "some text"}],
        "acceptable_alternatives": [],
        "labeled_by": "owner",
        "labeled_on": "2026-11-02",
        "corpus_version": "v2",
        "split": "dev",
    }
    with pytest.raises(ValueError, match="Rule 1 Violation: not_answerable questions must have empty evidence"):
        validate_question(bad_q)


def test_rule_2_answerable_must_have_required_span_in_v2():
    """Rule 2: answerable questions in v2 have at least one required span."""
    bad_q = {
        "id": "TEST-02",
        "topic": "FastAPI",
        "type": "conceptual",
        "origin": {"kind": "student", "url": "", "collected_on": "2026-11-02"},
        "question": "How to configure CORS?",
        "answerability": "answerable",
        "required_evidence": [],  # Empty required evidence in v2
        "acceptable_alternatives": [],
        "labeled_by": "owner",
        "labeled_on": "2026-11-02",
        "corpus_version": "v2",
        "split": "dev",
    }
    with pytest.raises(ValueError, match="Rule 2 Violation: answerable questions in corpus_version 'v2' must have at least one required span"):
        validate_question(bad_q)


def test_rule_3_verified_span_verbatim_check():
    """Rule 3: A VERIFIED span must appear verbatim in the named corpus file."""
    # Invalid span not in fastapi_cors.md
    bad_q = {
        "id": "TEST-03",
        "topic": "FastAPI",
        "type": "exact_syntax",
        "origin": {"kind": "owner", "url": "", "collected_on": "2026-11-02"},
        "question": "How to allow CORS origins?",
        "answerability": "answerable",
        "required_evidence": [
            {"source_file": "fastapi_cors.md", "span": "THIS TEXT DEFINITELY DOES NOT EXIST IN FASTAPI CORS MD 12345"}
        ],
        "acceptable_alternatives": [],
        "span_status": "VERIFIED",
        "labeled_by": "owner",
        "labeled_on": "2026-11-02",
        "corpus_version": "v2",
        "split": "dev",
    }
    with pytest.raises(ValueError, match="Rule 3 Violation: VERIFIED span does not appear verbatim"):
        validate_question(bad_q, corpus_raw_dir=RAW_DIR)

    # Valid span known to be verbatim in fastapi_cors.md
    valid_q = dict(bad_q)
    valid_q["required_evidence"] = [
        {"source_file": "fastapi_cors.md", "span": "You can configure it in your **FastAPI** application using the `CORSMiddleware`."}
    ]
    model = validate_question(valid_q, corpus_raw_dir=RAW_DIR)
    assert model.span_status == "VERIFIED"


def test_rule_4_test_question_cannot_be_burned():
    """Rule 4: A test question must not be BURNED (e.g. LABELED_AFTER_RESULTS)."""
    bad_q = {
        "id": "GS-18",
        "topic": "FastAPI",
        "type": "conceptual",
        "origin": {"kind": "owner", "url": "", "collected_on": "2026-11-02"},
        "question": "Debugging question",
        "answerability": "not_answerable",
        "required_evidence": [],
        "acceptable_alternatives": [],
        "labeled_by": "owner",
        "labeled_on": "2026-11-02",
        "corpus_version": "v2",
        "split": "test",  # in test split
        "labeling_status": "LABELED_AFTER_RESULTS",  # burned!
    }
    with pytest.raises(ValueError, match="Rule 4 Violation: A test question must not be BURNED"):
        validate_question(bad_q)


def test_rule_5_every_row_has_origin_labeled_by_labeled_on():
    """Rule 5: Every row has origin, labeled_by, and labeled_on."""
    # Missing labeled_by
    bad_q = {
        "id": "TEST-05",
        "topic": "FastAPI",
        "type": "conceptual",
        "origin": {"kind": "owner", "url": "", "collected_on": "2026-11-02"},
        "question": "Question text",
        "answerability": "not_answerable",
        "required_evidence": [],
        "acceptable_alternatives": [],
        "labeled_by": "",  # Empty
        "labeled_on": "2026-11-02",
        "corpus_version": "v2",
        "split": "dev",
    }
    with pytest.raises(ValueError, match="Rule 5 Violation"):
        validate_question(bad_q)


def test_migrated_v2_gold_set_passes_all_rules():
    """Verify that eval/gold_set_v2.json satisfies all row requirements."""
    assert V2_GOLD_SET_PATH.exists(), f"Migrated file {V2_GOLD_SET_PATH} not found."
    with open(V2_GOLD_SET_PATH, "r", encoding="utf-8") as f:
        rows = json.load(f)

    assert len(rows) == 392, f"Expected 392 rows, found {len(rows)}"
    
    # Run full validator
    validated = validate_dataset(rows, corpus_raw_dir=RAW_DIR)
    assert len(validated) == 392

    # Check answerability: 298 not_answerable, 94 answerable
    not_ans = [q for q in validated if q.answerability == "not_answerable"]
    ans = [q for q in validated if q.answerability == "answerable"]
    assert len(not_ans) == 298
    assert len(ans) == 94

    # Check labeling status: exactly 7 post-hoc labeled questions
    post_hoc = [q for q in validated if q.labeling_status == "LABELED_AFTER_RESULTS"]
    post_hoc_ids = {q.id for q in post_hoc}
    expected_post_hoc = {"GS-17", "GS-18", "GS-19", "GS-20", "GS-22", "GS-23", "GS-24"}
    assert post_hoc_ids == expected_post_hoc

    # Check test split hygiene: zero burned/post-hoc questions in test split
    test_burned = [q for q in validated if q.split == "test" and q.labeling_status != "CLEAN"]
    assert len(test_burned) == 0


def test_retrieval_metrics_evidence_coverage_and_hit():
    """Verify Coverage@K, Hit@K, and MRR on span-based evidence."""
    retrieved = [
        {"rank": 1, "chunk_id": "c1", "text": "To configure CORS, use CORSMiddleware from fastapi.middleware.cors"},
        {"rank": 2, "chunk_id": "c2", "text": "Set allow_origins with explicit client domains"},
        {"rank": 3, "chunk_id": "c3", "text": "Do not use wildcard allow_origins=['*'] with allow_credentials=True"},
    ]

    # Question with 2 required evidence items
    req_ev = [
        {"source_file": "fastapi_cors.md", "span": "CORSMiddleware"},
        {"source_file": "fastapi_cors.md", "span": "wildcard allow_origins=['*'] with allow_credentials=True"},
    ]

    # Top-1 retrieved covers item 1 only -> Coverage@1=0.5, Hit@1=1.0, MRR=1.0
    m_top1 = calculate_retrieval_metrics(retrieved[:1], required_evidence=req_ev)
    assert m_top1["evidence_coverage_at_3"] == 0.5
    assert m_top1["hit_at_3"] == 1.0
    assert m_top1["reciprocal_rank"] == 1.0

    # Top-3 retrieved covers both items -> Coverage@3=1.0, Hit@3=1.0, MRR=1.0
    m_top3 = calculate_retrieval_metrics(retrieved, required_evidence=req_ev)
    assert m_top3["evidence_coverage_at_3"] == 1.0
    assert m_top3["hit_at_3"] == 1.0
    assert m_top3["reciprocal_rank"] == 1.0


def test_retrieval_metrics_acceptable_alternatives():
    """Verify that acceptable alternatives count as covered."""
    retrieved = [
        {"rank": 1, "chunk_id": "c1", "text": "Alternative text: origins = ['http://localhost:3000']"}
    ]

    req_ev = [{"source_file": "fastapi_cors.md", "span": "allow_origins=['http://localhost:3000']"}]
    alt_ev = [{"source_file": "fastapi_cors.md", "span": "origins = ['http://localhost:3000']"}]

    metrics = calculate_retrieval_metrics(
        retrieved,
        required_evidence=req_ev,
        acceptable_alternatives=alt_ev,
    )
    assert metrics["evidence_coverage_at_3"] == 1.0
    assert metrics["hit_at_3"] == 1.0
    assert metrics["reciprocal_rank"] == 1.0


def test_day_43_gold_benchmark_v2_integrity():
    """Verify Day 43 expanded multi-author benchmark (eval/gold_benchmark_v2.json)."""
    import hashlib
    benchmark_path = PROJECT_ROOT / "eval" / "gold_benchmark_v2.json"
    split_path = PROJECT_ROOT / "eval" / "split_v2.json"
    sha_path = PROJECT_ROOT / "eval" / "test_ids.sha256"

    assert benchmark_path.exists(), "gold_benchmark_v2.json not found"
    assert split_path.exists(), "split_v2.json not found"
    assert sha_path.exists(), "test_ids.sha256 not found"

    with open(benchmark_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 1. Size requirement: 60+ questions (65 built)
    assert len(data) >= 60, f"Expected at least 60 questions, found {len(data)}"

    # 2. Validate all 5 schema rules
    validated = validate_dataset(data, corpus_raw_dir=RAW_DIR)
    assert len(validated) == len(data)

    # 3. Multi-author provenance: no single contributor accounts for > 20%
    author_counts = {}
    for q in validated:
        author_counts[q.labeled_by] = author_counts.get(q.labeled_by, 0) + 1
    max_share = max(author_counts.values()) / len(validated)
    assert max_share <= 0.20, f"Max author share {max_share:.2%} exceeds 20% limit"
    assert len(author_counts) >= 6, "Expected at least 6 distinct contributors"

    # Verify real friend contributors and author/owner curator
    expected_friends = {"Haadi", "Rohan", "Yeshwanth", "swamy", "Ravi", "Imam"}
    assert expected_friends.issubset(set(author_counts.keys())), f"Missing friend contributors: {expected_friends - set(author_counts.keys())}"
    assert "Kumbham Nikhil" in author_counts, "Expected project author Kumbham Nikhil as owner/curator"

    # 4. Out-of-scope refusal questions have strictly empty evidence (Rule 1)
    refusals = [q for q in validated if q.answerability == "not_answerable"]
    assert len(refusals) >= 15, "Expected at least 15 refusal control questions"
    for r in refusals:
        assert len(r.answer_spans) == 0
        assert len(r.acceptable_alternatives) == 0

    # 5. In-scope answerable questions have verified verbatim spans (Rules 2 & 3)
    answerable = [q for q in validated if q.answerability == "answerable"]
    assert len(answerable) >= 40, "Expected at least 40 answerable questions"
    for a in answerable:
        assert len(a.answer_spans) >= 1
        assert a.span_status == "VERIFIED"

    # 6. Test split hygiene: SHA256 integrity and zero burned questions (Rule 4)
    with open(split_path, "r", encoding="utf-8") as f:
        split_meta = json.load(f)
    test_ids = split_meta.get("test_question_ids", [])
    dev_ids = split_meta.get("dev_question_ids", [])
    assert len(test_ids) >= 20, "Expected at least 20 held-out test questions"
    assert len(dev_ids) >= 35, "Expected at least 35 dev questions"

    # Verify complete and disjoint partition
    test_set = set(test_ids)
    dev_set = set(dev_ids)
    all_validated_ids = {q.id for q in validated}
    assert test_set.isdisjoint(dev_set), "Overlap detected between dev and test split IDs"
    assert (test_set | dev_set) == all_validated_ids, "Split partition does not match all benchmark question IDs"

    # Explicitly enforce Rule 4: zero burned questions in test split
    test_qs = [q for q in validated if q.split == "test"]
    assert len(test_qs) == len(test_ids)
    assert all(q.labeling_status == "CLEAN" for q in test_qs), "Test split contains burned or post-hoc questions"

    test_ids_sorted = sorted(test_ids)
    computed_sha = hashlib.sha256("\n".join(test_ids_sorted).encode("utf-8")).hexdigest()
    recorded_sha = sha_path.read_text(encoding="utf-8").strip()
    assert computed_sha == recorded_sha, "test_ids.sha256 mismatch with split_v2.json"


def test_gold_benchmark_v2_runner_test_split_refusal():
    """Verify eval/run_eval.py refuses evaluation on gold_benchmark_v2 test split without --final."""
    import subprocess
    cmd = [
        sys.executable,
        "eval/run_eval.py",
        "--gold-set",
        "eval/gold_benchmark_v2.json",
        "--split-set",
        "test",
        "-n",
        "1",
    ]
    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    assert proc.returncode != 0
    assert "refused" in proc.stdout.lower() or "final" in proc.stdout.lower()


