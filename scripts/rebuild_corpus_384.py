import os
import sys
import json
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.ingestion import extract_text_from_file, map_chunks_to_baseline
from app.rag import (
    index_corpus,
    COLLECTION_NAME,
    SWEEP_COLLECTION_NAME,
    get_qdrant_client,
    DATA_DIR,
    BM25_VOCAB_FILE,
)
from app.pgvector_store import (
    PgVectorStore,
    index_corpus_pgvector,
    get_pgvector_store,
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CORPUS_DIR = PROJECT_ROOT / "corpus" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "corpus" / "processed"
OUTPUT_FILE = PROCESSED_DIR / "chunks_384.json"
CACHE_FILE = DATA_DIR / "embeddings_cache_chunks_384.json"

TEN_TIER1_FILES = [
    "docker_compose.md",
    "docker_compose_best_practices.md",
    "docker_production_guide.md",
    "fastapi_background_tasks.md",
    "fastapi_cors.md",
    "fastapi_fullstack_guide.md",
    "fastapi_validation.md",
    "postgresql_psycopg2.md",
    "pydantic_models.md",
    "pydantic_validation.md",
]

def rebuild_chunks():
    splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name="cl100k_base",
        chunk_size=384,
        chunk_overlap=60,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    all_chunks = []
    for fname in sorted(TEN_TIER1_FILES):
        fpath = CORPUS_DIR / fname
        if not fpath.exists():
            raise FileNotFoundError(f"Missing required T1 corpus file: {fpath}")
        
        text = extract_text_from_file(fpath)
        if not text:
            raise ValueError(f"Extracted empty text from {fpath}")
        
        split_texts = splitter.split_text(text)
        for i, ct in enumerate(split_texts):
            all_chunks.append({
                "chunk_id": f"{fpath.stem}_sweep384_chunk_{i}",
                "source_file": fname,
                "chunk_index": i,
                "text": ct,
                "char_count": len(ct),
            })

    # Map to baseline chunks if available
    all_chunks = map_chunks_to_baseline(all_chunks)

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_chunks, f, indent=2)

    print(f"Generated {len(all_chunks)} chunks across {len(TEN_TIER1_FILES)} files -> {OUTPUT_FILE}")
    return all_chunks


def rebuild_qdrant_indexes():
    # Index into tutorial_navigator_chunks_sweep
    print("Indexing into Qdrant collection:", SWEEP_COLLECTION_NAME)
    cnt_sweep = index_corpus(
        chunks_path=OUTPUT_FILE,
        collection_name=SWEEP_COLLECTION_NAME,
        recreate=True,
        cache_path=CACHE_FILE,
    )
    print(f"Indexed {cnt_sweep} chunks into {SWEEP_COLLECTION_NAME}")

    # Also index into primary tutorial_navigator_chunks so run_eval.py default collection evaluates the 10-file 384 chunks
    print("Indexing into Qdrant collection:", COLLECTION_NAME)
    cnt_primary = index_corpus(
        chunks_path=OUTPUT_FILE,
        collection_name=COLLECTION_NAME,
        recreate=True,
        cache_path=CACHE_FILE,
    )
    print(f"Indexed {cnt_primary} chunks into {COLLECTION_NAME}")


def rebuild_pgvector_indexes():
    print("Indexing into pgvector store...")
    pg_store = PgVectorStore(in_memory=True)
    cnt_pg = index_corpus_pgvector(
        chunks_path=OUTPUT_FILE,
        cache_path=CACHE_FILE,
        store=pg_store,
    )
    print(f"Indexed {cnt_pg} chunks into pgvector in-memory store.")


if __name__ == "__main__":
    chunks = rebuild_chunks()
    rebuild_qdrant_indexes()
    rebuild_pgvector_indexes()
    print("All dense and BM25 indexes rebuilt successfully!")
