import os
import sys
import json
import time
import logging
import asyncio
from pathlib import Path
from typing import Optional, Dict, Any, Tuple
from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
REWRITES_CACHE_FILE = DATA_DIR / "query_rewrites_cache.json"

REWRITE_PROMPT = """You are a technical search query optimizer for a computer science documentation index.
Given a user query (often conversational or vague), generate a concise, keyword-rich search query targeting technical documentation (FastAPI, Docker, Pydantic, PostgreSQL).
Preserve exact terms, flags, error messages, and decorator syntax. Return ONLY the rewritten query string without quotes or preamble.

User Query: {query}
Rewritten Query:"""

_rewrites_cache: Dict[str, Dict[str, Any]] = {}


def _load_rewrites_cache():
    """Load cached query rewrites from disk to prevent redundant API calls."""
    global _rewrites_cache
    if not _rewrites_cache and REWRITES_CACHE_FILE.exists():
        try:
            with open(REWRITES_CACHE_FILE, "r", encoding="utf-8") as f:
                _rewrites_cache = json.load(f)
        except Exception as e:
            logger.warning("Failed to load rewrites cache: %s", e)
            _rewrites_cache = {}


def _save_rewrites_cache():
    """Persist rewrites cache to disk."""
    try:
        REWRITES_CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(REWRITES_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(_rewrites_cache, f, indent=2)
    except Exception as e:
        logger.warning("Failed to save rewrites cache: %s", e)


async def rewrite_query_with_latency(
    query: str,
    client: Optional[Any] = None,
    model_name: str = "gemini-flash-lite-latest",
    use_cache: bool = True,
) -> Tuple[str, float]:
    """
    Expands conversational student queries into technical keywords for dense/sparse retrieval.
    
    Returns:
        Tuple of (rewritten_query_str, latency_ms)
    """
    _load_rewrites_cache()
    norm_query = query.strip()

    if use_cache and norm_query in _rewrites_cache:
        entry = _rewrites_cache[norm_query]
        return entry.get("rewritten", norm_query), entry.get("latency_ms", 0.0)

    if not client:
        from app.client import get_genai_client
        client = get_genai_client()

    t_start = time.perf_counter()
    prompt = REWRITE_PROMPT.format(query=norm_query)

    try:
        response = await client.aio.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        rewritten = response.text.strip().replace("\n", " ").replace('"', '') if response and response.text else norm_query
        rewritten = rewritten if rewritten else norm_query

        if use_cache:
            _rewrites_cache[norm_query] = {
                "rewritten": rewritten,
                "latency_ms": latency_ms,
            }
            _save_rewrites_cache()

        return rewritten, latency_ms
    except Exception as e:
        logger.warning("Query rewrite failed: %s, falling back to original query", e)
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return norm_query, latency_ms


async def rewrite_query(query: str, client: Optional[Any] = None) -> str:
    """Async convenience wrapper returning the rewritten query string."""
    rewritten, _ = await rewrite_query_with_latency(query, client=client)
    return rewritten


def rewrite_query_sync(query: str, client: Optional[Any] = None) -> str:
    """Synchronous wrapper for query rewriting."""
    rewritten, _ = rewrite_query_with_latency_sync(query, client=client)
    return rewritten


def rewrite_query_with_latency_sync(
    query: str,
    client: Optional[Any] = None,
    model_name: str = "gemini-flash-lite-latest",
    use_cache: bool = True,
) -> Tuple[str, float]:
    """
    Synchronous query rewriter using direct SDK calls to avoid event loop closure issues.
    """
    _load_rewrites_cache()
    norm_query = query.strip()

    if use_cache and norm_query in _rewrites_cache:
        entry = _rewrites_cache[norm_query]
        return entry.get("rewritten", norm_query), entry.get("latency_ms", 0.0)

    if not client:
        from app.client import get_genai_client
        client = get_genai_client()

    t_start = time.perf_counter()
    prompt = REWRITE_PROMPT.format(query=norm_query)

    try:
        response = client.models.generate_content(
            model=model_name,
            contents=prompt,
        )
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        rewritten = response.text.strip().replace("\n", " ").replace('"', '') if response and response.text else norm_query
        rewritten = rewritten if rewritten else norm_query

        if use_cache:
            _rewrites_cache[norm_query] = {
                "rewritten": rewritten,
                "latency_ms": latency_ms,
            }
            _save_rewrites_cache()

        return rewritten, latency_ms
    except Exception as e:
        logger.warning("Query rewrite failed: %s, falling back to original query", e)
        latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
        return norm_query, latency_ms
