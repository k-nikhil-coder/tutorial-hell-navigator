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



def test_query_logging_end_to_end(client, tmp_path, monkeypatch):
    """A1 Check 1: Verify trajectory logging works end to end with all telemetry metrics."""
    test_traj_file = tmp_path / "test_trajectories.jsonl"
    monkeypatch.setattr("app.telemetry.TRAJECTORY_LOG_FILE", test_traj_file)

    from app.telemetry import log_query_trajectory
    record = log_query_trajectory(
        query="How do I configure CORS in FastAPI?",
        retrieved_chunks=[
            {"chunk_id": "fastapi_cors_chunk_1", "source_file": "fastapi_cors.md", "score": 0.92}
        ],
        response_summary="Add CORSMiddleware with allowed origins.",
        is_refusal=False,
        cited_chunk_ids=["fastapi_cors_chunk_1"],
        latency_ms=125.4,
        topic="fastapi",
        retrieval_ms=15.2,
        rerank_ms=45.8,
        ttft_ms=64.1,
        prompt_tokens=450,
        completion_tokens=180,
    )

    assert test_traj_file.exists()

    res = client.get("/telemetry/trajectories?limit=10")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] >= 1
    recent = data["trajectories"][-1]

    assert recent["query"] == "How do I configure CORS in FastAPI?"
    assert recent["topic"] == "fastapi"
    assert recent["retrieval_ms"] == 15.2
    assert recent["rerank_ms"] == 45.8
    assert recent["ttft_ms"] == 64.1
    assert recent["prompt_tokens"] == 450
    assert recent["completion_tokens"] == 180
    assert recent["cited_chunk_ids"] == ["fastapi_cors_chunk_1"]


def test_consent_notice_rendered_end_to_end(client):
    """A1 Check 2: Verify consent notice banner and dismissal button render end to end."""
    res = client.get("/")
    assert res.status_code == 200
    html = res.text

    assert 'id="consent-banner"' in html
    assert "Anonymous Evaluation Notice" in html
    assert "logs query benchmarks and unstick ratings" in html
    assert "acceptConsent" in html
    assert "I Understand" in html

    res_chat = client.get("/chat")
    assert res_chat.status_code == 200
    assert 'id="consent-banner"' in res_chat.text


def test_unstick_button_submission_and_summary_end_to_end(client, tmp_path, monkeypatch):
    """A1 Check 3: Verify 'Did this unstick you?' prompt in UI and feedback submission end to end."""
    # 1. UI renders unstick card and buttons
    ui_res = client.get("/")
    assert ui_res.status_code == 200
    assert "unstick-card" in ui_res.text
    assert "Did this explanation unstick you?" in ui_res.text
    assert "recordUnstick" in ui_res.text

    # 2. End-to-end feedback logging and summary updates
    test_feedback_file = tmp_path / "feedback_unstick_e2e.jsonl"
    monkeypatch.setattr("app.telemetry.FEEDBACK_LOG_FILE", test_feedback_file)

    post_yes = client.post("/api/feedback", json={
        "query": "PostgreSQL deadlock resolution",
        "unstuck": True,
        "rating": "positive",
        "session_id": "e2e_student_1",
    })
    assert post_yes.status_code == 200

    post_no = client.post("/api/feedback", json={
        "query": "Docker mount permission issue",
        "unstuck": False,
        "rating": "negative",
        "session_id": "e2e_student_2",
    })
    assert post_no.status_code == 200

    sum_res = client.get("/api/feedback/summary")
    assert sum_res.status_code == 200
    summary = sum_res.json()
    assert summary["total_records"] == 2
    assert summary["unstuck_count"] == 1
    assert summary["stuck_count"] == 1
    assert summary["unstick_rate_percent"] == 50.0


def test_tunnel_security_controls_end_to_end(client, monkeypatch):
    """A4: Verify tunnel invite code, per-IP rate limit, and daily request cap."""
    tunnel_headers = {"X-Forwarded-Host": "tutorial-navigator.ngrok-free.app"}

    # 1. Missing invite code -> 401
    res_no_code = client.get("/api", headers=tunnel_headers)
    assert res_no_code.status_code == 401
    assert "invite code" in res_no_code.json()["detail"]

    # 2. Invalid invite code -> 401
    res_bad_code = client.get("/api", headers={**tunnel_headers, "X-Invite-Code": "WRONG_CODE"})
    assert res_bad_code.status_code == 401

    # 3. Valid invite code -> 200
    valid_headers = {
        **tunnel_headers,
        "X-Invite-Code": "NAVIGATOR2026",
        "X-Forwarded-For": "203.0.113.195",
    }
    res_valid = client.get("/api", headers=valid_headers)
    assert res_valid.status_code == 200

    # 4. Per-IP rate limiting (limit to 3 requests for testing)
    monkeypatch.setenv("TUNNEL_RATE_LIMIT_PER_MINUTE", "3")
    ip_headers = {
        **tunnel_headers,
        "X-Invite-Code": "NAVIGATOR2026",
        "X-Forwarded-For": "203.0.113.42",
    }
    for _ in range(3):
        res = client.get("/api", headers=ip_headers)
        assert res.status_code == 200
    res_limited = client.get("/api", headers=ip_headers)
    assert res_limited.status_code == 429
    assert "rate limit exceeded" in res_limited.json()["detail"].lower()

    # 5. Daily request cap
    monkeypatch.setenv("TUNNEL_DAILY_REQUEST_CAP", "1")
    cap_headers = {
        **tunnel_headers,
        "X-Invite-Code": "NAVIGATOR2026",
        "X-Forwarded-For": "198.51.100.99",
    }
    from app.main import _tunnel_daily_counts
    from datetime import datetime, timezone
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    _tunnel_daily_counts[today_str] = 1

    res_capped = client.get("/api", headers=cap_headers)
    assert res_capped.status_code == 429
    assert "daily request cap reached" in res_capped.json()["detail"].lower()
