import os
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional

try:
    import pymupdf as fitz
except ImportError:
    import fitz

from langchain_text_splitters import RecursiveCharacterTextSplitter

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "corpus" / "processed"


def clean_text(raw: str) -> str:
    """Normalize whitespace and strip noisy document artifacts."""
    # Replace non-breaking spaces and null bytes
    cleaned = raw.replace("\xa0", " ").replace("\x00", "")
    # Collapse multiple consecutive blank lines
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def extract_text_from_pdf(file_path: Path) -> str:
    """Extract raw text from a PDF file using PyMuPDF."""
    text_parts = []
    with fitz.open(file_path) as doc:
        for page in doc:
            page_text = page.get_text("text")
            if page_text:
                text_parts.append(page_text)
    return clean_text("\n".join(text_parts))


def extract_text_from_file(file_path: Path) -> Optional[str]:
    """Extract text from supported document formats (.pdf, .md, .txt)."""
    suffix = file_path.suffix.lower()
    if suffix == ".pdf":
        return extract_text_from_pdf(file_path)
    elif suffix in [".md", ".txt", ".markdown"]:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            return clean_text(f.read())
    return None


def process_documents(
    chunk_size: int = 512,
    chunk_overlap: int = 50,
    raw_dir: Path = CORPUS_DIR,
    output_dir: Path = PROCESSED_DIR,
) -> List[Dict[str, Any]]:
    """Parse raw technical documents and split them into token-aware overlapping chunks."""
    output_dir.mkdir(parents=True, exist_ok=True)

    # Token-aware splitter using OpenAI's cl100k_base tokenizer
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    raw_files = sorted(raw_dir.glob("*.*"))

    for file_path in raw_files:
        content = extract_text_from_file(file_path)
        if not content:
            continue

        chunks = splitter.split_text(content)

        for i, chunk_text in enumerate(chunks):
            chunk_record = {
                "chunk_id": f"{file_path.stem}_chunk_{i}",
                "source_file": file_path.name,
                "chunk_index": i,
                "text": chunk_text,
                "char_count": len(chunk_text),
            }
            all_chunks.append(chunk_record)

    output_file = output_dir / f"chunks_{chunk_size}.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)

    print(f"Processed {len(all_chunks)} chunks for size {chunk_size} (overlap: {chunk_overlap}) -> {output_file.name}")
    return all_chunks


def map_chunks_to_baseline(
    sweep_chunks: List[Dict[str, Any]],
    baseline_chunks_path: Path = PROCESSED_DIR / "chunks_512.json",
    min_word_overlap: int = 15,
    min_overlap_ratio: float = 0.20,
) -> List[Dict[str, Any]]:
    """
    Map chunks from an alternative chunking sweep to baseline 512-token chunks
    based on source file and textual overlap. This allows fair evaluation against gold set
    ground-truth expected_chunk_ids.
    """
    if not baseline_chunks_path.exists():
        return sweep_chunks

    with open(baseline_chunks_path, "r", encoding="utf-8") as f:
        baseline_chunks = json.load(f)

    from collections import defaultdict
    b_by_source = defaultdict(list)
    for b in baseline_chunks:
        b_by_source[b["source_file"]].append(b)

    for chunk in sweep_chunks:
        src = chunk.get("source_file", "")
        candidates = b_by_source.get(src, [])
        chunk_words = set(chunk["text"].lower().split())
        if not chunk_words:
            chunk["mapped_512_chunk_ids"] = []
            continue

        matched = []
        for b in candidates:
            b_words = set(b["text"].lower().split())
            intersection = len(chunk_words & b_words)
            if intersection >= min_word_overlap:
                ratio = intersection / len(chunk_words)
                if ratio >= min_overlap_ratio:
                    matched.append((b["chunk_id"], ratio))

        matched.sort(key=lambda x: x[1], reverse=True)
        chunk["mapped_512_chunk_ids"] = [cid for cid, _ in matched]

    return sweep_chunks


def process_chunk_sweep(
    chunk_size: int = 384,
    chunk_overlap: int = 60,
    raw_dir: Path = CORPUS_DIR,
    output_dir: Path = PROCESSED_DIR,
    output_filename: str = "chunks_384.json",
) -> List[Dict[str, Any]]:
    """
    Generate an alternative chunk sweep dataset with mapped 512-token chunk references.
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    raw_files = sorted(raw_dir.glob("*.*"))

    for file_path in raw_files:
        content = extract_text_from_file(file_path)
        if not content:
            continue

        chunks = splitter.split_text(content)
        for i, chunk_text in enumerate(chunks):
            chunk_record = {
                "chunk_id": f"{file_path.stem}_sweep384_chunk_{i}",
                "source_file": file_path.name,
                "chunk_index": i,
                "text": chunk_text,
                "char_count": len(chunk_text),
            }
            all_chunks.append(chunk_record)

    all_chunks = map_chunks_to_baseline(all_chunks)

    output_file = output_dir / output_filename
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)

    print(f"Processed sweep dataset: {len(all_chunks)} chunks for size {chunk_size} -> {output_file.name}")
    return all_chunks


def run_ingestion_pipeline():
    """Run ingestion across benchmark chunk sizes."""
    print("=" * 60)
    print("Ingesting technical documents from:", CORPUS_DIR)
    print("=" * 60)

    strategies = [
        {"size": 256, "overlap": 25},
        {"size": 512, "overlap": 50},
        {"size": 1024, "overlap": 100},
    ]

    for strat in strategies:
        process_documents(chunk_size=strat["size"], chunk_overlap=strat["overlap"])

    print("=" * 60)
    print("Data ingestion complete.")


if __name__ == "__main__":
    run_ingestion_pipeline()
