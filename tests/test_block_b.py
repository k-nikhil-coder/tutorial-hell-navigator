import sys
import json
import pytest
import subprocess
from pathlib import Path

from eval.bootstrap import paired_bootstrap_difference, bootstrap_ci
from eval.schema import GoldStandardQuestionV2, EvidenceItem, Origin, validate_question
from scripts.spans_to_chunks import (
    find_chunks_covering_span,
    map_spans_to_chunk_ids,
    get_chunks_for_size,
)
from eval.make_grading_sheet import create_grading_sheet

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def test_b1_paired_bootstrap_30_point_inconclusive():
    """B1: Paired bootstrap 1000 resamples seed 42. If 95% interval > 30 points, status is INCONCLUSIVE."""
    # Data with large per-question variance leading to CI width > 0.30
    mode_a = [1.0, 0.0, 1.0, 0.0, 1.0, 0.0]
    mode_b = [0.0, 1.0, 0.0, 1.0, 0.0, 1.0]

    res = paired_bootstrap_difference(mode_a, mode_b, num_resamples=1000, seed=42, max_width_points=30.0)
    assert res["is_wider_than_30_points"] is True
    assert res["status"] == "INCONCLUSIVE"
    assert res["is_inconclusive"] is True
    assert res["width"] > 0.30

    # Data with consistent small difference (width <= 0.30)
    mode_c = [0.8, 0.85, 0.8, 0.85, 0.8, 0.85] * 4
    mode_d = [0.75, 0.8, 0.75, 0.8, 0.75, 0.8] * 4
    res_conclusive = paired_bootstrap_difference(mode_c, mode_d, num_resamples=1000, seed=42)
    assert res_conclusive["status"] == "CONCLUSIVE"
    assert res_conclusive["width"] <= 0.30
    assert not res_conclusive["is_inconclusive"]


def test_b2_no_recall_for_none_and_full_context(tmp_path):
    """B2: Modes 'none' and 'full-context' must not compute Recall@K and compare on correctness only."""
    import asyncio
    from eval.run_eval import evaluate_benchmark

    out_file = tmp_path / "test_report_none.json"

    # Run limit 2 on 'none' mode in retrieval_only
    asyncio.run(
        evaluate_benchmark(
            limit=2,
            output_path=str(out_file),
            search_mode="none",
            retrieval_only=True,
            delay=0,
        )
    )

    with open(out_file, "r", encoding="utf-8") as f:
        rep = json.load(f)

    # Recall metrics must be None / omitted
    rm = rep["retrieval_metrics"]
    assert rm["recall_at_3"] is None
    assert rm["recall_at_5"] is None
    assert rm["evidence_coverage_at_3"] is None
    assert rep["ground_truth_count"] == 0


def test_b3_report_metrics_latency_ttft_prompt_tokens(tmp_path):
    """B3: Report includes mean latency, time to first token (p95), and mean prompt tokens."""
    import asyncio
    from eval.run_eval import evaluate_benchmark

    out_file = tmp_path / "test_report_metrics.json"

    asyncio.run(
        evaluate_benchmark(
            limit=3,
            output_path=str(out_file),
            search_mode="dense",
            retrieval_only=True,
            delay=0,
        )
    )

    with open(out_file, "r", encoding="utf-8") as f:
        rep = json.load(f)

    # Check top-level keys
    assert "mean_latency" in rep
    assert "time_to_first_token_p95" in rep
    assert "mean_prompt_tokens" in rep

    # Check latency_metrics subdict
    lm = rep["latency_metrics"]
    assert "mean_latency_ms" in lm
    assert "time_to_first_token_p95_ms" in lm
    assert "mean_prompt_tokens" in lm
    assert lm["mean_prompt_tokens"] > 0


def test_b4_schema_answer_spans_and_alternatives():
    """B4: Label format has answer_spans, acceptable_alternatives, and span_status."""
    q_data = {
        "id": "TEST-B4-01",
        "topic": "FastAPI",
        "type": "exact_syntax",
        "origin": {
            "kind": "owner",
            "collected_on": "2026-11-02",
        },
        "question": "How do you configure CORS middleware in FastAPI?",
        "answerability": "answerable",
        "answer_spans": [
            {
                "source_file": "fastapi_cors.md",
                "span": "app.add_middleware(CORSMiddleware, allow_origins=origins)",
            }
        ],
        "acceptable_alternatives": [
            {
                "source_file": "fastapi_cors.md",
                "span": "allow_origins=['*']",
            }
        ],
        "span_status": "UNVERIFIED",
        "labeled_by": "auditor",
        "labeled_on": "2026-11-02",
        "corpus_version": "v2",
        "split": "dev",
        "labeling_status": "CLEAN",
    }

    validated = validate_question(q_data)
    assert len(validated.answer_spans) == 1
    assert len(validated.acceptable_alternatives) == 1
    assert validated.span_status == "UNVERIFIED"
    assert validated.answer_spans[0].source_file == "fastapi_cors.md"


def test_b5_spans_to_chunk_ids_arbitrary_sizes():
    """B5: Script makes chunk IDs from spans for any chunk size."""
    mock_chunks = [
        {
            "chunk_id": "doc1_chunk_0",
            "source_file": "doc1.md",
            "text": "The quick brown fox jumps over the lazy dog.",
        },
        {
            "chunk_id": "doc1_chunk_1",
            "source_file": "doc1.md",
            "text": "Python FastAPI enables rapid async REST API development.",
        },
    ]

    # Test span matching
    cids = find_chunks_covering_span("rapid async REST API", "doc1.md", mock_chunks)
    assert cids == ["doc1_chunk_1"]

    cids_missing = find_chunks_covering_span("Non-existent text", "doc1.md", mock_chunks)
    assert cids_missing == []


def test_b6_runner_refuses_test_split_without_final(tmp_path):
    """B6: Without --final, runner must refuse test split."""
    python_exe = sys.executable
    cmd = [
        python_exe,
        "eval/run_eval.py",
        "--split-set",
        "test",
        "-n",
        "1",
    ]

    proc = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    # Must exit non-zero and print error about --final
    assert proc.returncode != 0
    assert "final" in proc.stdout.lower() or "final" in proc.stderr.lower()


def test_b7_grading_sheet_blind_mode_hidden(tmp_path):
    """B7: Grading sheet hides mode names and key is saved in a separate file."""
    rep_1 = tmp_path / "rep1.json"
    rep_2 = tmp_path / "rep2.json"

    item_1 = {
        "id": "Q1",
        "question": "What is CORS?",
        "response": {"summary": "CORS explanation", "action_plan": []},
        "retrieved_chunk_ids": ["c1", "c2"],
    }
    rep_1.write_text(
        json.dumps({"search_mode": "secret_mode_alpha", "items": [item_1]}),
        encoding="utf-8",
    )
    rep_2.write_text(
        json.dumps({"search_mode": "secret_mode_beta", "items": [item_1]}),
        encoding="utf-8",
    )

    sheet_csv = tmp_path / "grading_sheet.csv"
    key_json = tmp_path / "grading_key.json"

    res = create_grading_sheet(
        report_paths=[rep_1, rep_2],
        sheet_output_path=sheet_csv,
        key_output_path=key_json,
        seed=42,
    )

    sheet_content = sheet_csv.read_text(encoding="utf-8")
    key_content = key_json.read_text(encoding="utf-8")

    # Mode names must NOT appear in the sheet CSV
    assert "secret_mode_alpha" not in sheet_content
    assert "secret_mode_beta" not in sheet_content

    # Key JSON MUST contain the secret modes
    assert "secret_mode_alpha" in key_content
    assert "secret_mode_beta" in key_content


def test_b6_runner_sha256_mismatch_stops(tmp_path):
    """B6: Runner must stop if test_ids.sha256 hash does not match."""
    import hashlib
    import asyncio
    from eval.run_eval import evaluate_benchmark

    fake_gold = tmp_path / "gold_set.json"
    fake_gold.write_text(json.dumps([{"id": "T1", "question": "test?"}]), encoding="utf-8")

    fake_split = tmp_path / "split.json"
    fake_split.write_text(json.dumps({
        "dev_question_ids": [],
        "test_question_ids": ["T1"],
    }), encoding="utf-8")

    # Write wrong sha256
    sha_file = tmp_path / "test_ids.sha256"
    sha_file.write_text("bad_hash_that_does_not_match\n", encoding="utf-8")

    with pytest.raises(SystemExit, match="test_ids.sha256 mismatch"):
        asyncio.run(
            evaluate_benchmark(
                gold_set_path=fake_gold,
                search_mode="none",
                retrieval_only=True,
                split_set="test",
                final=True,
            )
        )


def test_b6_runner_final_logging(tmp_path):
    """B6: Runner logs the date and git commit of each --final run."""
    import asyncio
    from eval.run_eval import evaluate_benchmark

    fake_gold = tmp_path / "gold_set.json"
    fake_gold.write_text(json.dumps([{"id": "T1", "question": "test?"}]), encoding="utf-8")

    fake_split = tmp_path / "split.json"
    fake_split.write_text(json.dumps({
        "dev_question_ids": [],
        "test_question_ids": ["T1"],
    }), encoding="utf-8")

    out_rep = tmp_path / "out.json"

    # Run with final=True
    asyncio.run(
        evaluate_benchmark(
            gold_set_path=fake_gold,
            search_mode="none",
            retrieval_only=True,
            split_set="test",
            final=True,
            output_path=str(out_rep),
        )
    )

    log_file = tmp_path / "final_runs.log"
    assert log_file.exists()
    log_content = log_file.read_text(encoding="utf-8")
    assert "FINAL RUN" in log_content
    assert "COMMIT:" in log_content
    assert "SHA256:" in log_content


def test_a5_split_voided_hygiene():
    """A5: eval/split.json must void old test split with test_count=0."""
    split_file = PROJECT_ROOT / "eval" / "split.json"
    assert split_file.exists()
    with open(split_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    meta = data.get("metadata", {})
    assert meta.get("test_count") == 0
    assert len(data.get("test_question_ids", [])) == 0
    assert meta.get("status") == "VOID_OLD_TEST_SPLIT"


def test_a6_legacy_reports_marking():
    """A6: All eval/*_report.json files must be marked LEGACY: corpus v1."""
    import glob
    eval_dir = PROJECT_ROOT / "eval"
    report_files = list(eval_dir.glob("*_report.json"))
    assert len(report_files) >= 7

    for rf in report_files:
        with open(rf, "r", encoding="utf-8") as f:
            data = json.load(f)
        assert data.get("status") == "LEGACY: corpus v1" or data.get("corpus_version") == "LEGACY: corpus v1"

