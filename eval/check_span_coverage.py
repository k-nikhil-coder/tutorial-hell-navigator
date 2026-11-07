"""
eval/check_span_coverage.py

Audits that every answerable question in the benchmark (v2) has its verbatim
evidence span present in at least one indexed chunk in corpus/processed/chunks_384.json.

Requirements:
- Fails on any missing span in the dev split, reporting ID, topic, and span.
- For the test split, audits coverage but prints the count ONLY (never printing
  question text or span text to preserve the sealed test split).
- Callable as a pytest test suite or standalone CLI script.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
GOLD_BENCHMARK_FILE = PROJECT_ROOT / "eval" / "gold_benchmark_v2.json"
CHUNKS_FILE = PROJECT_ROOT / "corpus" / "processed" / "chunks_384.json"


def normalize_ws(text: str) -> str:
    """Normalize internal and surrounding whitespace for robust substring matching."""
    return " ".join(text.split())


def load_chunks():
    assert CHUNKS_FILE.exists(), f"Processed chunks file not found: {CHUNKS_FILE}"
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    return chunks, [normalize_ws(c["text"]) for c in chunks]


def load_benchmark():
    assert GOLD_BENCHMARK_FILE.exists(), f"Benchmark file not found: {GOLD_BENCHMARK_FILE}"
    with open(GOLD_BENCHMARK_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def test_dev_answerable_spans_coverage():
    """Verify that every answerable question in the dev split has its evidence span in chunks_384.json."""
    data = load_benchmark()
    chunks, norm_chunk_texts = load_chunks()

    dev_answerable = [q for q in data if q.get("split") == "dev" and q.get("answerability") == "answerable"]
    assert len(dev_answerable) > 0, "No answerable dev questions found in benchmark"

    misses = []
    for q in dev_answerable:
        spans = [e["span"] for e in q.get("required_evidence", [])]
        found = False
        for s in spans:
            norm_s = normalize_ws(s)
            if any(norm_s in t for t in norm_chunk_texts):
                found = True
                break
        if not found:
            misses.append({
                "id": q["id"],
                "topic": q.get("topic"),
                "source_file": q.get("required_evidence", [{}])[0].get("source_file"),
                "missing_spans": spans,
            })

    if misses:
        error_lines = [
            f"  - [{m['id']}] Topic: {m['topic']} | File: {m['source_file']} | Span: {m['missing_spans']}"
            for m in misses
        ]
        assert len(misses) == 0, (
            f"Dev split coverage check FAILED: {len(misses)} of {len(dev_answerable)} questions "
            f"have evidence spans missing from {CHUNKS_FILE.name}:\n" + "\n".join(error_lines)
        )

    print(f"\n[PASS] Dev split span coverage: {len(dev_answerable)}/{len(dev_answerable)} (100% covered across {len(chunks)} chunks).")


def test_test_split_spans_coverage_silent():
    """
    Verify test split answerable questions have evidence spans in chunks_384.json.
    STRICT PRIVACY: Prints the count ONLY, never printing question text or spans.
    """
    data = load_benchmark()
    chunks, norm_chunk_texts = load_chunks()

    test_answerable = [q for q in data if q.get("split") == "test" and q.get("answerability") == "answerable"]
    assert len(test_answerable) > 0, "No answerable test questions found in benchmark"

    missing_count = 0
    for q in test_answerable:
        spans = [e["span"] for e in q.get("required_evidence", [])]
        found = False
        for s in spans:
            norm_s = normalize_ws(s)
            if any(norm_s in t for t in norm_chunk_texts):
                found = True
                break
        if not found:
            missing_count += 1

    covered_count = len(test_answerable) - missing_count
    print(f"\n[PASS] Test split span coverage: {covered_count}/{len(test_answerable)} covered (missing count: {missing_count}).")

    assert missing_count == 0, (
        f"Test split coverage check FAILED: {missing_count} of {len(test_answerable)} "
        f"test questions have evidence spans missing from {CHUNKS_FILE.name}."
    )


if __name__ == "__main__":
    test_dev_answerable_spans_coverage()
    test_test_split_spans_coverage_silent()
    print("\nAll answerable questions verified: 100% span coverage in indexed chunks.")
