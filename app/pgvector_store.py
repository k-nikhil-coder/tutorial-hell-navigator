import os
import sys
import re
import json
import logging
import time
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Union
import numpy as np
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
PROCESSED_CHUNKS_FILE = PROJECT_ROOT / "corpus" / "processed" / "chunks_512.json"
SWEEP_CHUNKS_FILE = PROJECT_ROOT / "corpus" / "processed" / "chunks_384.json"
EMBEDDINGS_CACHE_FILE = DATA_DIR / "embeddings_cache.json"

DEFAULT_POSTGRES_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{os.getenv('POSTGRES_USER', 'navigator_user')}:{os.getenv('POSTGRES_PASSWORD', 'navigator_password')}@localhost:5432/{os.getenv('POSTGRES_DB', 'navigator_db')}",
)
VECTOR_DIMENSION = 3072
TABLE_NAME = "document_chunks"

# Categorization metadata mapping based on source file
SOURCE_METADATA_MAP: Dict[str, Dict[str, str]] = {
    "docker_compose.md": {
        "topic": "Docker Compose & Orchestration",
        "category": "DevOps & Infrastructure",
    },
    "docker_compose_best_practices.md": {
        "topic": "Docker & Containerization",
        "category": "DevOps & Infrastructure",
    },
    "docker_production_guide.md": {
        "topic": "Docker & Production Deployment",
        "category": "DevOps & Infrastructure",
    },
    "fastapi_background_tasks.md": {
        "topic": "FastAPI Background Tasks",
        "category": "Backend Architecture",
    },
    "fastapi_cors.md": {
        "topic": "FastAPI CORS & Security",
        "category": "Web Security & APIs",
    },
    "fastapi_fullstack_guide.md": {
        "topic": "Fullstack Architecture",
        "category": "Full-Stack Engineering",
    },
    "fastapi_validation.md": {
        "topic": "FastAPI Request Validation",
        "category": "Backend Architecture",
    },
    "git_reference.md": {
        "topic": "Git & Version Control",
        "category": "Developer Tooling",
    },
    "postgresql_psycopg2.md": {
        "topic": "PostgreSQL & Psycopg2",
        "category": "Databases & Storage",
    },
    "pydantic_models.md": {
        "topic": "Pydantic Models",
        "category": "Data Validation & Typing",
    },
    "pydantic_validation.md": {
        "topic": "Pydantic Validation",
        "category": "Data Validation & Typing",
    },
    "python_debugging.md": {
        "topic": "Python Debugging & Runtime",
        "category": "Python Fundamentals",
    },
    "cs_engineering_roadmap.pdf": {
        "topic": "CS Fundamentals & Roadmaps",
        "category": "Engineering Fundamentals",
    },
}


def infer_metadata(source_file: str, text: str = "") -> Tuple[str, str]:
    """Infer (topic, category) for a given source file and chunk text."""
    clean_src = Path(source_file).name.lower()
    if clean_src in SOURCE_METADATA_MAP:
        meta = SOURCE_METADATA_MAP[clean_src]
        return meta["topic"], meta["category"]

    lower_text = text.lower()
    if "docker" in lower_text or "container" in lower_text:
        return "Docker & Containerization", "DevOps & Infrastructure"
    elif "cors" in lower_text or "origin" in lower_text:
        return "FastAPI CORS & Security", "Web Security & APIs"
    elif "backgroundtasks" in lower_text or "background" in lower_text:
        return "FastAPI Background Tasks", "Backend Architecture"
    elif "pydantic" in lower_text or "field_validator" in lower_text:
        return "Pydantic Validation", "Data Validation & Typing"
    elif "roadmap" in lower_text or "fundamentals" in lower_text:
        return "CS Fundamentals & Roadmaps", "Engineering Fundamentals"
    else:
        return "General Engineering", "General"


def cosine_similarity(vec_a: Union[List[float], np.ndarray], vec_b: Union[List[float], np.ndarray]) -> float:
    """Compute cosine similarity between two float vectors."""
    a = np.asarray(vec_a, dtype=np.float32)
    b = np.asarray(vec_b, dtype=np.float32)
    norm_a = np.linalg.norm(a)
    norm_b = np.linalg.norm(b)
    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


class PgVectorStore:
    """
    Production PostgreSQL + pgvector storage and retrieval engine.
    Supports:
    - Real PostgreSQL with pgvector extension (when reachable via connection string).
    - HNSW indexing with cosine similarity (`vector_cosine_ops`).
    - SQL metadata filtering (topic, category, source_file, char_count).
    - Combined SQL metadata filters + vector search in a single query.
    - Graceful in-memory simulation mode for isolated testing and offline execution.
    """

    def __init__(
        self,
        connection_string: Optional[str] = None,
        in_memory: bool = False,
        table_name: str = TABLE_NAME,
        vector_dim: int = VECTOR_DIMENSION,
    ):
        if not re.match(r"^[A-Za-z0-9_]+$", table_name):
            raise ValueError(f"Invalid SQL table name: {table_name}")
        self.connection_string = connection_string or DEFAULT_POSTGRES_URL
        self.table_name = table_name
        self.vector_dim = vector_dim
        self._in_memory = in_memory
        self._is_live = False
        self._memory_chunks: Dict[str, Dict[str, Any]] = {}

        if not in_memory:
            self._try_connect_live()

    def _try_connect_live(self) -> bool:
        """Attempt to connect to real PostgreSQL and verify pgvector extension."""
        try:
            import psycopg
            from pgvector.psycopg import register_vector

            # Quick connection timeout of 2 seconds to avoid hanging if DB down
            conn_info = self.connection_string
            with psycopg.connect(conn_info, connect_timeout=2) as conn:
                register_vector(conn)
                with conn.cursor() as cur:
                    cur.execute("SELECT 1;")
                self._is_live = True
                logger.info("Successfully connected to live PostgreSQL instance at %s", self.connection_string)
                self.init_db()
                return True
        except Exception as e:
            logger.info("Live PostgreSQL unavailable (%s); using in-memory pgvector simulation engine.", e)
            self._is_live = False
            return False

    @property
    def is_live(self) -> bool:
        """Return True if currently backed by a live PostgreSQL server."""
        return self._is_live

    def get_connection(self):
        """Get a live psycopg connection with pgvector registered and safe timeout."""
        if not self._is_live:
            raise ConnectionError("Live PostgreSQL server is not connected.")
        import psycopg
        from pgvector.psycopg import register_vector

        conn = psycopg.connect(self.connection_string, connect_timeout=5)
        register_vector(conn)
        return conn

    def init_db(self):
        """Create pgvector extension, table schema, and HNSW cosine index.
        Uses halfvec(dim) with halfvec_cosine_ops when vector_dim > 2000 to satisfy
        pgvector's HNSW 2000-dimension limit (HNSW_MAX_DIM = 2000)."""
        if not self._is_live:
            return

        vec_type = f"halfvec({self.vector_dim})" if self.vector_dim > 2000 else f"vector({self.vector_dim})"
        hnsw_ops = "halfvec_cosine_ops" if self.vector_dim > 2000 else "vector_cosine_ops"

        ddl = f"""
        CREATE EXTENSION IF NOT EXISTS vector;

        CREATE TABLE IF NOT EXISTS {self.table_name} (
            chunk_id VARCHAR(128) PRIMARY KEY,
            source_file VARCHAR(255) NOT NULL,
            chunk_index INTEGER NOT NULL,
            text TEXT NOT NULL,
            char_count INTEGER NOT NULL,
            topic VARCHAR(128),
            category VARCHAR(128),
            mapped_512_chunk_ids TEXT[] DEFAULT '{{}}',
            metadata JSONB DEFAULT '{{}}'::jsonb,
            embedding {vec_type} NOT NULL,
            created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
        );

        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_hnsw_cosine
        ON {self.table_name}
        USING hnsw (embedding {hnsw_ops})
        WITH (m = 16, ef_construction = 64);

        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_topic ON {self.table_name} (topic);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_category ON {self.table_name} (category);
        CREATE INDEX IF NOT EXISTS idx_{self.table_name}_source_file ON {self.table_name} (source_file);
        """
        with self.get_connection() as conn:
            with conn.cursor() as cur:
                cur.execute(ddl)
            conn.commit()
            logger.info("Initialized pgvector schema and HNSW cosine index on table '%s' with type %s", self.table_name, vec_type)

    def upsert_chunks(
        self,
        chunks: List[Dict[str, Any]],
        embeddings: Optional[List[List[float]]] = None,
    ) -> int:
        """
        Upsert a list of chunks and their embedding vectors into the database.
        Automatically infers topic and category metadata.
        """
        if not chunks:
            return 0

        # Prepare records
        prepared = []
        for idx, chunk in enumerate(chunks):
            cid = chunk.get("chunk_id", f"chunk_{idx}")
            src = chunk.get("source_file", "unknown")
            text = chunk.get("text", "")
            cidx = chunk.get("chunk_index", idx)
            char_cnt = chunk.get("char_count", len(text))
            topic = chunk.get("topic")
            category = chunk.get("category")
            if not topic or not category:
                inferred_topic, inferred_cat = infer_metadata(src, text)
                topic = topic or inferred_topic
                category = category or inferred_cat

            mapped_ids = chunk.get("mapped_512_chunk_ids", [])
            emb = embeddings[idx] if embeddings and idx < len(embeddings) else chunk.get("embedding")
            if emb is None:
                raise ValueError(f"Chunk '{cid}' has no embedding vector provided.")

            prepared.append({
                "chunk_id": cid,
                "source_file": src,
                "chunk_index": cidx,
                "text": text,
                "char_count": char_cnt,
                "topic": topic,
                "category": category,
                "mapped_512_chunk_ids": mapped_ids,
                "metadata": chunk.get("metadata", {}),
                "embedding": np.asarray(emb, dtype=np.float32),
            })

        if self._is_live:
            vec_cast = f"halfvec({self.vector_dim})" if self.vector_dim > 2000 else f"vector({self.vector_dim})"
            insert_sql = f"""
            INSERT INTO {self.table_name} (
                chunk_id, source_file, chunk_index, text, char_count, topic, category,
                mapped_512_chunk_ids, metadata, embedding
            ) VALUES (
                %(chunk_id)s, %(source_file)s, %(chunk_index)s, %(text)s, %(char_count)s,
                %(topic)s, %(category)s, %(mapped_512_chunk_ids)s, %(metadata)s, %(embedding)s::{vec_cast}
            )
            ON CONFLICT (chunk_id) DO UPDATE SET
                source_file = EXCLUDED.source_file,
                chunk_index = EXCLUDED.chunk_index,
                text = EXCLUDED.text,
                char_count = EXCLUDED.char_count,
                topic = EXCLUDED.topic,
                category = EXCLUDED.category,
                mapped_512_chunk_ids = EXCLUDED.mapped_512_chunk_ids,
                metadata = EXCLUDED.metadata,
                embedding = EXCLUDED.embedding;
            """
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    for row in prepared:
                        cur.execute(
                            insert_sql,
                            {
                                **row,
                                "metadata": json.dumps(row["metadata"]),
                                "embedding": str(row["embedding"].tolist()),
                            },
                        )
                conn.commit()
            logger.info("Upserted %d chunks into live PostgreSQL table '%s'", len(prepared), self.table_name)
        else:
            for row in prepared:
                self._memory_chunks[row["chunk_id"]] = row

        return len(prepared)

    def retrieve_dense(
        self,
        query_vec: List[float],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """Retrieve top-K chunks using pgvector cosine distance (<=>)."""
        return self.retrieve_filtered(query_vec=query_vec, top_k=top_k)

    def retrieve_filtered(
        self,
        query_vec: List[float],
        top_k: int = 5,
        topic: Optional[str] = None,
        category: Optional[str] = None,
        source_file: Optional[str] = None,
        min_char_count: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Execute vector similarity search combined with SQL relational metadata filters.
        In PostgreSQL:
          ORDER BY embedding <=> query_vec::vector ASC
          WHERE topic ILIKE %s AND source_file = %s ...
        """
        if self._is_live:
            where_clauses = ["1=1"]
            params: Dict[str, Any] = {
                "qvec": str(np.asarray(query_vec, dtype=np.float32).tolist()),
                "limit": top_k,
            }

            if topic:
                where_clauses.append("topic ILIKE %(topic)s")
                params["topic"] = f"%{topic}%"
            if category:
                where_clauses.append("category ILIKE %(category)s")
                params["category"] = f"%{category}%"
            if source_file:
                where_clauses.append("source_file = %(source_file)s")
                params["source_file"] = source_file
            if min_char_count is not None:
                where_clauses.append("char_count >= %(min_char)s")
                params["min_char"] = min_char_count

            vec_cast = "halfvec" if self.vector_dim > 2000 else "vector"
            where_sql = " AND ".join(where_clauses)
            query_sql = f"""
            SELECT
                chunk_id,
                source_file,
                chunk_index,
                text,
                char_count,
                topic,
                category,
                mapped_512_chunk_ids,
                1 - (embedding <=> %(qvec)s::{vec_cast}) AS score
            FROM {self.table_name}
            WHERE {where_sql}
            ORDER BY embedding <=> %(qvec)s::{vec_cast} ASC
            LIMIT %(limit)s;
            """
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query_sql, params)
                    rows = cur.fetchall()

            return [
                {
                    "chunk_id": r[0],
                    "source_file": r[1],
                    "chunk_index": r[2],
                    "text": r[3],
                    "char_count": r[4],
                    "topic": r[5],
                    "category": r[6],
                    "mapped_512_chunk_ids": r[7] or [],
                    "score": round(float(r[8]), 4),
                    "is_grounded": bool(float(r[8]) >= 0.40),
                    "retrieval_method": "pgvector_filtered" if (topic or category or source_file) else "pgvector_dense",
                }
                for r in rows
            ]

        # In-Memory / Simulation execution
        candidates = list(self._memory_chunks.values())

        # Apply relational filters
        if topic:
            t_low = topic.lower()
            candidates = [c for c in candidates if t_low in c.get("topic", "").lower()]
        if category:
            c_low = category.lower()
            candidates = [c for c in candidates if c_low in c.get("category", "").lower()]
        if source_file:
            candidates = [c for c in candidates if c.get("source_file") == source_file]
        if min_char_count is not None:
            candidates = [c for c in candidates if c.get("char_count", 0) >= min_char_count]

        if not candidates:
            return []

        q_arr = np.asarray(query_vec, dtype=np.float32)
        scored = []
        for c in candidates:
            sim = cosine_similarity(q_arr, c["embedding"])
            scored.append((sim, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_k]

        return [
            {
                "chunk_id": c["chunk_id"],
                "source_file": c["source_file"],
                "chunk_index": c["chunk_index"],
                "text": c["text"],
                "char_count": c["char_count"],
                "topic": c.get("topic", ""),
                "category": c.get("category", ""),
                "mapped_512_chunk_ids": c.get("mapped_512_chunk_ids", []),
                "score": round(float(sim), 4),
                "is_grounded": bool(float(sim) >= 0.40),
                "retrieval_method": "pgvector_filtered" if (topic or category or source_file) else "pgvector_dense",
            }
            for sim, c in top
        ]

    def count(self) -> int:
        """Return total number of chunks stored."""
        if self._is_live:
            try:
                with self.get_connection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(f"SELECT COUNT(*) FROM {self.table_name};")
                        res = cur.fetchone()
                        return res[0] if res else 0
            except Exception:
                return 0
        return len(self._memory_chunks)

    def get_chunk_by_id(self, chunk_id: str) -> Optional[Dict[str, Any]]:
        """Fetch a specific chunk by its chunk_id."""
        if self._is_live:
            query_sql = f"""
            SELECT chunk_id, source_file, chunk_index, text, char_count, topic, category, mapped_512_chunk_ids
            FROM {self.table_name}
            WHERE chunk_id = %s;
            """
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(query_sql, (chunk_id,))
                    row = cur.fetchone()
                    if not row:
                        return None
                    return {
                        "chunk_id": row[0],
                        "source_file": row[1],
                        "chunk_index": row[2],
                        "text": row[3],
                        "char_count": row[4],
                        "topic": row[5],
                        "category": row[6],
                        "mapped_512_chunk_ids": row[7] or [],
                    }
        return self._memory_chunks.get(chunk_id)

    def delete_all(self):
        """Truncate all rows in table or memory."""
        if self._is_live:
            with self.get_connection() as conn:
                with conn.cursor() as cur:
                    cur.execute(f"TRUNCATE TABLE {self.table_name};")
                conn.commit()
        self._memory_chunks.clear()


_pgvector_store_instance: Optional[PgVectorStore] = None


def get_pgvector_store(
    connection_string: Optional[str] = None,
    in_memory: bool = False,
    force_new: bool = False,
) -> PgVectorStore:
    """Singleton getter for PgVectorStore."""
    global _pgvector_store_instance
    if _pgvector_store_instance is None or force_new or in_memory:
        store = PgVectorStore(connection_string=connection_string, in_memory=in_memory)
        if not in_memory:
            _pgvector_store_instance = store
        return store
    return _pgvector_store_instance


def index_corpus_pgvector(
    chunks_path: Path = PROCESSED_CHUNKS_FILE,
    cache_path: Path = EMBEDDINGS_CACHE_FILE,
    store: Optional[PgVectorStore] = None,
) -> int:
    """Index the document corpus into pgvector store using cached embeddings."""
    if not chunks_path.exists():
        logger.warning("Chunks file not found: %s", chunks_path)
        return 0

    with open(chunks_path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if not chunks:
        return 0

    embeddings = []
    if cache_path.exists():
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                cached = json.load(f)
            embeddings = [cached[str(i)] for i in range(len(chunks))]
        except Exception as e:
            logger.warning("Failed to load embeddings cache: %s", e)

    if not embeddings or len(embeddings) != len(chunks):
        from app.rag import embed_batch
        texts = [c["text"] for c in chunks]
        embeddings = embed_batch(texts)
        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump({str(i): emb for i, emb in enumerate(embeddings)}, f)
        except Exception:
            pass

    pg_store = store or get_pgvector_store()
    return pg_store.upsert_chunks(chunks=chunks, embeddings=embeddings)


def retrieve_pgvector_chunks(
    query: str,
    top_k: int = 5,
    topic: Optional[str] = None,
    category: Optional[str] = None,
    source_file: Optional[str] = None,
    min_char_count: Optional[int] = None,
    store: Optional[PgVectorStore] = None,
) -> List[Dict[str, Any]]:
    """Generate query embedding and retrieve relevant chunks via pgvector with SQL filters."""
    from app.rag import embed_text

    pg_store = store or get_pgvector_store()
    if pg_store.count() == 0:
        index_corpus_pgvector(store=pg_store)

    query_vec = embed_text(query)
    return pg_store.retrieve_filtered(
        query_vec=query_vec,
        top_k=top_k,
        topic=topic,
        category=category,
        source_file=source_file,
        min_char_count=min_char_count,
    )


def retrieve_pgvector_hybrid_chunks(
    query: str,
    top_k: int = 3,
    candidate_k: int = 10,
    topic: Optional[str] = None,
    category: Optional[str] = None,
    store: Optional[PgVectorStore] = None,
) -> List[Dict[str, Any]]:
    """
    Hybrid search combining PgVector dense vector cosine similarity with BM25 lexical sparse vectors
    using Reciprocal Rank Fusion (RRF), with optional SQL topic/category filtering.
    """
    from app.rag import retrieve_sparse_bm25_chunks, reciprocal_rank_fusion

    dense_results = retrieve_pgvector_chunks(
        query=query,
        top_k=candidate_k,
        topic=topic,
        category=category,
        store=store,
    )
    try:
        sparse_results = retrieve_sparse_bm25_chunks(
            query=query,
            top_k=candidate_k,
        )
    except Exception as e:
        logger.warning("BM25 sparse retrieval failed (%s); returning dense pgvector results.", e)
        sparse_results = []

    if not sparse_results:
        return dense_results[:top_k]

    fused = reciprocal_rank_fusion(dense_results, sparse_results, k=60, top_k=top_k)
    for item in fused:
        item["retrieval_method"] = "pgvector_hybrid_rrf"
    return fused
