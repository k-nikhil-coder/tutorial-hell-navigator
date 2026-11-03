import pytest
import numpy as np
from pathlib import Path
from unittest.mock import MagicMock, patch

from app.pgvector_store import (
    PgVectorStore,
    get_pgvector_store,
    infer_metadata,
    cosine_similarity,
    index_corpus_pgvector,
    retrieve_pgvector_chunks,
    retrieve_pgvector_hybrid_chunks,
    SOURCE_METADATA_MAP,
    VECTOR_DIMENSION,
)
from app.rag import retrieve_relevant_chunks, get_pgvector_indexed_count


def test_cosine_similarity_edge_cases():
    # Identical vectors
    v1 = [1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v1), rel=1e-5) == 1.0

    # Orthogonal vectors
    v2 = [0.0, 1.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v2), abs=1e-5) == 0.0

    # Opposite vectors
    v3 = [-1.0, 0.0, 0.0]
    assert pytest.approx(cosine_similarity(v1, v3), rel=1e-5) == -1.0

    # Zero vector handling
    v_zero = [0.0, 0.0, 0.0]
    assert cosine_similarity(v1, v_zero) == 0.0


def test_infer_metadata():
    topic, cat = infer_metadata("docker_compose_best_practices.md")
    assert topic == "Docker & Containerization"
    assert cat == "DevOps & Infrastructure"

    topic, cat = infer_metadata("fastapi_cors.md")
    assert topic == "FastAPI CORS & Security"
    assert cat == "Web Security & APIs"

    topic, cat = infer_metadata("pydantic_validation.md")
    assert topic == "Pydantic Validation"
    assert cat == "Data Validation & Typing"

    topic, cat = infer_metadata("unknown_doc.txt", "Some text explaining Docker containers")
    assert topic == "Docker & Containerization"


def test_pgvector_store_in_memory_upsert_and_dense():
    store = PgVectorStore(in_memory=True, vector_dim=4)
    assert not store.is_live
    assert store.count() == 0

    chunks = [
        {
            "chunk_id": "c1",
            "source_file": "fastapi_cors.md",
            "text": "CORS configuration in FastAPI",
            "chunk_index": 0,
            "char_count": 29,
        },
        {
            "chunk_id": "c2",
            "source_file": "docker_compose_best_practices.md",
            "text": "Docker compose multi-container architecture",
            "chunk_index": 0,
            "char_count": 43,
        },
    ]
    embeddings = [
        [1.0, 0.0, 0.0, 0.0],
        [0.0, 1.0, 0.0, 0.0],
    ]

    count = store.upsert_chunks(chunks, embeddings)
    assert count == 2
    assert store.count() == 2

    # Query nearest to c1
    res1 = store.retrieve_dense([0.9, 0.1, 0.0, 0.0], top_k=1)
    assert len(res1) == 1
    assert res1[0]["chunk_id"] == "c1"
    assert res1[0]["topic"] == "FastAPI CORS & Security"
    assert res1[0]["score"] > 0.85

    # Query nearest to c2
    res2 = store.retrieve_dense([0.1, 0.95, 0.0, 0.0], top_k=1)
    assert len(res2) == 1
    assert res2[0]["chunk_id"] == "c2"
    assert res2[0]["topic"] == "Docker & Containerization"


def test_pgvector_sql_metadata_filtering():
    store = PgVectorStore(in_memory=True, vector_dim=4)
    chunks = [
        {
            "chunk_id": "c_docker_1",
            "source_file": "docker_production_guide.md",
            "text": "Production Docker containerization with multi-stage builds",
            "chunk_index": 0,
            "char_count": 100,
        },
        {
            "chunk_id": "c_docker_2",
            "source_file": "docker_compose_best_practices.md",
            "text": "Docker Compose orchestration",
            "chunk_index": 1,
            "char_count": 50,
        },
        {
            "chunk_id": "c_pydantic_1",
            "source_file": "pydantic_validation.md",
            "text": "Pydantic field validators and data schemas",
            "chunk_index": 0,
            "char_count": 80,
        },
    ]
    # All vectors identical to test pure SQL filtering effect
    emb = [0.5, 0.5, 0.5, 0.5]
    embeddings = [emb, emb, emb]
    store.upsert_chunks(chunks, embeddings)

    # 1. Filter by topic='Docker'
    res_docker = store.retrieve_filtered(emb, topic="Docker", top_k=5)
    assert len(res_docker) == 2
    assert all("docker" in r["chunk_id"] for r in res_docker)

    # 2. Filter by topic='Pydantic'
    res_pydantic = store.retrieve_filtered(emb, topic="Pydantic", top_k=5)
    assert len(res_pydantic) == 1
    assert res_pydantic[0]["chunk_id"] == "c_pydantic_1"

    # 3. Filter by category='DevOps & Infrastructure'
    res_cat = store.retrieve_filtered(emb, category="DevOps", top_k=5)
    assert len(res_cat) == 2

    # 4. Filter by source_file
    res_file = store.retrieve_filtered(emb, source_file="docker_production_guide.md", top_k=5)
    assert len(res_file) == 1
    assert res_file[0]["chunk_id"] == "c_docker_1"

    # 5. Filter by min_char_count
    res_len = store.retrieve_filtered(emb, min_char_count=90, top_k=5)
    assert len(res_len) == 1
    assert res_len[0]["chunk_id"] == "c_docker_1"


def test_index_corpus_pgvector_and_retrieve():
    store = PgVectorStore(in_memory=True)
    count = index_corpus_pgvector(store=store)
    assert count > 0
    assert store.count() == count

    # Retrieve CORS query
    results = retrieve_pgvector_chunks("FastAPI CORS allow_credentials wildcard origin", top_k=3, store=store)
    assert len(results) > 0
    top_chunk = results[0]
    assert "cors" in top_chunk["source_file"].lower()
    assert top_chunk["score"] > 0.5


def test_pgvector_hybrid_retrieval():
    store = PgVectorStore(in_memory=True)
    index_corpus_pgvector(store=store)

    hybrid_results = retrieve_pgvector_hybrid_chunks(
        query="psycopg2 gcc build failure in minimal Docker image",
        top_k=3,
        store=store,
    )
    assert len(hybrid_results) == 3
    # Check that docker production guide containing psycopg2 fix is retrieved at rank 1
    top_chunk = hybrid_results[0]
    assert "docker" in top_chunk["source_file"].lower()
    assert top_chunk["retrieval_method"] == "pgvector_hybrid_rrf"
    assert "rrf_score" in top_chunk


def test_rag_module_pgvector_integration():
    # Test retrieve_relevant_chunks with backend="pgvector"
    results = retrieve_relevant_chunks(
        query="How to configure CORS in FastAPI?",
        top_k=2,
        backend="pgvector",
    )
    assert len(results) == 2
    assert "fastapi_cors" in results[0]["chunk_id"]

    # Test get_pgvector_indexed_count
    cnt = get_pgvector_indexed_count()
    assert isinstance(cnt, int)
    assert cnt >= 0


def test_live_postgres_mocked_interaction():
    """Verify live PostgreSQL interaction: DDL, HNSW cosine index, SQL queries."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("chunk_1", "fastapi_cors.md", 0, "CORS text", 100, "FastAPI CORS", "Web Security", [], 0.92)
    ]
    mock_cursor.fetchone.return_value = [1]

    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg.connect", return_value=mock_conn):
        with patch("pgvector.psycopg.register_vector") as mock_reg:
            store = PgVectorStore(
                connection_string="postgresql://user:pass@localhost:5432/testdb",
                in_memory=False,
            )
            assert store.is_live is True
            mock_reg.assert_called()

            # Verify DDL executed HNSW index with halfvec for dim > 2000 (3072)
            calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
            ddl_calls = [c for c in calls if "CREATE EXTENSION" in c or "CREATE TABLE" in c]
            assert len(ddl_calls) >= 1
            assert "embedding halfvec(3072) NOT NULL" in ddl_calls[0]
            assert "USING hnsw (embedding halfvec_cosine_ops)" in ddl_calls[0]

            # Test filtered query with topic parameter
            res = store.retrieve_filtered(
                query_vec=[0.1] * VECTOR_DIMENSION,
                topic="CORS",
                top_k=5,
            )
            assert len(res) == 1
            assert res[0]["chunk_id"] == "chunk_1"

            # Check that SQL query contained vector cosine distance <=> cast to halfvec
            sql_query = mock_cursor.execute.call_args[0][0]
            assert "embedding <=> %(qvec)s::halfvec" in sql_query
            assert "topic ILIKE %(topic)s" in sql_query


def test_live_postgres_dim_under_2000():
    """Verify that vector dimensions <= 2000 use standard vector(dim) and vector_cosine_ops."""
    mock_cursor = MagicMock()
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg.connect", return_value=mock_conn):
        with patch("pgvector.psycopg.register_vector"):
            store = PgVectorStore(
                connection_string="postgresql://user:pass@localhost:5432/testdb",
                in_memory=False,
                vector_dim=1536,
            )
            assert store.is_live is True
            calls = [c[0][0] for c in mock_cursor.execute.call_args_list]
            ddl_calls = [c for c in calls if "CREATE EXTENSION" in c or "CREATE TABLE" in c]
            assert len(ddl_calls) >= 1
            assert "embedding vector(1536) NOT NULL" in ddl_calls[0]
            assert "USING hnsw (embedding vector_cosine_ops)" in ddl_calls[0]


def test_get_chunk_by_id_pgvector():
    store = PgVectorStore(in_memory=True, vector_dim=4)
    store.upsert_chunks(
        [{"chunk_id": "target_chunk", "source_file": "test.md", "text": "Hello world"}],
        [[0.1, 0.2, 0.3, 0.4]],
    )
    found = store.get_chunk_by_id("target_chunk")
    assert found is not None
    assert found["text"] == "Hello world"

    missing = store.get_chunk_by_id("non_existent_id")
    assert missing is None


def test_pgvector_table_name_validation():
    # Valid names
    store1 = PgVectorStore(in_memory=True, table_name="valid_table_123")
    assert store1.table_name == "valid_table_123"

    # SQL injection attempt
    with pytest.raises(ValueError, match="Invalid SQL table name"):
        PgVectorStore(in_memory=True, table_name="chunks; DROP TABLE users;")

    with pytest.raises(ValueError, match="Invalid SQL table name"):
        PgVectorStore(in_memory=True, table_name="chunks--comment")


def test_pgvector_hybrid_resilience_when_bm25_fails():
    store = PgVectorStore(in_memory=True)
    index_corpus_pgvector(store=store)

    with patch("app.rag.retrieve_sparse_bm25_chunks", side_effect=RuntimeError("Qdrant connection refused")):
        results = retrieve_pgvector_hybrid_chunks(
            query="FastAPI CORS allow_credentials wildcard origin",
            top_k=2,
            store=store,
        )
        assert len(results) == 2
        assert results[0]["retrieval_method"] in ("pgvector_dense", "pgvector_filtered")


def test_pgvector_grounding_flag_low_similarity():
    store = PgVectorStore(in_memory=True, vector_dim=4)
    store.upsert_chunks(
        [{"chunk_id": "c1", "source_file": "fastapi.md", "text": "FastAPI"}],
        [[1.0, 0.0, 0.0, 0.0]],
    )
    # Orthogonal query vec -> cosine sim is 0.0 -> is_grounded must be False
    res = store.retrieve_filtered([0.0, 1.0, 0.0, 0.0], top_k=1)
    assert len(res) == 1
    assert res[0]["score"] == 0.0
    assert res[0]["is_grounded"] is False


@pytest.mark.asyncio
async def test_health_endpoint_pgvector_metadata():
    import httpx
    from app.main import app

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "pgvector_indexed_chunks" in data
        assert "pgvector_is_live" in data
        assert isinstance(data["pgvector_indexed_chunks"], int)
        assert isinstance(data["pgvector_is_live"], bool)


def test_live_postgres_upsert_chunks_dim_over_2000():
    """Verify live PostgreSQL upsert formats DDL and INSERT with halfvec(dim) cast for dim > 2000."""
    mock_cursor = MagicMock()
    mock_cursor.fetchone.return_value = [1]
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg.connect", return_value=mock_conn):
        with patch("pgvector.psycopg.register_vector"):
            store = PgVectorStore(
                connection_string="postgresql://user:pass@localhost:5432/testdb",
                in_memory=False,
                vector_dim=3072,
            )
            assert store.is_live is True

            sample_chunks = [
                {
                    "chunk_id": "test_chunk_halfvec",
                    "source_file": "fastapi_cors.md",
                    "text": "CORS middleware explanation",
                    "chunk_index": 0,
                    "char_count": 27,
                }
            ]
            embeddings = [[0.01] * 3072]
            upserted = store.upsert_chunks(sample_chunks, embeddings)
            assert upserted == 1

            # Check executed SQL queries
            calls = [c[0] for c in mock_cursor.execute.call_args_list]
            insert_calls = [c for c in calls if "INSERT INTO document_chunks" in c[0]]
            assert len(insert_calls) == 1
            sql = insert_calls[0][0]
            params = insert_calls[0][1]

            assert "embedding" in sql
            assert "%(embedding)s::halfvec(3072)" in sql
            assert params["chunk_id"] == "test_chunk_halfvec"
            assert isinstance(params["embedding"], str)
            assert params["embedding"].startswith("[") and params["embedding"].endswith("]")


def test_live_postgres_filtered_clauses():
    """Verify all SQL where clauses (category, source_file, min_char_count) in live mode."""
    mock_cursor = MagicMock()
    mock_cursor.fetchall.return_value = [
        ("chunk_x", "fastapi_cors.md", 0, "text", 150, "CORS", "Security", [], 0.95)
    ]
    mock_cursor.fetchone.return_value = [1]
    mock_conn = MagicMock()
    mock_conn.__enter__.return_value = mock_conn
    mock_conn.cursor.return_value.__enter__.return_value = mock_cursor

    with patch("psycopg.connect", return_value=mock_conn):
        with patch("pgvector.psycopg.register_vector"):
            store = PgVectorStore(
                connection_string="postgresql://user:pass@localhost:5432/testdb",
                in_memory=False,
                vector_dim=3072,
            )
            results = store.retrieve_filtered(
                query_vec=[0.05] * 3072,
                top_k=3,
                topic="CORS",
                category="Security",
                source_file="fastapi_cors.md",
                min_char_count=100,
            )
            assert len(results) == 1
            assert results[0]["chunk_id"] == "chunk_x"

            # Check that all SQL clauses and params were constructed
            last_call = mock_cursor.execute.call_args
            sql_text = last_call[0][0]
            sql_params = last_call[0][1]

            assert "topic ILIKE %(topic)s" in sql_text
            assert "category ILIKE %(category)s" in sql_text
            assert "source_file = %(source_file)s" in sql_text
            assert "char_count >= %(min_char)s" in sql_text
            assert sql_params["topic"] == "%CORS%"
            assert sql_params["category"] == "%Security%"
            assert sql_params["source_file"] == "fastapi_cors.md"
            assert sql_params["min_char"] == 100


