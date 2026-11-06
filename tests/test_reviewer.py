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


def test_reviewer_detects_sql_injection():
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Query users with string interpolation directly.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Execute Query",
                command="python query.py",
                explanation="Run cursor.execute(f'SELECT * FROM users WHERE id = {user_id}') directly.",
                verification="python query.py",
                citations=["sql_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["Do not skip error checks."],
        is_refusal=False,
        cited_chunk_ids=["sql_chunk_0"],
    )

    result = reviewer.audit(
        query="How do I query a user by ID in psycopg2?",
        response=resp,
        retrieved_chunks=[{"chunk_id": "sql_chunk_0", "text": "Always use parameterized queries."}],
    )

    assert result.is_valid is False
    assert result.verdict == "FAIL"
    assert result.code_correctness_score == 0.0
    assert any("SQL injection risk" in h for h in result.hallucinated_code)


def test_reviewer_detects_git_secret_commit():
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Save passwords directly in git repository.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Commit passwords",
                command="git add docker-compose.yml && git commit -m 'save password'",
                explanation="Putting POSTGRES_PASSWORD=secret in git is convenient.",
                verification="git status",
                citations=["docker_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["None."],
        is_refusal=False,
        cited_chunk_ids=["docker_chunk_0"],
    )

    result = reviewer.audit(
        query="How should I configure environment variables in Docker?",
        response=resp,
        retrieved_chunks=[{"chunk_id": "docker_chunk_0", "text": "Keep .env in .gitignore."}],
    )

    assert result.is_valid is False
    assert result.verdict == "FAIL"
    assert any("Security violation: committing raw credentials" in h for h in result.hallucinated_code)


def test_reviewer_detects_rollback_suppression():
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Do not rollback on transaction errors.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Ignore errors",
                command="python script.py",
                explanation="Never call conn.rollback(). Just keep executing queries.",
                verification="echo ok",
                citations=["pg_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["None."],
        is_refusal=False,
        cited_chunk_ids=["pg_chunk_0"],
    )

    result = reviewer.audit(
        query="How do you handle transaction failures in psycopg2?",
        response=resp,
        retrieved_chunks=[{"chunk_id": "pg_chunk_0", "text": "Always call conn.rollback() in the exception handler."}],
    )

    assert result.is_valid is False
    assert result.verdict == "FAIL"
    assert any("Database integrity risk: suppressing conn.rollback()" in h for h in result.hallucinated_code)


def test_reviewer_detects_pgvector_dimension_contradiction():
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="pgvector supports huge dimensions.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Index Large Vectors",
                command="CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops);",
                explanation="standard vector(3072) supports HNSW indexes with up to 10,000 dimensions.",
                verification="SELECT 1;",
                citations=["pgvector_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["None."],
        is_refusal=False,
        cited_chunk_ids=["pgvector_chunk_0"],
    )

    result = reviewer.audit(
        query="Can standard vector(3072) be indexed with HNSW?",
        response=resp,
        retrieved_chunks=[{"chunk_id": "pgvector_chunk_0", "text": "Standard pgvector vector type has an HNSW index limit of 2,000 dimensions."}],
    )

    assert result.is_valid is False
    assert result.verdict == "FAIL"
    assert any("2,000 dimensions" in h for h in result.hallucinated_code)


def test_reviewer_accepts_safe_commands_with_env_vars():
    reviewer = ReviewerAgent()
    resp = NavigatorResponse(
        summary="Run migration with environment variable.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Run Migration",
                command="DATABASE_URL=postgresql://localhost:5432/db alembic upgrade head",
                explanation="Apply the database migrations.",
                verification="echo done",
                citations=["alembic_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["Do not skip migrations."],
        is_refusal=False,
        cited_chunk_ids=["alembic_chunk_0"],
    )

    result = reviewer.audit(
        query="How do I run Alembic migrations with custom database URL?",
        response=resp,
        retrieved_chunks=[{"chunk_id": "alembic_chunk_0", "text": "alembic upgrade head"}],
    )

    assert result.is_valid is True
    assert result.verdict == "PASS"
    assert len(result.hallucinated_code) == 0

