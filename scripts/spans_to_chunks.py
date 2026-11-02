"""
scripts/spans_to_chunks.py (and eval/spans_to_chunks.py)

Maps verbatim evidence spans to chunk IDs for any arbitrary chunk size and overlap:
1. Loads corpus documents and chunks them with requested chunk size and overlap (or loads pre-chunked JSON).
2. For each question and each span in 'answer_spans' / 'acceptable_alternatives', searches the corresponding
   corpus chunks for verbatim substring occurrences.
3. Outputs question_id -> list of covering chunk IDs.
"""

import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Set

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_RAW_DIR = PROJECT_ROOT / "corpus" / "raw"
CORPUS_PROCESSED_DIR = PROJECT_ROOT / "corpus" / "processed"
GOLD_SET_PATH = PROJECT_ROOT / "eval" / "gold_set_v2.json"


def get_chunks_for_size(
    chunk_size: int = 384,
    chunk_overlap: int = 60,
    raw_dir: Path = CORPUS_RAW_DIR,
    processed_dir: Path = CORPUS_PROCESSED_DIR,
) -> List[Dict[str, Any]]:
    """
    Get chunks for the requested chunk size.
    If pre-chunked file chunks_{chunk_size}.json exists in processed_dir, load it.
    Otherwise, chunk on the fly using token-aware splitting.
    """
    target_file = processed_dir / f"chunks_{chunk_size}.json"
    if target_file.exists():
        with open(target_file, "r", encoding="utf-8") as f:
            return json.load(f)

    # Chunk on the fly using app/ingestion.py logic
    try:
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
            encoding_name="cl100k_base",
            chunk_size=chunk_size,
            chunk_overlap=chunk_overlap,
            separators=["\n\n", "\n", ". ", " ", ""],
        )
    except ImportError:
        # Fallback character-based splitter if langchain is unavailable
        class SimpleSplitter:
            def __init__(self, c_size: int, c_overlap: int):
                self.char_size = c_size * 4
                self.char_overlap = c_overlap * 4
            def split_text(self, text: str) -> List[str]:
                chunks = []
                start = 0
                while start < len(text):
                    end = start + self.char_size
                    chunks.append(text[start:end])
                    start += (self.char_size - self.char_overlap)
                return chunks
        splitter = SimpleSplitter(chunk_size, chunk_overlap)

    all_chunks = []
    for file_path in sorted(raw_dir.glob("*.*")):
        suffix = file_path.suffix.lower()
        if suffix in [".md", ".txt", ".markdown"]:
            text = file_path.read_text(encoding="utf-8", errors="replace")
        elif suffix == ".pdf":
            try:
                import fitz
                doc = fitz.open(file_path)
                text = "\n".join(page.get_text() for page in doc)
                doc.close()
            except Exception:
                continue
        else:
            continue

        raw_chunks = splitter.split_text(text)
        for idx, c_text in enumerate(raw_chunks):
            all_chunks.append({
                "chunk_id": f"{file_path.stem}_chunk_{idx}",
                "source_file": file_path.name,
                "chunk_index": idx,
                "text": c_text,
                "char_count": len(c_text),
            })

    return all_chunks


def find_chunks_covering_span(
    span: str,
    source_file: str,
    chunks: List[Dict[str, Any]],
) -> List[str]:
    """Find chunk IDs in source_file that contain the given verbatim span."""
    if not span or not span.strip():
        return []

    norm_span = " ".join(span.split()).strip()
    source_stem = Path(source_file).stem
    matched_cids = []

    for c in chunks:
        # Check source file matching by filename or stem
        c_src = c.get("source_file", "")
        c_id = c.get("chunk_id", "")
        if c_src != source_file and not c_id.startswith(source_stem):
            continue

        c_text = c.get("text", "")
        if span in c_text:
            matched_cids.append(c_id)
        else:
            norm_c_text = " ".join(c_text.split())
            if norm_span in norm_c_text:
                matched_cids.append(c_id)

    return matched_cids


def map_spans_to_chunk_ids(
    questions: List[Dict[str, Any]],
    chunk_size: int = 384,
    chunk_overlap: int = 60,
    raw_dir: Path = CORPUS_RAW_DIR,
    processed_dir: Path = CORPUS_PROCESSED_DIR,
) -> Dict[str, List[str]]:
    """
    Map verbatim answer spans to chunk IDs for all questions at a given chunk size.
    Returns: Dict[question_id, List[chunk_id]]
    """
    chunks = get_chunks_for_size(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        raw_dir=raw_dir,
        processed_dir=processed_dir,
    )

    mapping: Dict[str, List[str]] = {}

    for q in questions:
        qid = q.get("id", "UNKNOWN")
        spans = q.get("answer_spans") or q.get("required_evidence") or []
        alt_spans = q.get("acceptable_alternatives") or []
        all_spans = spans + alt_spans

        all_covering_cids: Set[str] = set()
        for item in all_spans:
            if isinstance(item, dict):
                span_text = item.get("span", "")
                src_file = item.get("source_file", "")
            else:
                span_text = getattr(item, "span", "")
                src_file = getattr(item, "source_file", "")

            matched = find_chunks_covering_span(span_text, src_file, chunks)
            all_covering_cids.update(matched)

        # Fallback to legacy expected chunks if no spans are present
        if not all_covering_cids and (q.get("expected_chunk_ids") or q.get("legacy_expected_chunk_ids")):
            legacy = q.get("expected_chunk_ids") or q.get("legacy_expected_chunk_ids") or []
            all_covering_cids.update(legacy)

        mapping[qid] = sorted(list(all_covering_cids))

    return mapping


def main():
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    parser = argparse.ArgumentParser(description="Map verbatim evidence spans to chunk IDs for any chunk size")
    parser.add_argument("--chunk-size", type=int, default=384, help="Target chunk size in tokens (default: 384)")
    parser.add_argument("--overlap", type=int, default=60, help="Chunk overlap in tokens (default: 60)")
    parser.add_argument("--gold-set", default=str(GOLD_SET_PATH), help="Path to gold set JSON with answer_spans")
    parser.add_argument("-o", "--output", default=None, help="Optional output JSON path for the mapping")
    args = parser.parse_args()

    with open(args.gold_set, "r", encoding="utf-8") as f:
        questions = json.load(f)

    mapping = map_spans_to_chunk_ids(
        questions=questions,
        chunk_size=args.chunk_size,
        chunk_overlap=args.overlap,
    )

    print("=" * 80)
    print(f"🧩 SPANS TO CHUNK IDs (Chunk Size: {args.chunk_size}, Overlap: {args.overlap})")
    print(f"Total questions processed: {len(questions)}")
    mapped_count = sum(1 for cids in mapping.values() if len(cids) > 0)
    print(f"Questions with mapped chunk IDs: {mapped_count}")
    print("-" * 80)

    for qid, cids in list(mapping.items())[:10]:
        print(f"  • {qid}: {cids}")

    if args.output:
        out_p = Path(args.output)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        with open(out_p, "w", encoding="utf-8") as f:
            json.dump(mapping, f, indent=2)
        print(f"Mapping saved to {out_p}")
    print("=" * 80)


if __name__ == "__main__":
    main()
