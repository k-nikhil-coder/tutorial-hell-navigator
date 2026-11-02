import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.telemetry import FEEDBACK_LOG_FILE


@pytest.fixture
def client():
    return TestClient(app)


def test_serve_chat_ui(client):
    """Verify that root GET / and /chat serve the frontend single-page HTML application."""
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers.get("content-type", "")
    assert "Tutorial Hell Navigator" in response.text
    assert "Grounded against Tier 1 Corpus" in response.text

    chat_response = client.get("/chat")
    assert chat_response.status_code == 200
    assert "Tutorial Hell Navigator" in chat_response.text


def test_feedback_submission_and_retrieval(client, tmp_path, monkeypatch):
    """Verify POST /api/feedback records positive/negative ratings and comments."""
    test_feedback_file = tmp_path / "feedback.jsonl"
    monkeypatch.setattr("app.telemetry.FEEDBACK_LOG_FILE", test_feedback_file)

    payload = {
        "query": "Why does CORS fail with allow_origins=['*'] and allow_credentials=True?",
        "rating": "positive",
        "comment": "Explained the browser W3C credential restriction clearly.",
        "cited_chunk_ids": ["fastapi_cors_chunk_1"],
    }

    # Submit feedback
    post_res = client.post("/api/feedback", json=payload)
    assert post_res.status_code == 200
    assert post_res.json()["status"] == "ok"

    # Verify retrieval
    get_res = client.get("/api/feedback")
    assert get_res.status_code == 200
    data = get_res.json()
    assert data["count"] >= 1
    recent = data["feedback"][-1]
    assert recent["rating"] == "positive"
    assert recent["query"] == payload["query"]
    assert recent["comment"] == payload["comment"]
    assert recent["cited_chunk_ids"] == ["fastapi_cors_chunk_1"]


def test_feedback_validation_errors(client):
    """Verify validation on empty query or invalid fields."""
    bad_payload = {
        "query": "",  # min_length is 1
        "rating": "positive",
    }
    res = client.post("/api/feedback", json=bad_payload)
    assert res.status_code == 422


def test_chunk_details_inspection(client):
    """Verify GET /api/chunks/{chunk_id} returns verbatim text and metadata for citation chips."""
    # Test valid chunk
    res = client.get("/api/chunks/docker_compose_best_practices_chunk_0")
    assert res.status_code == 200
    data = res.json()
    assert data["chunk_id"] == "docker_compose_best_practices_chunk_0"
    assert "docker_compose_best_practices.md" in data["source_file"]
    assert len(data["text"]) > 10

    # Test missing chunk
    res_404 = client.get("/api/chunks/non_existent_chunk_id_xyz")
    assert res_404.status_code == 404


def test_unstick_metric_feedback_summary(client, tmp_path, monkeypatch):
    """Verify 'Did this unstick you?' metric logging and summary calculations."""
    test_feedback_file = tmp_path / "feedback_unstick.jsonl"
    monkeypatch.setattr("app.telemetry.FEEDBACK_LOG_FILE", test_feedback_file)

    # 1. Unstuck YES
    client.post("/api/feedback", json={
        "query": "CORS credentials error",
        "unstuck": True,
        "rating": "positive",
        "session_id": "anon_user_1",
    })

    # 2. Unstuck NO
    client.post("/api/feedback", json={
        "query": "Docker Postgres race condition",
        "unstuck": False,
        "rating": "negative",
        "comment": "Container kept crashing anyway",
        "session_id": "anon_user_2",
    })

    # 3. Another Unstuck YES
    client.post("/api/feedback", json={
        "query": "Pydantic validator syntax",
        "unstuck": True,
        "rating": "positive",
        "session_id": "anon_user_3",
    })

    # Verify summary calculation: 2 unstuck out of 3 total = 66.7%
    sum_res = client.get("/api/feedback/summary")
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert summary["total_records"] == 3
    assert summary["unstuck_count"] == 2
    assert summary["stuck_count"] == 1
    assert summary["unstick_rate_percent"] == 66.7
    assert summary["positive_ratings"] == 2
    assert summary["negative_ratings"] == 1
