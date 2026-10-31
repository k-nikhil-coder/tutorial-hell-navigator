import pytest
from pathlib import Path
from app.ingestion import (
    clean_text,
    extract_text_from_pdf,
    extract_text_from_file,
    process_documents,
    CORPUS_DIR,
    PROCESSED_DIR,
)
from benchmarks.chunk_eval import (
    load_chunks,
    extract_keywords,
    evaluate_chunk_hit_rate,
)


def test_clean_text_normalizes_artifacts():
    dirty = "Hello\xa0World\x00\n\n\n\nLine 2   "
    cleaned = clean_text(dirty)
    assert "\xa0" not in cleaned
    assert "\x00" not in cleaned
    assert "\n\n\n" not in cleaned
    assert cleaned.startswith("Hello World")
    assert cleaned.endswith("Line 2")


def test_extract_text_from_pdf():
    pdf_path = CORPUS_DIR / "cs_engineering_roadmap.pdf"
    if not pdf_path.exists():
        pytest.skip("Sample PDF not found in corpus/raw")
    text = extract_text_from_pdf(pdf_path)
    assert len(text) > 100
    assert "Tutorial Hell" in text


def test_extract_text_from_markdown():
    md_path = CORPUS_DIR / "fastapi_fullstack_guide.md"
    if not md_path.exists():
        pytest.skip("Sample Markdown not found in corpus/raw")
    text = extract_text_from_file(md_path)
    assert text is not None
    assert "FastAPI" in text
    assert "PostgreSQL" in text


def test_process_documents_creates_valid_chunks(tmp_path):
    chunks = process_documents(
        chunk_size=256,
        chunk_overlap=25,
        raw_dir=CORPUS_DIR,
        output_dir=tmp_path,
    )
    assert len(chunks) > 0

    first = chunks[0]
    assert "chunk_id" in first
    assert "source_file" in first
    assert "chunk_index" in first
    assert "text" in first
    assert "char_count" in first
    assert (tmp_path / "chunks_256.json").exists()


def test_load_chunks():
    chunks = load_chunks(512)
    assert isinstance(chunks, list)
    if chunks:
        assert "chunk_id" in chunks[0]
        assert "text" in chunks[0]


def test_extract_keywords():
    text = "How do I fix a CORS error in FastAPI when calling from React?"
    kws = extract_keywords(text)
    assert "fastapi" in kws
    assert "react" in kws
    assert "cors" in kws
    # Stop words or short words should be excluded
    assert "when" not in kws
    assert "how" not in kws


def test_evaluate_chunk_hit_rate():
    results = evaluate_chunk_hit_rate(sample_size=5, chunk_sizes=[256, 512])
    assert 256 in results
    assert 512 in results
    assert results[512]["hit_rate_pct"] >= 0.0


def test_map_chunks_to_baseline():
    from app.ingestion import map_chunks_to_baseline
    sweep_sample = [
        {
            "chunk_id": "test_sweep_chunk_0",
            "source_file": "fastapi_fullstack_guide.md",
            "text": "FastAPI is a modern, fast web framework for building APIs with Python 3.8+ based on standard Python type hints.",
        }
    ]
    mapped = map_chunks_to_baseline(sweep_sample)
    assert len(mapped) == 1
    assert "mapped_512_chunk_ids" in mapped[0]

