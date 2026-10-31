import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from app.rewriter import (
    REWRITE_PROMPT,
    rewrite_query,
    rewrite_query_sync,
    rewrite_query_with_latency,
    rewrite_query_with_latency_sync,
)


def test_rewrite_prompt_formatting():
    """Verify rewrite prompt correctly interpolates student query."""
    user_q = "How do I configure CORS for my React app?"
    prompt = REWRITE_PROMPT.format(query=user_q)
    assert user_q in prompt
    assert "FastAPI" in prompt or "technical documentation" in prompt


@pytest.mark.asyncio
async def test_rewrite_query_with_mock_client():
    """Verify rewrite query transforms conversational query into technical keywords."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "FastAPI CORSMiddleware allow_origins allow_credentials"
    mock_client.aio.models.generate_content = AsyncMock(return_value=mock_response)

    raw_query = "Why is my browser throwing CORS errors when React calls my FastAPI server?"
    rewritten, lat = await rewrite_query_with_latency(
        raw_query, client=mock_client, use_cache=False
    )

    assert rewritten == "FastAPI CORSMiddleware allow_origins allow_credentials"
    assert lat >= 0.0


@pytest.mark.asyncio
async def test_rewrite_query_fallback_on_exception():
    """Verify query rewriter gracefully falls back to raw query on API failure."""
    mock_client = MagicMock()
    mock_client.aio.models.generate_content = AsyncMock(side_effect=RuntimeError("API Quota Exceeded"))

    raw_query = "What is Docker Compose healthcheck syntax?"
    rewritten, lat = await rewrite_query_with_latency(
        raw_query, client=mock_client, use_cache=False
    )

    assert rewritten == raw_query
    assert lat >= 0.0


def test_rewrite_query_sync_wrapper():
    """Verify synchronous wrapper works correctly without active event loop."""
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text = "Docker multi-stage build python slim gcc"
    mock_client.models.generate_content = MagicMock(return_value=mock_response)

    rewritten = rewrite_query_sync(
        "How to build small docker image?", client=mock_client
    )
    assert rewritten == "Docker multi-stage build python slim gcc"
