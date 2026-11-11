import time
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.schemas import NavigatorResponse, ActionableStep
from app.client import (
    USER_FACING_REFUSAL_MESSAGE,
    INTERNAL_REFUSAL_PHRASES,
    sanitize_refusal_response,
    generate_structured_response_async,
    _execute_chat_with_fallback,
    count_tokens,
)
from app.telemetry import log_query_trajectory, get_recent_trajectories
from app.main import app


def test_user_facing_refusal_message_definition():
    """Verify standard user-facing refusal message is defined and non-empty."""
    assert USER_FACING_REFUSAL_MESSAGE
    assert "outside the scope of the verified technical documentation" in USER_FACING_REFUSAL_MESSAGE
    assert "consult official documentation" in USER_FACING_REFUSAL_MESSAGE.lower()


def test_sanitize_refusal_response_clears_citations():
    """Verify refusal response forces cited_chunk_ids and step citations to empty lists."""
    raw_response = NavigatorResponse(
        summary="Initial summary before sanitization",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Search Docs",
                explanation="Consult official FastAPI documentation.",
                command=None,
                verification="Check docs site",
                citations=["fastapi_guide_chunk_0", "fastapi_guide_chunk_1"],
            )
        ],
        anti_patterns_to_avoid=["Hallucinating configurations"],
        is_refusal=True,
        refusal_reason="Out of corpus",
        cited_chunk_ids=["fastapi_guide_chunk_0"],
    )

    sanitized = sanitize_refusal_response(raw_response)

    assert sanitized.is_refusal is True
    assert sanitized.cited_chunk_ids == []
    for step in sanitized.action_plan:
        assert step.citations == []


def test_sanitize_refusal_response_scrubs_internal_phrases():
    """Verify internal debug phrases are completely eliminated and replaced with clean message."""
    raw_response = NavigatorResponse(
        summary="The provided verified context is empty and out-of-bounds. Therefore, an out-of-corpus refusal triggered.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Notice: Out-of-corpus refusal triggered",
                explanation="Since the verified context is empty, an out-of-corpus refusal is triggered. Refer to standard docs.",
                command="echo 'verified context is empty'",
                verification="Verify that out-of-corpus refusal was handled.",
                citations=["dummy_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=[
            "Ignoring strict out-of-corpus refusal rules",
            "Trusting unverified advice",
        ],
        key_takeaway="An out-of-corpus refusal has been triggered.",
        is_refusal=True,
        refusal_reason="Initial internal reason",
    )

    sanitized = sanitize_refusal_response(raw_response)

    # 1. Summary and refusal_reason must match clean user-facing guidance
    assert sanitized.summary == USER_FACING_REFUSAL_MESSAGE
    assert sanitized.refusal_reason == "Question is outside the scope of the verified technical documentation."

    # 2. Citations must be completely empty
    assert sanitized.cited_chunk_ids == []
    assert sanitized.action_plan[0].citations == []

    # 3. Check all fields for absence of internal debug phrases
    all_text = (
        sanitized.summary
        + " "
        + sanitized.refusal_reason
        + " "
        + sanitized.action_plan[0].title
        + " "
        + sanitized.action_plan[0].explanation
        + " "
        + (sanitized.action_plan[0].command or "")
        + " "
        + (sanitized.action_plan[0].verification or "")
        + " "
        + (sanitized.key_takeaway or "")
        + " "
        + " ".join(sanitized.anti_patterns_to_avoid)
    ).lower()

    for phrase in INTERNAL_REFUSAL_PHRASES:
        assert phrase.lower() not in all_text, f"Internal phrase '{phrase}' leaked into sanitized refusal"

    assert "verified context is empty" not in all_text
    assert "out-of-corpus refusal triggered" not in all_text


def test_sanitize_refusal_response_ensures_advisory_step_and_antipatterns():
    """Verify fallback defaults if model generated empty action_plan or empty anti_patterns."""
    raw_response = NavigatorResponse(
        summary="Some refusal summary",
        action_plan=[],
        anti_patterns_to_avoid=[],
        is_refusal=True,
    )

    sanitized = sanitize_refusal_response(raw_response)

    assert sanitized.is_refusal is True
    assert len(sanitized.action_plan) >= 1
    assert sanitized.action_plan[0].citations == []
    assert len(sanitized.anti_patterns_to_avoid) >= 1
    assert sanitized.summary == USER_FACING_REFUSAL_MESSAGE


@pytest.mark.asyncio
async def test_token_accounting_gemini_metadata_object():
    """Verify token accounting consumes Gemini usage metadata object and sets token_source='gemini'."""
    sample_response = NavigatorResponse(
        summary="Configure CORS using CORSMiddleware.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Add Middleware",
                explanation="Import and attach CORSMiddleware to your FastAPI app.",
                command="pip install fastapi",
                verification="curl -I http://localhost:8000",
                citations=["fastapi_guide_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["Wildcard origins with allow_credentials=True"],
        is_refusal=False,
    )

    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 142
    mock_usage.candidates_token_count = 68

    with patch(
        "app.client._execute_chat_with_fallback",
        new=AsyncMock(return_value=(sample_response.model_dump_json(), 45.0, mock_usage)),
    ), patch(
        "app.client.retrieve_relevant_chunks_async",
        new=AsyncMock(return_value=[{"chunk_id": "fastapi_guide_chunk_0", "score": 0.85, "retrieval_method": "dense"}]),
    ):
        result = await generate_structured_response_async("How to configure CORS in FastAPI?")

        assert getattr(result, "_prompt_tokens", None) == 142
        assert getattr(result, "_completion_tokens", None) == 68
        assert getattr(result, "_token_source", None) == "gemini"
        assert result.cited_chunk_ids == ["fastapi_guide_chunk_0"]


@pytest.mark.asyncio
async def test_token_accounting_gemini_metadata_dict():
    """Verify token accounting consumes Gemini usage metadata as dictionary and sets token_source='gemini'."""
    sample_response = NavigatorResponse(
        summary="Configure Docker multi-stage builds.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Create Dockerfile",
                explanation="Define builder stage and runtime stage.",
                command="docker build -t app .",
                verification="docker images",
                citations=["docker_guide_chunk_1"],
            )
        ],
        anti_patterns_to_avoid=["Leaving build tools in production image"],
        is_refusal=False,
    )

    mock_usage = {
        "prompt_token_count": 210,
        "candidates_token_count": 95,
    }

    with patch(
        "app.client._execute_chat_with_fallback",
        new=AsyncMock(return_value=(sample_response.model_dump_json(), 50.0, mock_usage)),
    ), patch(
        "app.client.retrieve_relevant_chunks_async",
        new=AsyncMock(return_value=[{"chunk_id": "docker_guide_chunk_1", "score": 0.90, "retrieval_method": "dense"}]),
    ):
        result = await generate_structured_response_async("How to build lean Docker containers?")

        assert getattr(result, "_prompt_tokens", None) == 210
        assert getattr(result, "_completion_tokens", None) == 95
        assert getattr(result, "_token_source", None) == "gemini"


@pytest.mark.asyncio
async def test_token_accounting_fallback_to_tiktoken_when_none():
    """Verify token accounting falls back to tiktoken when metadata is absent, setting token_source='tiktoken'."""
    sample_response = NavigatorResponse(
        summary="Configure Docker multi-stage builds.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Build Stage",
                explanation="Compile assets in builder image.",
                command="docker build -t test .",
                verification="docker run test",
                citations=[],
            )
        ],
        anti_patterns_to_avoid=["Running as root"],
        is_refusal=False,
    )

    with patch(
        "app.client._execute_chat_with_fallback",
        new=AsyncMock(return_value=(sample_response.model_dump_json(), 55.0, None)),
    ), patch(
        "app.client.retrieve_relevant_chunks_async",
        new=AsyncMock(return_value=[{"chunk_id": "docker_guide_chunk_1", "score": 0.88, "retrieval_method": "dense"}]),
    ):
        result = await generate_structured_response_async("How to build Docker image?")

        assert getattr(result, "_token_source", None) == "tiktoken"
        assert isinstance(getattr(result, "_prompt_tokens", None), int)
        assert getattr(result, "_prompt_tokens") > 0
        assert isinstance(getattr(result, "_completion_tokens", None), int)
        assert getattr(result, "_completion_tokens") > 0


def test_telemetry_records_token_source(tmp_path, monkeypatch):
    """Verify log_query_trajectory records token_source in trajectory record and log file."""
    test_traj_file = tmp_path / "test_trajectories.jsonl"
    monkeypatch.setattr("app.telemetry.LOGS_DIR", tmp_path)
    monkeypatch.setattr("app.telemetry.TRAJECTORY_LOG_FILE", test_traj_file)

    rec1 = log_query_trajectory(
        query="CORS query",
        retrieved_chunks=[],
        response_summary="summary",
        is_refusal=False,
        cited_chunk_ids=[],
        latency_ms=100.0,
        prompt_tokens=150,
        completion_tokens=50,
        token_source="gemini",
    )
    assert rec1["token_source"] == "gemini"

    rec2 = log_query_trajectory(
        query="Cake query",
        retrieved_chunks=[],
        response_summary="refusal",
        is_refusal=True,
        cited_chunk_ids=[],
        latency_ms=40.0,
        prompt_tokens=80,
        completion_tokens=30,
        token_source="tiktoken",
    )
    assert rec2["token_source"] == "tiktoken"

    recent = get_recent_trajectories(limit=10)
    assert len(recent) == 2
    assert recent[0]["token_source"] == "gemini"
    assert recent[1]["token_source"] == "tiktoken"


def test_navigate_endpoint_records_token_source(tmp_path, monkeypatch):
    """Verify POST /navigate extracts token_source from response and records in telemetry."""
    test_traj_file = tmp_path / "test_trajectories.jsonl"
    monkeypatch.setattr("app.telemetry.LOGS_DIR", tmp_path)
    monkeypatch.setattr("app.telemetry.TRAJECTORY_LOG_FILE", test_traj_file)

    mock_resp = NavigatorResponse(
        summary="CORS config guidance.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Add CORS",
                explanation="Use CORSMiddleware.",
                command="pip install fastapi",
                verification="pytest",
                citations=["fastapi_chunk_0"],
            )
        ],
        anti_patterns_to_avoid=["Allow all origins"],
        is_refusal=False,
        cited_chunk_ids=["fastapi_chunk_0"],
    )
    object.__setattr__(mock_resp, "_prompt_tokens", 333)
    object.__setattr__(mock_resp, "_completion_tokens", 111)
    object.__setattr__(mock_resp, "_token_source", "gemini")
    object.__setattr__(mock_resp, "_retrieved_chunks", [])
    object.__setattr__(mock_resp, "_topic", "fastapi")
    object.__setattr__(mock_resp, "_retrieval_ms", 12.0)
    object.__setattr__(mock_resp, "_rerank_ms", 20.0)
    object.__setattr__(mock_resp, "_ttft_ms", 45.0)

    with patch("app.main.generate_structured_response_async", new=AsyncMock(return_value=mock_resp)):
        client = TestClient(app)
        res = client.post("/navigate", json={"query": "How to handle CORS in FastAPI?"})
        assert res.status_code == 200

        recent = get_recent_trajectories(limit=5)
        assert len(recent) >= 1
        last = recent[-1]
        assert last["token_source"] == "gemini"
        assert last["prompt_tokens"] == 333
        assert last["completion_tokens"] == 111


@pytest.mark.asyncio
async def test_ungrounded_query_automatic_refusal_sanitization():
    """Verify that when retrieved context is ungrounded (score < 0.40), response is sanitized with zero citations."""
    leaky_response = NavigatorResponse(
        summary="The provided verified context is empty. Out-of-corpus refusal triggered.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Out-of-corpus refusal",
                explanation="The verified context is empty and out-of-bounds. Consult python docs.",
                command=None,
                verification="Check docs",
                citations=["hallucinated_chunk_99"],
            )
        ],
        anti_patterns_to_avoid=["Violating strict out-of-corpus refusal rules"],
        key_takeaway="An out-of-corpus refusal has been triggered.",
        is_refusal=False,  # Model may fail to flag is_refusal
        cited_chunk_ids=["hallucinated_chunk_99"],
    )

    # Retrieval returns low score chunk (below 0.40 threshold)
    ungrounded_chunk = [
        {
            "chunk_id": "weak_chunk_0",
            "score": 0.22,
            "retrieval_method": "dense",
            "text": "Unrelated content",
        }
    ]

    with patch(
        "app.client._execute_chat_with_fallback",
        new=AsyncMock(return_value=(leaky_response.model_dump_json(), 35.0, None)),
    ), patch(
        "app.client.retrieve_relevant_chunks_async",
        new=AsyncMock(return_value=ungrounded_chunk),
    ):
        result = await generate_structured_response_async("How do I bake a chocolate cake?")

        # Must be forced to refusal and fully sanitized
        assert result.is_refusal is True
        assert result.summary == USER_FACING_REFUSAL_MESSAGE
        assert result.refusal_reason == "Question is outside the scope of the verified technical documentation."
        assert result.cited_chunk_ids == []
        for step in result.action_plan:
            assert step.citations == []

        all_text = (
            result.summary
            + " "
            + result.action_plan[0].explanation
            + " "
            + result.action_plan[0].title
            + " "
            + (result.key_takeaway or "")
        ).lower()
        assert "verified context is empty" not in all_text
        assert "out-of-corpus refusal triggered" not in all_text


# ---------------------------------------------------------------------------
# Consolidated Edge-Case Tests (Citations, Leakage Casing, Token & Fallback)
# ---------------------------------------------------------------------------

def _to_alternating_case(text: str) -> str:
    """Helper to generate mixed casing e.g. vErIfIeD cOnTeXt Is EmPtY."""
    return "".join(c.upper() if i % 2 == 0 else c.lower() for i, c in enumerate(text))


def _build_dummy_navigator_response() -> NavigatorResponse:
    return NavigatorResponse(
        summary="A clean technical response.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Execute Step",
                explanation="Run command to resolve issue.",
                command="echo ok",
                verification="Check exit code 0.",
                citations=["chunk_a"],
            )
        ],
        anti_patterns_to_avoid=["Do not skip verification."],
        is_refusal=False,
    )


class _MockStreamChunk:
    def __init__(self, text: str, usage_metadata=None):
        self.text = text
        self.usage_metadata = usage_metadata


async def _mock_async_stream(chunks):
    for chunk in chunks:
        yield chunk


def test_adversarial_citations_unsynced_and_orphaned():
    """Verify purging when root cited_chunk_ids and step citations disagree."""
    resp_a = NavigatorResponse(
        summary="Some refusal summary",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Review docs",
                explanation="Consult standard docs.",
                citations=[],
            )
        ],
        anti_patterns_to_avoid=["Don't skip docs"],
        is_refusal=True,
        cited_chunk_ids=["orphaned_chunk_1", "orphaned_chunk_2"],
    )
    san_a = sanitize_refusal_response(resp_a)
    assert san_a.cited_chunk_ids == []
    assert san_a.action_plan[0].citations == []

    resp_b = NavigatorResponse(
        summary="Some refusal summary",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Review docs",
                explanation="Consult standard docs.",
                citations=["step_chunk_1", "step_chunk_2"],
            )
        ],
        anti_patterns_to_avoid=["Don't skip docs"],
        is_refusal=True,
        cited_chunk_ids=[],
    )
    san_b = sanitize_refusal_response(resp_b)
    assert san_b.cited_chunk_ids == []
    assert san_b.action_plan[0].citations == []


@pytest.mark.parametrize("phrase", INTERNAL_REFUSAL_PHRASES)
def test_leakage_resistance_all_internal_phrases_and_mixed_case(phrase: str):
    """Verify every phrase in INTERNAL_REFUSAL_PHRASES (including mixed casing) is scrubbed from all fields."""
    mixed = _to_alternating_case(phrase)
    raw_response = NavigatorResponse(
        summary=f"Alert: {phrase} / {mixed} detected.",
        action_plan=[
            ActionableStep(
                step_number=1,
                title=f"Title: {mixed}",
                explanation=f"Explanation: {phrase} and {mixed} happened.",
                command=f"cat '{phrase}'",
                verification=f"grep '{mixed}'",
                citations=["leak_cite_1"],
            )
        ],
        anti_patterns_to_avoid=[f"Pattern with {mixed}"],
        key_takeaway=f"Key takeaway mentioning {phrase}",
        is_refusal=True,
        refusal_reason=f"Reason: {phrase}",
        cited_chunk_ids=["leak_cite_1"],
    )

    sanitized = sanitize_refusal_response(raw_response)
    assert sanitized.summary == USER_FACING_REFUSAL_MESSAGE
    assert sanitized.cited_chunk_ids == []
    assert all(step.citations == [] for step in sanitized.action_plan)

    fields = [
        sanitized.summary,
        sanitized.refusal_reason or "",
        sanitized.action_plan[0].title,
        sanitized.action_plan[0].explanation,
        sanitized.action_plan[0].command or "",
        sanitized.action_plan[0].verification or "",
        sanitized.key_takeaway or "",
    ] + sanitized.anti_patterns_to_avoid

    search_space = " ".join(fields).lower()
    assert phrase.lower() not in search_space


def test_anti_patterns_fallback_when_all_anti_patterns_scrubbed():
    """Verify safe default anti-pattern when every anti-pattern only contained internal phrases."""
    raw_response = NavigatorResponse(
        summary="Refusal summary",
        action_plan=[
            ActionableStep(
                step_number=1,
                title="Action",
                explanation="Consult docs",
                citations=[],
            )
        ],
        anti_patterns_to_avoid=[
            "verified context is empty",
            "out-of-corpus refusal triggered",
            "strict out-of-corpus refusal rules",
        ],
        is_refusal=True,
    )

    sanitized = sanitize_refusal_response(raw_response)
    assert len(sanitized.anti_patterns_to_avoid) >= 1
    for ap in sanitized.anti_patterns_to_avoid:
        assert ap
        assert "verified context is empty" not in ap.lower()
        assert "out-of-corpus refusal" not in ap.lower()


@pytest.mark.asyncio
async def test_end_to_end_generate_forces_refusal_when_ungrounded_despite_llm_flag():
    """Verify ungrounded context (score < 0.40) forces refusal and clears citations even if LLM sets is_refusal=False."""
    adversarial_answering_llm_json = """
    {
        "summary": "Here is how to bake a cake despite verified context is empty.",
        "action_plan": [
            {
                "step_number": 1,
                "title": "Mix ingredients",
                "explanation": "Even though verified context is empty, mix flour.",
                "command": "mix flour",
                "verification": "check dough",
                "citations": ["baking_chunk_1", "baking_chunk_2"]
            }
        ],
        "anti_patterns_to_avoid": ["Burning the cake"],
        "key_takeaway": "Baking is fun.",
        "is_refusal": false,
        "refusal_reason": null,
        "cited_chunk_ids": ["baking_chunk_1", "baking_chunk_2"]
    }
    """
    ungrounded_chunks = [
        {
            "chunk_id": "low_score_chunk",
            "score": 0.28,
            "retrieval_method": "dense",
            "text": "Some unrelated content",
        }
    ]

    with patch(
        "app.client._execute_chat_with_fallback",
        new=AsyncMock(return_value=(adversarial_answering_llm_json, 50.0, None)),
    ), patch(
        "app.client.retrieve_relevant_chunks_async",
        new=AsyncMock(return_value=ungrounded_chunks),
    ):
        result = await generate_structured_response_async("How to bake a cake?")

    assert result.is_refusal is True
    assert result.cited_chunk_ids == []
    assert all(step.citations == [] for step in result.action_plan)
    assert result.summary == USER_FACING_REFUSAL_MESSAGE
    assert "verified context is empty" not in result.action_plan[0].explanation.lower()


@pytest.mark.parametrize(
    "input_text,expected_min",
    [
        ("", 0),
        ("   ", 1),
        ("\n\t\r", 3),
        ("a", 1),
        ("Hello, world!", 3),
        ("def calculate_fibonacci(n: int) -> int:\n    if n <= 1:\n        return n\n    return calculate_fibonacci(n - 1) + calculate_fibonacci(n - 2)\n", 10),
        ("SELECT users.id, profiles.bio FROM users JOIN profiles ON users.id = profiles.user_id WHERE users.active = 1;", 10),
        ('{"topic": "fastapi", "count": 42, "items": ["chunk_1", "chunk_2"], "nested": {"valid": true}}', 10),
        ("你好世界！这是一个针对分词器中文边界的压力测试。", 5),
        ("こんにちは世界！形態素解析トークン化のテストです。", 5),
        ("مرحبا بالعالم! هذا اختبار لمعالجة النصوص باللغة العربية.", 5),
        ("Привет, мир! Это стресс-тест токенизации на русском языке.", 5),
        ("שלום עולם! בדיקת טוקניזציה לעברית.", 5),
        ("नमस्ते दुनिया! यह टोकन काउंटर के लिए हिंदी परीक्षण है।", 5),
        ("🚀 🔥 💻 ⚡ 🎉", 5),
        ("👨‍👩‍👧‍👦 👩🏽‍💻 🏳️‍🌈 🇺🇸 👍🏽", 5),
        ("<|endoftext|>", 1),
        ("<|fim_prefix|>def foo():<|fim_suffix|>return 1<|fim_middle|>", 1),
    ],
)
def test_count_tokens_various_inputs(input_text, expected_min):
    """Verify count_tokens handles empty strings, code, unicode, emojis, and special tokens."""
    tokens = count_tokens(input_text)
    assert isinstance(tokens, int)
    if not input_text:
        assert tokens == 0
    else:
        assert tokens >= expected_min


def test_count_tokens_none_handling():
    """Verify count_tokens handles None gracefully without raising AttributeError."""
    assert count_tokens(None) == 0


def test_count_tokens_long_string_performance():
    """Verify count_tokens completes in under 1s on a 100,000+ character string."""
    long_text = "FastAPI dependency injection and Pydantic validation are essential. " * 1500
    assert len(long_text) >= 100_000
    t0 = time.perf_counter()
    tokens = count_tokens(long_text)
    elapsed = time.perf_counter() - t0
    assert tokens > 10_000
    assert elapsed < 1.0


@pytest.mark.asyncio
async def test_execute_chat_streaming_captures_usage_metadata_object():
    """Verify _execute_chat_with_fallback captures usage_metadata object from stream."""
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 185
    mock_usage.candidates_token_count = 92

    chunks = [
        _MockStreamChunk('{"summary": "Test summary", '),
        _MockStreamChunk('"action_plan": []}', usage_metadata=mock_usage),
    ]
    mock_chat = MagicMock()
    mock_chat.send_message_stream = AsyncMock(return_value=_mock_async_stream(chunks))
    mock_client = MagicMock()
    mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

    with patch("app.client.get_genai_client", return_value=mock_client):
        raw_text, ttft_ms, usage = await _execute_chat_with_fallback("test query")
        assert '{"summary": "Test summary", "action_plan": []}' in raw_text
        assert ttft_ms is not None and ttft_ms >= 0
        assert usage is mock_usage
        assert usage.prompt_token_count == 185
        assert usage.candidates_token_count == 92


@pytest.mark.asyncio
async def test_execute_chat_streaming_captures_usage_metadata_dict():
    """Verify _execute_chat_with_fallback captures dict usage_metadata from stream."""
    mock_usage = {"prompt_token_count": 215, "candidates_token_count": 88}
    chunks = [
        _MockStreamChunk('{"summary": "Dict chunk 1", '),
        _MockStreamChunk('"action_plan": []}', usage_metadata=mock_usage),
    ]
    mock_chat = MagicMock()
    mock_chat.send_message_stream = AsyncMock(return_value=_mock_async_stream(chunks))
    mock_client = MagicMock()
    mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

    with patch("app.client.get_genai_client", return_value=mock_client):
        _, _, usage = await _execute_chat_with_fallback("test query")
        assert usage == mock_usage


@pytest.mark.asyncio
async def test_execute_chat_streaming_without_usage_metadata():
    """Verify _execute_chat_with_fallback returns usage=None if stream chunks lack usage_metadata."""
    chunks = [_MockStreamChunk('{"summary": "No metadata"}', usage_metadata=None)]
    mock_chat = MagicMock()
    mock_chat.send_message_stream = AsyncMock(return_value=_mock_async_stream(chunks))
    mock_client = MagicMock()
    mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

    with patch("app.client.get_genai_client", return_value=mock_client):
        _, _, usage = await _execute_chat_with_fallback("test query")
        assert usage is None


@pytest.mark.asyncio
async def test_execute_chat_unary_fallback_captures_and_handles_missing_usage_metadata():
    """Verify unary fallback captures usage_metadata when present and returns None when absent."""
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 300
    mock_usage.candidates_token_count = 120

    mock_response = MagicMock()
    mock_response.text = '{"summary": "Unary fallback response", "action_plan": []}'
    mock_response.usage_metadata = mock_usage

    mock_chat = MagicMock()
    mock_chat.send_message_stream = AsyncMock(side_effect=RuntimeError("Stream aborted"))
    mock_chat.send_message = AsyncMock(return_value=mock_response)
    mock_client = MagicMock()
    mock_client.aio.chats.create = MagicMock(return_value=mock_chat)

    with patch("app.client.get_genai_client", return_value=mock_client):
        raw_text, _, usage = await _execute_chat_with_fallback("test query")
        assert "Unary fallback response" in raw_text
        assert usage is mock_usage

    mock_response_no_meta = MagicMock(spec=["text"])
    mock_response_no_meta.text = '{"summary": "Unary response without metadata", "action_plan": []}'
    mock_chat.send_message = AsyncMock(return_value=mock_response_no_meta)

    with patch("app.client.get_genai_client", return_value=mock_client):
        raw_text, _, usage = await _execute_chat_with_fallback("test query")
        assert "Unary response without metadata" in raw_text
        assert usage is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "mock_usage,expected_source,expect_prompt,expect_completion",
    [
        ({"prompt_token_count": 310, "candidates_token_count": None}, "tiktoken", 310, None),
        ({"prompt_token_count": None, "candidates_token_count": 95}, "tiktoken", None, 95),
        ({}, "tiktoken", None, None),
        ({"prompt_token_count": 0, "candidates_token_count": 0}, "gemini", 0, 0),
    ],
)
async def test_token_accounting_partial_empty_and_zero_metadata(
    mock_usage, expected_source, expect_prompt, expect_completion
):
    """Verify partial, empty, and zero usage_metadata edge cases preserve valid counts and label source accurately."""
    sample_resp = _build_dummy_navigator_response()

    with patch(
        "app.client._execute_chat_with_fallback",
        new=AsyncMock(return_value=(sample_resp.model_dump_json(), 30.0, mock_usage)),
    ), patch(
        "app.client.retrieve_relevant_chunks_async",
        new=AsyncMock(return_value=[{"chunk_id": "chunk_a", "score": 0.88, "retrieval_method": "dense"}]),
    ):
        result = await generate_structured_response_async("Explain dependency injection")

    assert getattr(result, "_token_source") == expected_source
    if expect_prompt is not None:
        assert getattr(result, "_prompt_tokens") == expect_prompt
    else:
        assert getattr(result, "_prompt_tokens") > 0
    if expect_completion is not None:
        assert getattr(result, "_completion_tokens") == expect_completion
    else:
        assert getattr(result, "_completion_tokens") > 0


@pytest.mark.asyncio
async def test_run_eval_live_logs_api_tokens_and_ttft(tmp_path):
    """Verify evaluate_benchmark(retrieval_only=False) records API token telemetry and measured TTFT instead of heuristics."""
    import json
    from eval.run_eval import evaluate_benchmark

    gold_file = tmp_path / "mini_gold.json"
    gold_file.write_text(
        json.dumps(
            [
                {
                    "id": "DEV-TOK-01",
                    "category": "FastAPI",
                    "question": "How do I configure CORS in FastAPI?",
                    "expected_chunk_ids": ["chunk_a"],
                    "expected_rubric": ["cors"],
                    "negative_constraints": [],
                }
            ]
        ),
        encoding="utf-8",
    )
    out_file = tmp_path / "mini_results.json"

    resp = _build_dummy_navigator_response()
    resp.cited_chunk_ids = ["chunk_a"]
    object.__setattr__(resp, "_prompt_tokens", 1984)
    object.__setattr__(resp, "_completion_tokens", 247)
    object.__setattr__(resp, "_token_source", "gemini")
    object.__setattr__(resp, "_ttft_ms", 142.5)

    with patch(
        "eval.run_eval.retrieve_relevant_chunks",
        return_value=[{"chunk_id": "chunk_a", "score": 0.91, "text": "CORSMiddleware allows origins."}],
    ), patch(
        "eval.run_eval.generate_structured_response_async",
        new=AsyncMock(return_value=resp),
    ):
        report = await evaluate_benchmark(
            gold_set_path=str(gold_file),
            output_path=str(out_file),
            search_mode="hybrid-rerank",
            retrieval_only=False,
            delay=0.0,
        )

    assert len(report["items"]) == 1
    item = report["items"][0]
    assert item["prompt_tokens"] == 1984
    assert item["completion_tokens"] == 247
    assert item["token_source"] == "gemini"
    assert item["ttft_ms"] == 142.5
    assert item["ttft_source"] == "measured"
    assert item["analytic_prompt_tokens"] > 0
    assert report["mean_prompt_tokens"] == 1984.0
    assert report["latency_metrics"]["mean_completion_tokens"] == 247.0
    assert report["latency_metrics"]["token_sources"] == {"gemini": 1}


@pytest.mark.asyncio
async def test_run_eval_quota_retry_logs_only_errored_question(tmp_path):
    """Verify quota/429 errors retry only the errored question and record retry counts in results & report."""
    import json
    from eval.run_eval import evaluate_benchmark

    gold_file = tmp_path / "mini_retry_gold.json"
    gold_file.write_text(
        json.dumps(
            [
                {
                    "id": "DEV-Q-01",
                    "category": "FastAPI",
                    "question": "Question one",
                    "expected_chunk_ids": ["chunk_a"],
                },
                {
                    "id": "DEV-Q-02",
                    "category": "Pydantic",
                    "question": "Question two",
                    "expected_chunk_ids": ["chunk_a"],
                },
            ]
        ),
        encoding="utf-8",
    )
    out_file = tmp_path / "mini_retry_results.json"

    calls = []

    async def fake_generate(prompt: str, search_mode: str = "hybrid-rerank"):
        calls.append(prompt)
        if prompt == "Question two" and calls.count("Question two") == 1:
            raise RuntimeError("429 RESOURCE_EXHAUSTED quota exceeded")
        r = _build_dummy_navigator_response()
        r.cited_chunk_ids = ["chunk_a"]
        object.__setattr__(r, "_prompt_tokens", 1200)
        object.__setattr__(r, "_completion_tokens", 180)
        object.__setattr__(r, "_token_source", "gemini")
        object.__setattr__(r, "_ttft_ms", 95.0)
        return r

    with patch(
        "eval.run_eval.retrieve_relevant_chunks",
        return_value=[{"chunk_id": "chunk_a", "score": 0.90, "text": "Docs text."}],
    ), patch(
        "eval.run_eval.generate_structured_response_async",
        side_effect=fake_generate,
    ), patch(
        "eval.run_eval.asyncio.sleep",
        new=AsyncMock(),
    ):
        report = await evaluate_benchmark(
            gold_set_path=str(gold_file),
            output_path=str(out_file),
            search_mode="hybrid-rerank",
            retrieval_only=False,
            delay=0.0,
        )

    assert calls.count("Question one") == 1
    assert calls.count("Question two") == 2
    by_id = {r["id"]: r for r in report["items"]}
    assert by_id["DEV-Q-01"]["quota_retries"] == 0
    assert by_id["DEV-Q-02"]["quota_retries"] == 1
    assert report["latency_metrics"]["quota_retry_count"] == 1
    assert report["latency_metrics"]["quota_retried_questions"] == {"DEV-Q-02": 1}
