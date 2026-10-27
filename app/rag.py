import os
import json
import logging
import asyncio
import atexit
from pathlib import Path
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

load_dotenv()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_QDRANT_PATH = PROJECT_ROOT / "data" / "qdrant_db"
PROCESSED_CHUNKS_FILE = PROJECT_ROOT / "corpus" / "processed" / "chunks_512.json"
COLLECTION_NAME = "tutorial_navigator_chunks"
EMBEDDING_MODEL = "gemini-embedding-001"
VECTOR_DIMENSION = 3072

_qdrant_client: Optional[QdrantClient] = None


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY environment variable.")
    return genai.Client(api_key=api_key)


def get_qdrant_client(path: Optional[Path] = None, in_memory: bool = False) -> QdrantClient:
    """Get or initialize a Qdrant client instance."""
    global _qdrant_client
    if in_memory:
        return QdrantClient(":memory:")

    if _qdrant_client is None:
        db_path = path or DEFAULT_QDRANT_PATH
        db_path.mkdir(parents=True, exist_ok=True)
        _qdrant_client = QdrantClient(path=str(db_path))

    return _qdrant_client


def close_qdrant_client():
    """Gracefully close local Qdrant storage before shutdown."""
    global _qdrant_client
    if _qdrant_client is not None:
        try:
            _qdrant_client.close()
        except Exception:
            pass
        _qdrant_client = None


atexit.register(close_qdrant_client)


def ensure_collection(client: QdrantClient, collection_name: str = COLLECTION_NAME, vector_size: int = VECTOR_DIMENSION):
    """Ensure the target Qdrant collection exists with cosine distance."""
    if not client.collection_exists(collection_name):
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
        )
        logger.info("Created Qdrant collection '%s' with size=%d", collection_name, vector_size)


def embed_text(text: str) -> List[float]:
    """Generate vector embedding for a single text string."""
    client = get_genai_client()
    response = client.models.embed_content(model=EMBEDDING_MODEL, contents=text)
    return response.embeddings[0].values


async def embed_text_async(text: str) -> List[float]:
    """Asynchronously generate vector embedding for a query string."""
    client = get_genai_client()
    response = await client.aio.models.embed_content(model=EMBEDDING_MODEL, contents=[text])
    return response.embeddings[0].values


def embed_batch(texts: List[str]) -> List[List[float]]:
    """Generate embeddings for a list of texts in batches."""
    client = get_genai_client()
    batch_size = 50
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i:i + batch_size]
        response = client.models.embed_content(model=EMBEDDING_MODEL, contents=batch)
        for emb in response.embeddings:
            all_embeddings.append(emb.values)

    return all_embeddings


def index_corpus(
    chunks_path: Path = PROCESSED_CHUNKS_FILE,
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
) -> int:
    """Index processed 512-token chunks into Qdrant."""
    if not chunks_path.exists():
        logger.warning("Processed chunks file not found at %s", chunks_path)
        return 0

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        logger.warning("No chunks found in %s", chunks_path)
        return 0

    client = qdrant_client or get_qdrant_client()
    ensure_collection(client, collection_name=collection_name)

    print(f"Generating embeddings for {len(chunks)} chunks using {EMBEDDING_MODEL}...")
    texts = [c["text"] for c in chunks]
    embeddings = embed_batch(texts)

    points = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        point = PointStruct(
            id=idx,
            vector=emb,
            payload={
                "chunk_id": chunk.get("chunk_id", f"chunk_{idx}"),
                "source_file": chunk.get("source_file", "unknown"),
                "chunk_index": chunk.get("chunk_index", idx),
                "text": chunk.get("text", ""),
                "char_count": chunk.get("char_count", len(chunk.get("text", ""))),
            },
        )
        points.append(point)

    client.upsert(collection_name=collection_name, points=points)
    print(f"Upserted {len(points)} chunks into Qdrant collection '{collection_name}'")
    return len(points)


def retrieve_relevant_chunks(
    query: str,
    top_k: int = 3,
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-K most relevant chunks for a user query."""
    client = qdrant_client or get_qdrant_client()
    ensure_collection(client, collection_name=collection_name)

    query_vec = embed_text(query)
    results = client.query_points(
        collection_name=collection_name,
        query=query_vec,
        limit=top_k,
    )

    retrieved = []
    for pt in results.points:
        retrieved.append({
            "chunk_id": pt.payload.get("chunk_id", ""),
            "source_file": pt.payload.get("source_file", ""),
            "score": float(pt.score),
            "text": pt.payload.get("text", ""),
        })

    return retrieved


async def retrieve_relevant_chunks_async(
    query: str,
    top_k: int = 3,
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
) -> List[Dict[str, Any]]:
    """Asynchronously retrieve top-K most relevant chunks from Qdrant."""
    client = qdrant_client or get_qdrant_client()
    ensure_collection(client, collection_name=collection_name)

    query_vec = await embed_text_async(query)
    loop = asyncio.get_running_loop()

    results = await loop.run_in_executor(
        None,
        lambda: client.query_points(
            collection_name=collection_name,
            query=query_vec,
            limit=top_k,
        ),
    )

    retrieved = []
    for pt in results.points:
        retrieved.append({
            "chunk_id": pt.payload.get("chunk_id", ""),
            "source_file": pt.payload.get("source_file", ""),
            "score": float(pt.score),
            "text": pt.payload.get("text", ""),
        })

    return retrieved


def format_retrieved_context(chunks: List[Dict[str, Any]]) -> str:
    """Format retrieved chunks into a structured context block with chunk IDs for citation."""
    if not chunks:
        return "[NO RELEVANT CONTEXT FOUND IN TECHNICAL CORPUS]"

    context_blocks = []
    for c in chunks:
        cid = c.get("chunk_id", "unknown_chunk")
        source = c.get("source_file", "unknown_source")
        text = c.get("text", "").strip()
        context_blocks.append(f"--- [CHUNK_ID: {cid}] (Source: {source}) ---\n{text}")

    return "\n\n".join(context_blocks)


def get_indexed_count(collection_name: str = COLLECTION_NAME) -> int:
    """Return count of vectors in the Qdrant collection."""
    try:
        client = get_qdrant_client()
        if not client.collection_exists(collection_name):
            return 0
        info = client.get_collection(collection_name)
        return info.points_count or 0
    except Exception:
        return 0


if __name__ == "__main__":
    print("Running initial Qdrant indexing for Day 34 baseline...")
    count = index_corpus()
    print(f"Done. Indexed {count} chunks.")
