"""
tests/test_reviewer.py

Unit tests verifying the AI Reviewer Agent (app/reviewer.py) and FastAPI review endpoint.
Audits:
1. Grounded responses pass audit.
2. Ungrounded steps detected.
3. Hallucinated chunk citations detected.
4. Hallucinated code and security anti-patterns (CORS wildcard, SQL injections, deprecated imports).
5. Refusal correctness (out-of-bounds queries vs false refusals).
6. FastAPI review endpoint (/api/review).
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.schemas import NavigatorResponse, ActionableStep
from app.reviewer import ReviewerAgent, audit_response


@pytest.fixture
def sample_chunks():
    return [
        {
            "chunk_id": "fastapi_cors_chunk_1",
            "source_file": "fastapi_cors.md",
            "text": "Configure CORSMiddleware in FastAPI using app.add_middleware(CORSMiddleware, allow_origins=['http://localhost:3000'], allow_credentials=True).",
        },
        {
            "chunk_id": "fastapi_cors_chunk_2",
            "source_file": "fastapi_cors.md",
            "text": "Wildcard origins ('*') are strictly forbidden when allow_credentials is True by the CORS specification.",
        },
    ]


def test_reviewer_valid_grounded_response_passes(sample_chunks):
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Configure CORS in FastAPI by importing and mounting CORSMiddleware.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Mount CORSMiddleware",
                command="pip install fastapi uvicorn",
                explanation="Mount CORSMiddleware with explicit origin http://localhost:3000.",
                verification="python -m uvicorn main:app",
                citations=["fastapi_cors_chunk_1"],
            )
        ],
        anti_patterns_to_avoid=["Do not use wildcard origins when allowing credentials."],
        is_refusal=False,
        cited_chunk_ids=["fastapi_cors_chunk_1"],
    )

    result = reviewer.audit(
        query="How do I configure CORS for my React app?",
        response=resp,
        retrieved_chunks=sample_chunks,
    )

    assert result.is_valid is True
    assert result.verdict == "PASS"
    assert result.groundedness_score == 1.0
    assert result.faithfulness_score == 1.0
    assert result.overall_score >= 0.80
    assert len(result.hallucinated_code) == 0
    assert len(result.ungrounded_steps) == 0


def test_reviewer_detects_ungrounded_steps(sample_chunks):
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="CORS configuration advice without chunk citation.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Configure Middleware",
                command="npm install express",
                explanation="Set up your app without citing the source documentation.",
                verification="npm test",
                citations=[],  # Empty citations when retrieved context was provided!
            )
        ],
        anti_patterns_to_avoid=["Do not skip testing."],
        is_refusal=False,
        cited_chunk_ids=[],
    )

    result = reviewer.audit(
        query="How do I configure CORS?",
        response=resp,
        retrieved_chunks=sample_chunks,
    )

    assert 1 in result.ungrounded_steps
    assert result.groundedness_score == 0.0


def test_reviewer_detects_hallucinated_chunk_id(sample_chunks):
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Configuring CORS with a fabricated chunk citation.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Configure Middleware",
                command="python main.py",
                explanation="Reference nonexistent chunk.",
                verification="curl http://localhost:8000",
                citations=["fastapi_cors_chunk_9999"],  # Nonexistent chunk ID
            )
        ],
        anti_patterns_to_avoid=["Do not guess chunk IDs."],
        is_refusal=False,
        cited_chunk_ids=["fastapi_cors_chunk_9999"],
    )

    result = reviewer.audit(
        query="How do I configure CORS?",
        response=resp,
        retrieved_chunks=sample_chunks,
    )

    assert result.is_valid is False
    assert result.verdict == "FAIL"
    assert any("cites nonexistent" in h for h in result.hallucinated_code)


def test_reviewer_detects_cors_security_violation(sample_chunks):
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Wildcard CORS setup.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Set Wildcard with Credentials",
                command="python main.py",
                explanation="Configure allow_origins=['*'] with allow_credentials=True.",
                verification="curl http://localhost:8000",
                citations=["fastapi_cors_chunk_1"],
            )
        ],
        anti_patterns_to_avoid=["None."],
        is_refusal=False,
        cited_chunk_ids=["fastapi_cors_chunk_1"],
    )

    result = reviewer.audit(
        query="Can I use wildcard origins with cookies?",
        response=resp,
        retrieved_chunks=sample_chunks,
    )

    assert result.is_valid is False
    assert result.verdict == "FAIL"
    assert any("CORS violation" in h for h in result.hallucinated_code)


def test_reviewer_detects_deprecated_pydantic_basesettings():
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Configure app settings in Pydantic.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Import BaseSettings",
                command="python -c 'from pydantic import BaseSettings'",
                explanation="from pydantic import BaseSettings is used for env loading.",
                verification="python config.py",
                citations=["pydantic_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["Do not hardcode secrets."],
        is_refusal=False,
        cited_chunk_ids=["pydantic_chunk_0"],
    )

    result = reviewer.audit(
        query="How to load settings in Pydantic v2?",
        response=resp,
        retrieved_chunks=[{"chunk_id": "pydantic_chunk_0", "text": "pydantic documentation"}],
    )

    assert result.is_valid is False
    assert any("BaseSettings was moved to 'pydantic_settings'" in h for h in result.hallucinated_code)


def test_reviewer_proper_refusal_passes():
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="This question is out-of-scope for the verified technical documentation.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Consult Professional Guidance",
                command="echo 'out of scope'",
                explanation="Consult career mentors for subjective salary discussions.",
                verification="Review contracts independently.",
                citations=[],
            )
        ],
        anti_patterns_to_avoid=[],
        is_refusal=True,
        refusal_reason="Question is out-of-corpus and cannot be verified.",
        cited_chunk_ids=[],
    )

    out_of_bounds_chunk = [
        {"chunk_id": "out_of_bounds", "text": "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]"}
    ]

    result = reviewer.audit(
        query="Should I choose offer A or offer B?",
        response=resp,
        retrieved_chunks=out_of_bounds_chunk,
    )

    assert result.is_valid is True
    assert result.verdict == "PASS"
    assert result.overall_score == 1.0


def test_fastapi_review_endpoint(sample_chunks):
    client = TestClient(app)
    payload = {
        "query": "How do I configure CORS for my React app?",
        "response": {
            "summary": "Configure CORS by mounting CORSMiddleware on FastAPI.",
            "action_plan": [
                {
                    "step_number": 1,
                    "title": "Mount CORSMiddleware",
                    "command": "pip install fastapi uvicorn",
                    "explanation": "Add CORSMiddleware with specific origins.",
                    "verification": "python -m uvicorn main:app",
                    "citations": ["fastapi_cors_chunk_1"],
                }
            ],
            "anti_patterns_to_avoid": ["Do not use wildcard with credentials."],
            "is_refusal": False,
            "cited_chunk_ids": ["fastapi_cors_chunk_1"],
        },
        "retrieved_chunks": sample_chunks,
    }

    res = client.post("/api/review", json=payload)
    assert res.status_code == 200
    data = res.json()
    assert data["is_valid"] is True
    assert data["verdict"] == "PASS"
    assert data["groundedness_score"] == 1.0
    assert "feedback" in data
