import pytest
import httpx
from pathlib import Path
from qdrant_client.models import PointStruct, Distance, VectorParams

from app.schemas import ActionableStep, NavigatorResponse
from app.rag import (
    get_qdrant_client,
    ensure_collection,
    format_retrieved_context,
    get_indexed_count,
    COLLECTION_NAME,
)
from app.telemetry import log_query_trajectory, get_recent_trajectories
from app.main import app


def test_schema_citations_and_refusal_fields():
    step = ActionableStep(
        step_number=1,
        title="Configure CORS",
        command="app.add_middleware(CORSMiddleware)",
        explanation="Permits cross-origin browser requests.",
        citations=["fastapi_guide_chunk_2"],
    )
    assert step.citations == ["fastapi_guide_chunk_2"]

    response = NavigatorResponse(
        summary="CORS is blocked due to missing middleware.",
        action_plan=[step],
        anti_patterns_to_avoid=["Allowing wildcard origins in production"],
        is_refusal=False,
        cited_chunk_ids=["fastapi_guide_chunk_2"],
    )
    assert not response.is_refusal
    assert response.cited_chunk_ids == ["fastapi_guide_chunk_2"]


def test_refusal_schema_defaults():
    response = NavigatorResponse(
        summary="Question is outside the indexed software engineering corpus.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Consult Relevant Domain Documentation",
                explanation="This system only grounds answers in verified engineering docs.",
            )
        ],
        anti_patterns_to_avoid=["Hallucinating ungrounded commands"],
        is_refusal=True,
        refusal_reason="Out-of-corpus query",
    )
    assert response.is_refusal is True
    assert response.refusal_reason == "Out-of-corpus query"
    assert response.cited_chunk_ids == []


def test_format_retrieved_context():
    sample_chunks = [
        {
            "chunk_id": "fastapi_chunk_0",
            "source_file": "fastapi_guide.md",
            "text": "FastAPI provides built-in CORS support.",
        },
        {
            "chunk_id": "docker_chunk_1",
            "source_file": "docker_guide.pdf",
            "text": "Use multi-stage builds for lean containers.",
        },
    ]

    formatted = format_retrieved_context(sample_chunks)
    assert "[CHUNK_ID: fastapi_chunk_0]" in formatted
    assert "[CHUNK_ID: docker_chunk_1]" in formatted
    assert "Source: fastapi_guide.md" in formatted
    assert "FastAPI provides built-in CORS support." in formatted

    empty_formatted = format_retrieved_context([])
    assert "NO RELEVANT CONTEXT FOUND" in empty_formatted


def test_qdrant_in_memory_collection():
    client = get_qdrant_client(in_memory=True)
    test_collection = "test_memory_collection"

    ensure_collection(client, collection_name=test_collection, vector_size=4)
    assert client.collection_exists(test_collection)

    # Upsert test points
    points = [
        PointStruct(id=1, vector=[1.0, 0.0, 0.0, 0.0], payload={"chunk_id": "c1", "text": "First chunk"}),
        PointStruct(id=2, vector=[0.0, 1.0, 0.0, 0.0], payload={"chunk_id": "c2", "text": "Second chunk"}),
    ]
    client.upsert(collection_name=test_collection, points=points)

    info = client.get_collection(test_collection)
    assert info.points_count == 2

    # Query nearest neighbor
    results = client.query_points(
        collection_name=test_collection,
        query=[0.9, 0.1, 0.0, 0.0],
        limit=1,
    )
    assert len(results.points) == 1
    assert results.points[0].payload["chunk_id"] == "c1"


def test_telemetry_logging_and_retrieval(tmp_path, monkeypatch):
    test_log_file = tmp_path / "test_trajectories.jsonl"
    monkeypatch.setattr("app.telemetry.LOGS_DIR", tmp_path)
    monkeypatch.setattr("app.telemetry.TRAJECTORY_LOG_FILE", test_log_file)

    log_query_trajectory(
        query="How to configure PostgreSQL pool in FastAPI?",
        retrieved_chunks=[{"chunk_id": "db_chunk_3", "source_file": "db.md", "score": 0.88}],
        response_summary="Use asyncpg pool with connection lifecycle management.",
        is_refusal=False,
        cited_chunk_ids=["db_chunk_3"],
        latency_ms=142.5,
    )

    log_query_trajectory(
        query="How to bake a chocolate cake?",
        retrieved_chunks=[],
        response_summary="Out-of-corpus query refused.",
        is_refusal=True,
        cited_chunk_ids=[],
        latency_ms=45.2,
        refusal_reason="Out-of-corpus query",
    )

    records = get_recent_trajectories(limit=10)
    assert len(records) == 2
    assert records[0]["query"] == "How to configure PostgreSQL pool in FastAPI?"
    assert records[0]["is_refusal"] is False
    assert records[0]["cited_chunk_ids"] == ["db_chunk_3"]
    assert records[1]["is_refusal"] is True
    assert records[1]["refusal_reason"] == "Out-of-corpus query"


def test_get_indexed_count():
    count = get_indexed_count()
    assert isinstance(count, int)
    assert count >= 0


@pytest.mark.asyncio
async def test_health_endpoint_rag_metadata():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "indexed_chunks" in data
        assert data["vector_store"] == "Qdrant"
        assert data["indexed_chunks"] >= 0


@pytest.mark.asyncio
async def test_telemetry_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/telemetry/trajectories?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "count" in data
        assert "trajectories" in data
        assert isinstance(data["trajectories"], list)


def test_render_yaml_configuration():
    render_path = Path(__file__).resolve().parent.parent / "render.yaml"
    assert render_path.exists()
    content = render_path.read_text(encoding="utf-8")
    assert "tutorial-hell-navigator" in content
    assert "mountPath: /app/data" in content
    assert "healthCheckPath: /health" in content


def test_eval_report_baseline_metrics():
    report_path = Path(__file__).resolve().parent.parent / "eval" / "eval_report.json"
    assert report_path.exists()
    import json
    with open(report_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert data["total_evaluated"] >= 5
    assert data["pass_rate"] >= 80.0
    assert "avg_steps_per_plan" in data["metrics"]
    assert "avg_citations_per_plan" in data["metrics"]
