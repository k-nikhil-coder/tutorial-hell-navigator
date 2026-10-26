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
