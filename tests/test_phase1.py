import pytest
from pathlib import Path
from eval.split import create_split
from eval.bootstrap import bootstrap_ci, paired_bootstrap_difference
from eval.error_analysis import diagnose_miss
from app.rag import retrieve_relevant_chunks, load_full_corpus_chunks


def test_split_deterministic_reproducibility(tmp_path):
    """Verify that train/test split is strictly reproducible across runs with fixed seed."""
    split1 = create_split(split_path=tmp_path / "split1.json", seed=42)
    split2 = create_split(split_path=tmp_path / "split2.json", seed=42)
    assert split1["dev_question_ids"] == split2["dev_question_ids"]
    assert split1["test_question_ids"] == split2["test_question_ids"]
    assert split1["metadata"]["dev_count"] + split1["metadata"]["test_count"] == split1["metadata"]["total_questions"]


def test_bootstrap_ci_exact_bounds():
    """Verify that bootstrap confidence intervals compute proper means and monotonic bounds."""
    data = [1.0, 1.0, 0.0, 0.0]
    ci_res = bootstrap_ci(data, num_resamples=500, ci=0.95, seed=42)
    assert ci_res["mean"] == 0.50
    assert ci_res["n"] == 4
    assert ci_res["ci_lower"] <= ci_res["mean"] <= ci_res["ci_upper"]


def test_paired_bootstrap_difference():
    """Verify paired bootstrap difference computes mean diff, bounds, and inconclusive width."""
    # Narrow conclusive difference
    scores_a = [1.0] * 20 + [0.0] * 5
    scores_b = [0.8] * 20 + [0.0] * 5
    res = paired_bootstrap_difference(scores_a, scores_b, num_resamples=1000, seed=42)
    assert res["status"] == "CONCLUSIVE"
    assert res["mean_diff"] > 0
    assert not res["is_inconclusive"]

    # Wide interval > 30 points -> INCONCLUSIVE
    scores_wide_a = [1.0, 0.0, 1.0, 0.0]
    scores_wide_b = [0.0, 1.0, 0.0, 1.0]
    res_wide = paired_bootstrap_difference(scores_wide_a, scores_wide_b, num_resamples=1000, seed=42)
    assert res_wide["width"] > 0.30
    assert res_wide["status"] == "INCONCLUSIVE"
    assert res_wide["is_inconclusive"] is True


def test_error_analysis_assigned_cause_needs_human():
    """Verify automated token-overlap classifier is removed and every cause is NEEDS HUMAN."""
    mock_corpus = {
        "chunk_1": {"chunk_id": "chunk_1", "text": "FastAPI CORS allow_origins configuration middleware"}
    }

    diag = diagnose_miss("How to cook pasta?", ["chunk_999"], [], mock_corpus)
    assert diag["cause"] == "NEEDS HUMAN"

    diag_label = diagnose_miss("Database deadlocks in PostgreSQL transactions", ["chunk_1"], [], mock_corpus)
    assert diag_label["cause"] == "NEEDS HUMAN"

    diag_ret = diagnose_miss("FastAPI CORS origins setup", ["chunk_1"], ["chunk_2"], mock_corpus)
    assert diag_ret["cause"] == "NEEDS HUMAN"


def test_retrieval_modes_none_and_vanilla():
    """Verify retrieval modes 'none' and 'vanilla' return empty chunks."""
    assert retrieve_relevant_chunks("FastAPI CORS", search_mode="none") == []
    assert retrieve_relevant_chunks("FastAPI CORS", search_mode="vanilla") == []


def test_retrieval_mode_full_context():
    """Verify retrieval mode 'full-context' returns all processed chunks."""
    all_chunks = retrieve_relevant_chunks("FastAPI CORS", search_mode="full-context")
    assert len(all_chunks) >= 60
    assert any("fastapi" in c.get("chunk_id", "") for c in all_chunks)
