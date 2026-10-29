import os
import sys
import re
import math
import json
import logging
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from collections import Counter
from dotenv import load_dotenv

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

from google import genai
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    SparseVector,
    SparseVectorParams,
)

load_dotenv()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_QDRANT_PATH = DATA_DIR / "qdrant_db"
PROCESSED_CHUNKS_FILE = PROJECT_ROOT / "corpus" / "processed" / "chunks_512.json"
COLLECTION_NAME = "tutorial_navigator_chunks"
EMBEDDING_MODEL = "gemini-embedding-001"
VECTOR_DIMENSION = 3072

BM25_VOCAB_FILE = DATA_DIR / "bm25_vocab.json"
EMBEDDINGS_CACHE_FILE = DATA_DIR / "embeddings_cache.json"

_qdrant_client: Optional[QdrantClient] = None


class BM25Encoder:
    """Term-frequency BM25 encoder producing sparse vectors for Qdrant storage and retrieval."""

    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.vocab: Dict[str, int] = {}
        self.idf: Dict[int, float] = {}
        self.avgdl: float = 0.0

    @staticmethod
    def tokenize(text: str) -> List[str]:
        """Extract code identifiers, words, and hyphenated terms."""
        return [t.lower() for t in re.findall(r"[a-zA-Z0-9_\-\.]+", text) if len(t) > 1]

    def fit(self, corpus: List[str]):
        """Fit BM25 parameters across corpus documents."""
        tokenized_corpus = [self.tokenize(doc) for doc in corpus]
        N = len(corpus)
        self.avgdl = sum(len(doc) for doc in tokenized_corpus) / (N or 1)

        doc_freqs = Counter()
        for doc in tokenized_corpus:
            doc_freqs.update(set(doc))

        self.vocab = {term: idx for idx, (term, _) in enumerate(doc_freqs.most_common())}

        self.idf = {}
        for term, idx in self.vocab.items():
            df = doc_freqs[term]
            self.idf[idx] = math.log(1.0 + (N - df + 0.5) / (df + 0.5))

    def save(self, path: Path = BM25_VOCAB_FILE):
        """Serialize BM25 vocabulary and parameters."""
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "k1": self.k1,
            "b": self.b,
            "avgdl": self.avgdl,
            "vocab": self.vocab,
            "idf": {str(k): v for k, v in self.idf.items()},
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def load(self, path: Path = BM25_VOCAB_FILE) -> bool:
        """Load pre-fitted BM25 vocabulary and parameters."""
        if not path.exists():
            return False
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.k1 = data.get("k1", 1.5)
            self.b = data.get("b", 0.75)
            self.avgdl = data.get("avgdl", 0.0)
            self.vocab = data.get("vocab", {})
            self.idf = {int(k): v for k, v in data.get("idf", {}).items()}
            return True
        except Exception as e:
            logger.warning("Failed to load BM25 vocab: %s", e)
            return False

    def encode_doc(self, text: str) -> SparseVector:
        """Encode a document into a Qdrant SparseVector."""
        tokens = self.tokenize(text)
        doc_len = len(tokens)
        counts = Counter(tokens)

        indices = []
        values = []
        for term, count in counts.items():
            if term in self.vocab:
                idx = self.vocab[term]
                idf = self.idf.get(idx, 0.0)
                tf = (count * (self.k1 + 1.0)) / (
                    count + self.k1 * (1.0 - self.b + self.b * (doc_len / (self.avgdl or 1.0)))
                )
                score = idf * tf
                if score > 0:
                    indices.append(idx)
                    values.append(round(score, 4))

        sorted_pairs = sorted(zip(indices, values))
        return SparseVector(
            indices=[p[0] for p in sorted_pairs],
            values=[p[1] for p in sorted_pairs],
        )

    def encode_query(self, text: str) -> SparseVector:
        """Encode a query string into a Qdrant SparseVector."""
        tokens = self.tokenize(text)
        counts = Counter(tokens)

        indices = []
        values = []
        for term, count in counts.items():
            if term in self.vocab:
                idx = self.vocab[term]
                idf = self.idf.get(idx, 1.0)
                indices.append(idx)
                values.append(round(count * idf, 4))

        sorted_pairs = sorted(zip(indices, values))
        return SparseVector(
            indices=[p[0] for p in sorted_pairs],
            values=[p[1] for p in sorted_pairs],
        )


_bm25_encoder: Optional[BM25Encoder] = None


def get_bm25_encoder() -> BM25Encoder:
    """Retrieve or initialize the BM25 encoder."""
    global _bm25_encoder
    if _bm25_encoder is None:
        _bm25_encoder = BM25Encoder()
        if not _bm25_encoder.load():
            if PROCESSED_CHUNKS_FILE.exists():
                with open(PROCESSED_CHUNKS_FILE, "r", encoding="utf-8") as f:
                    chunks = json.load(f)
                _bm25_encoder.fit([c["text"] for c in chunks])
                _bm25_encoder.save()
    return _bm25_encoder


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


def ensure_collection(
    client: QdrantClient,
    collection_name: str = COLLECTION_NAME,
    vector_size: int = VECTOR_DIMENSION,
):
    """Ensure the target Qdrant collection exists with dense and sparse vector support."""
    need_create = False
    if client.collection_exists(collection_name):
        try:
            info = client.get_collection(collection_name)
            sparse_conf = getattr(info.config.params, "sparse_vectors", None)
            if sparse_conf is None or "bm25" not in sparse_conf:
                logger.info("Existing collection '%s' lacks sparse vectors; recreating with hybrid support.", collection_name)
                client.delete_collection(collection_name)
                need_create = True
        except Exception:
            need_create = True
    else:
        need_create = True

    if need_create:
        client.create_collection(
            collection_name=collection_name,
            vectors_config=VectorParams(size=vector_size, distance=Distance.COSINE),
            sparse_vectors_config={"bm25": SparseVectorParams()},
        )
        logger.info("Created hybrid Qdrant collection '%s' (dense=%d, sparse=bm25)", collection_name, vector_size)


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
    """Generate embeddings for a list of texts in batches with rate-limit throttling."""
    import time

    client = get_genai_client()
    batch_size = 15
    all_embeddings = []

    for i in range(0, len(texts), batch_size):
        batch = texts[i : i + batch_size]
        for attempt in range(6):
            try:
                response = client.models.embed_content(model=EMBEDDING_MODEL, contents=batch)
                for emb in response.embeddings:
                    all_embeddings.append(emb.values)
                print(f"Embedded batch {i // batch_size + 1}/{(len(texts) + batch_size - 1) // batch_size} ({len(batch)} chunks)")
                break
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "503" in err_str:
                    wait_secs = 25 * (attempt + 1)
                    print(f"Rate limit / transient error on batch {i // batch_size + 1}: {e}. Retrying in {wait_secs}s...")
                    time.sleep(wait_secs)
                else:
                    raise e

        # Throttle between batches to remain safely below the 30k tokens/min free tier cap
        if i + batch_size < len(texts):
            time.sleep(8)

    return all_embeddings


def index_corpus(
    chunks_path: Path = PROCESSED_CHUNKS_FILE,
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
    recreate: bool = False,
) -> int:
    """Index processed 512-token chunks into Qdrant with dual dense and BM25 sparse vectors."""
    if not chunks_path.exists():
        logger.warning("Processed chunks file not found at %s", chunks_path)
        return 0

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        logger.warning("No chunks found in %s", chunks_path)
        return 0

    client = qdrant_client or get_qdrant_client()
    if recreate and client.collection_exists(collection_name):
        client.delete_collection(collection_name)
    ensure_collection(client, collection_name=collection_name)

    # 1. Fit & save BM25 encoder
    bm25 = get_bm25_encoder()
    texts = [c["text"] for c in chunks]
    bm25.fit(texts)
    bm25.save()

    # 2. Dense embeddings: reuse cache if available, else batch-embed
    embeddings = []
    if EMBEDDINGS_CACHE_FILE.exists():
        try:
            with open(EMBEDDINGS_CACHE_FILE, "r", encoding="utf-8") as f:
                cached = json.load(f)
            if len(cached) == len(chunks):
                embeddings = [cached[str(i)] for i in range(len(chunks))]
                print(f"Loaded {len(embeddings)} pre-computed embeddings from cache.")
        except Exception as e:
            logger.info("Cache read failed, re-embedding: %s", e)

    if not embeddings:
        print(f"Generating embeddings for {len(chunks)} chunks using {EMBEDDING_MODEL}...")
        embeddings = embed_batch(texts)
        try:
            with open(EMBEDDINGS_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump({str(i): emb for i, emb in enumerate(embeddings)}, f)
        except Exception:
            pass

    # 3. Create Points with dual vectors (unnamed dense + named 'bm25' sparse)
    points = []
    for idx, (chunk, emb) in enumerate(zip(chunks, embeddings)):
        sparse_vec = bm25.encode_doc(chunk["text"])
        point = PointStruct(
            id=idx,
            vector={
                "": emb,
                "bm25": sparse_vec,
            },
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
    print(f"Upserted {len(points)} chunks with dense & sparse BM25 vectors into Qdrant collection '{collection_name}'")
    return len(points)


def retrieve_dense_chunks(
    query: str,
    top_k: int = 5,
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-K chunks using dense vector cosine similarity."""
    client = qdrant_client or get_qdrant_client()
    ensure_collection(client, collection_name=collection_name)

    query_vec = embed_text(query)
    results = client.query_points(
        collection_name=collection_name,
        query=query_vec,
        limit=top_k,
    )

    return [
        {
            "chunk_id": pt.payload.get("chunk_id", ""),
            "source_file": pt.payload.get("source_file", ""),
            "score": float(pt.score),
            "text": pt.payload.get("text", ""),
            "retrieval_method": "dense",
        }
        for pt in results.points
    ]


def retrieve_sparse_bm25_chunks(
    query: str,
    top_k: int = 5,
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-K chunks using BM25 sparse vector dot product in Qdrant."""
    client = qdrant_client or get_qdrant_client()
    ensure_collection(client, collection_name=collection_name)

    bm25 = get_bm25_encoder()
    sparse_query = bm25.encode_query(query)
    if not sparse_query.indices:
        return []

    results = client.query_points(
        collection_name=collection_name,
        query=sparse_query,
        using="bm25",
        limit=top_k,
    )

    return [
        {
            "chunk_id": pt.payload.get("chunk_id", ""),
            "source_file": pt.payload.get("source_file", ""),
            "score": float(pt.score),
            "text": pt.payload.get("text", ""),
            "retrieval_method": "bm25",
        }
        for pt in results.points
    ]


def reciprocal_rank_fusion(
    dense_results: List[Dict[str, Any]],
    sparse_results: List[Dict[str, Any]],
    k: int = 60,
    top_k: int = 3,
) -> List[Dict[str, Any]]:
    """Fuse dense vector results and sparse BM25 results using Reciprocal Rank Fusion."""
    scores: Dict[str, float] = {}
    chunk_map: Dict[str, Dict[str, Any]] = {}
    dense_ranks: Dict[str, int] = {}
    sparse_ranks: Dict[str, int] = {}
    dense_scores: Dict[str, float] = {}
    sparse_scores: Dict[str, float] = {}

    for rank, item in enumerate(dense_results, 1):
        cid = item.get("chunk_id", "")
        chunk_map[cid] = item
        dense_ranks[cid] = rank
        dense_scores[cid] = item.get("score", 0.0)
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))

    for rank, item in enumerate(sparse_results, 1):
        cid = item.get("chunk_id", "")
        if cid not in chunk_map:
            chunk_map[cid] = item
        sparse_ranks[cid] = rank
        sparse_scores[cid] = item.get("score", 0.0)
        scores[cid] = scores.get(cid, 0.0) + (1.0 / (k + rank))

    fused = []
    for cid, rrf_score in sorted(scores.items(), key=lambda x: x[1], reverse=True):
        entry = dict(chunk_map[cid])
        d_score = dense_scores.get(cid, 0.0)
        s_score = sparse_scores.get(cid, 0.0)
        entry["rrf_score"] = round(rrf_score, 5)
        entry["dense_rank"] = dense_ranks.get(cid)
        entry["sparse_rank"] = sparse_ranks.get(cid)
        entry["dense_score"] = round(d_score, 4)
        entry["sparse_score"] = round(s_score, 4)
        entry["score"] = round(rrf_score, 5)
        entry["is_grounded"] = bool(d_score >= 0.40 or s_score > 0.0)
        entry["retrieval_method"] = "hybrid_rrf"
        fused.append(entry)

    return fused[:top_k]


def retrieve_hybrid_chunks(
    query: str,
    top_k: int = 3,
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
    candidate_k: int = 10,
) -> List[Dict[str, Any]]:
    """Retrieve top-K chunks via Hybrid Search (Dense + BM25 merged with RRF)."""
    dense_results = retrieve_dense_chunks(
        query=query, top_k=candidate_k, collection_name=collection_name, qdrant_client=qdrant_client
    )
    sparse_results = retrieve_sparse_bm25_chunks(
        query=query, top_k=candidate_k, collection_name=collection_name, qdrant_client=qdrant_client
    )
    return reciprocal_rank_fusion(dense_results, sparse_results, k=60, top_k=top_k)


def retrieve_relevant_chunks(
    query: str,
    top_k: int = 3,
    search_mode: str = "hybrid",
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
) -> List[Dict[str, Any]]:
    """Retrieve top-K most relevant chunks using the specified search mode ('hybrid', 'dense', or 'sparse')."""
    if search_mode == "dense":
        return retrieve_dense_chunks(
            query=query, top_k=top_k, collection_name=collection_name, qdrant_client=qdrant_client
        )
    elif search_mode == "sparse":
        return retrieve_sparse_bm25_chunks(
            query=query, top_k=top_k, collection_name=collection_name, qdrant_client=qdrant_client
        )
    else:
        return retrieve_hybrid_chunks(
            query=query, top_k=top_k, collection_name=collection_name, qdrant_client=qdrant_client
        )


async def retrieve_relevant_chunks_async(
    query: str,
    top_k: int = 3,
    search_mode: str = "hybrid",
    collection_name: str = COLLECTION_NAME,
    qdrant_client: Optional[QdrantClient] = None,
) -> List[Dict[str, Any]]:
    """Asynchronously retrieve top-K most relevant chunks from Qdrant."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: retrieve_relevant_chunks(
            query=query,
            top_k=top_k,
            search_mode=search_mode,
            collection_name=collection_name,
            qdrant_client=qdrant_client,
        ),
    )


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
    print("Indexing corpus into Qdrant with Dense and BM25 Sparse vectors...")
    count = index_corpus(recreate=True)
    print(f"Done. Indexed {count} chunks into hybrid collection '{COLLECTION_NAME}'.")
