import pytest
import httpx
from pydantic import ValidationError

from app.schemas import (
    ActionableStep,
    NavigatorResponse,
    QueryRequest,
    HealthStatus,
)
from app.tools import (
    search_error_catalog,
    get_project_milestones,
    get_architecture_blueprint,
    AVAILABLE_TOOLS,
)
from app.client import (
    is_transient_error,
    clean_json_text,
    GLOBAL_SEMAPHORE,
    generate_structured_response_async,
    stream_response_sse,
)
from app.main import app
from benchmarks.load_test import calculate_percentile


def test_actionable_step_validation():
    step = ActionableStep(
        step_number=1,
        title="Install libpq-dev",
        command="apt-get install -y libpq-dev gcc",
        explanation="Compiles native C extensions for psycopg2.",
        verification="python -c 'import psycopg2'",
    )
    assert step.step_number == 1
    assert step.command is not None

    with pytest.raises(ValidationError):
        ActionableStep(
            step_number=0,
            title="Invalid",
            explanation="Bad step",
        )


def test_navigator_response_schema():
    sample_json = {
        "summary": "Fix PostgreSQL build errors in Docker container.",
        "action_plan": [
            {
                "step_number": 1,
                "title": "Add dependencies",
                "command": "apt-get install -y gcc libpq-dev",
                "explanation": "Provides headers for psycopg2 compilation.",
            }
        ],
        "anti_patterns_to_avoid": [
            "Never use root credentials in database connection URLs in production.",
            "Do not install dependencies after copying application code.",
        ],
        "architecture_contract": "Clean separation between DB layer and API routes.",
        "key_takeaway": "Always verify native header requirements when containerizing C packages.",
    }
    model = NavigatorResponse.model_validate(sample_json)
    assert model.summary.startswith("Fix PostgreSQL")
    assert len(model.action_plan) == 1
    assert len(model.anti_patterns_to_avoid) == 2


def test_navigator_response_rejects_empty_plans():
    with pytest.raises(ValidationError):
        NavigatorResponse(
            summary="Empty plan test",
            action_plan=[],
            anti_patterns_to_avoid=["Bad practice"],
        )


def test_search_error_catalog_psycopg2():
    res = search_error_catalog("psycopg2.OperationalError: could not connect to server")
    assert res["found"] is True
    assert "libpq" in res["cli_remediation"].lower()
    assert "fix" in res


def test_search_error_catalog_cors():
    res = search_error_catalog("Access-Control-Allow-Origin header is missing in preflight")
    assert res["found"] is True
    assert "CORSMiddleware" in res["fix"]


def test_search_error_catalog_unknown():
    res = search_error_catalog("random_unseen_runtime_error_123")
    assert res["found"] is False
    assert "details" in res


def test_get_project_milestones():
    res = get_project_milestones("fastapi")
    assert res["found"] is True
    assert len(res["milestones"]) >= 4
    assert any("Schema" in m or "Pydantic" in m for m in res["milestones"])


def test_get_architecture_blueprint():
    res = get_architecture_blueprint("clean_architecture")
    assert res["found"] is True
    assert "app/" in res["blueprint"]["directory_tree"]


def test_clean_json_text():
    raw = "```json\n{\"test\": 123}\n```"
    assert clean_json_text(raw) == "{\"test\": 123}"


def test_is_transient_error_detection():
    assert is_transient_error(Exception("503 Service Unavailable")) is True
    assert is_transient_error(Exception("Resource_Exhausted rate limit reached")) is True
    assert is_transient_error(Exception("SyntaxError in user script")) is False


def test_calculate_percentile():
    data = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0, 100.0]
    assert calculate_percentile(data, 50) == 55.0
    assert calculate_percentile(data, 90) == 91.0


@pytest.mark.asyncio
async def test_api_health_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "healthy"
        assert "concurrency_limit" in data
        assert len(data["available_tools"]) >= 3


@pytest.mark.asyncio
async def test_api_streaming_endpoint():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=30.0) as client:
        async with client.stream("POST", "/navigate/stream", json={"query": "How to resolve CORS in FastAPI"}) as resp:
            assert resp.status_code == 200
            assert "text/event-stream" in resp.headers.get("content-type", "")
            lines = [line async for line in resp.aiter_lines() if line]
            assert len(lines) > 0
            assert any("data:" in line for line in lines)
            assert any("[DONE]" in line for line in lines)


@pytest.mark.asyncio
async def test_api_structured_navigation():
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test", timeout=45.0) as client:
        resp = await client.post("/navigate", json={"query": "How do I fix a CORS error in FastAPI?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "action_plan" in data
        assert len(data["action_plan"]) >= 1
        assert "anti_patterns_to_avoid" in data
        assert len(data["anti_patterns_to_avoid"]) >= 1
