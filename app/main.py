import os
import time
import uuid
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime, timezone
from collections import defaultdict
from threading import Lock
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse, JSONResponse

from app.schemas import (
    QueryRequest,
    NavigatorResponse,
    HealthStatus,
    FeedbackRequest,
    FeedbackResponse,
    ReviewRequest,
    ReviewResult,
)
from app.reviewer import audit_response
from app.client import (
    generate_structured_response_async,
    stream_response_sse,
    PRIMARY_MODEL,
    DEFAULT_CONCURRENCY_LIMIT,
)
from app.tools import AVAILABLE_TOOLS, search_error_catalog
from app.rag import get_indexed_count, get_chunk_by_id, get_pgvector_indexed_count, get_pgvector_store
from app.telemetry import (
    log_query_trajectory,
    get_recent_trajectories,
    log_user_feedback,
    get_recent_feedback,
    get_feedback_summary,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def validate_tunnel_config() -> None:
    """Validate tunnel security configuration on application startup.

    If TUNNEL_MODE is enabled ('true', '1', 'yes'), INVITE_CODE must be set and non-empty.
    Fails application startup with RuntimeError if INVITE_CODE is unset or empty.
    """
    tunnel_mode = os.getenv("TUNNEL_MODE", "").lower() in ("true", "1", "yes")
    invite_code = (os.getenv("INVITE_CODE") or "").strip()
    if tunnel_mode and not invite_code:
        raise RuntimeError(
            "Application startup failed: TUNNEL_MODE is enabled but INVITE_CODE is missing or empty. "
            "Set INVITE_CODE to a secure token before enabling tunnel mode."
        )


@asynccontextmanager
async def lifespan(app: FastAPI):
    validate_tunnel_config()
    yield


app = FastAPI(
    title="Tutorial Hell Navigator API",
    description="Eval-first mentor API that provides structured action plans and debugging roadmaps for CS students.",
    version="1.0.0",
    lifespan=lifespan,
)

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000,http://localhost:8000").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept", "X-Invite-Code"],
)

# --- Tunnel Access Controls (Day 47 Lane A4) ---
_tunnel_lock = Lock()
_tunnel_ip_history = defaultdict(list)
_tunnel_daily_counts = defaultdict(int)


def is_tunnel_request(request: Request) -> bool:
    """Detect if request arrives via tunnel / reverse proxy."""
    if os.getenv("TUNNEL_MODE", "").lower() in ("true", "1", "yes"):
        return True
    if request.headers.get("x-tunnel-request", "").lower() == "true":
        return True
    host = request.headers.get("x-forwarded-host") or request.headers.get("host") or ""
    host_clean = host.lower().split(":")[0]
    if host_clean in ("localhost", "127.0.0.1", "testserver", "0.0.0.0", "test"):
        return False
    tunnel_markers = ("ngrok", "localtunnel", "trycloudflare", "pinggy", "serveo", "pagekite", "telebit", "tailscale")
    if any(m in host_clean for m in tunnel_markers):
        return True
    return False


def get_client_ip(request: Request) -> str:
    """Extract client IP address, trusting X-Forwarded-For ONLY when TRUST_PROXY=1."""
    trust_proxy = os.getenv("TRUST_PROXY", "").strip() in ("1", "true", "yes")
    if trust_proxy:
        xff = request.headers.get("x-forwarded-for")
        if xff:
            first_ip = xff.split(",")[0].strip()
            if first_ip:
                return first_ip
    return request.client.host if request.client else "unknown"


def get_tunnel_daily_cap() -> int:
    """Get daily request cap for tunnel access, defaulting to 300/day."""
    return int(os.getenv("TUNNEL_DAILY_REQUEST_CAP") or os.getenv("DAILY_REQUEST_CAP") or "300")


def get_tunnel_rate_limit() -> int:
    """Get per-IP rate limit per minute for tunnel access, defaulting to 10."""
    return int(os.getenv("TUNNEL_RATE_LIMIT_PER_MINUTE") or os.getenv("RATE_LIMIT_PER_MINUTE") or "10")


@app.middleware("http")
async def tunnel_security_middleware(request: Request, call_next):
    if is_tunnel_request(request):
        # 1. Invite Code Check
        expected_code = (os.getenv("INVITE_CODE") or "").strip()
        provided_code = request.headers.get("x-invite-code") or request.query_params.get("invite_code")
        if not expected_code or provided_code != expected_code:
            return JSONResponse(
                status_code=status.HTTP_401_UNAUTHORIZED,
                content={"detail": "Tunnel access requires a valid invite code."},
            )

        now = time.time()
        today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        client_ip = get_client_ip(request)

        rate_limit = get_tunnel_rate_limit()
        daily_cap = get_tunnel_daily_cap()

        with _tunnel_lock:
            # 2. Daily Request Cap Check
            if _tunnel_daily_counts[today_str] >= daily_cap:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": f"Tunnel daily request cap reached (max {daily_cap} requests per day)."},
                )

            # 3. Per-IP Rate Limit Check (60s sliding window)
            timestamps = [t for t in _tunnel_ip_history[client_ip] if now - t < 60.0]
            if len(timestamps) >= rate_limit:
                return JSONResponse(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    content={"detail": f"Tunnel rate limit exceeded (max {rate_limit} requests per minute)."},
                )

            timestamps.append(now)
            _tunnel_ip_history[client_ip] = timestamps
            _tunnel_daily_counts[today_str] += 1

    return await call_next(request)





FRONTEND_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


@app.get("/", include_in_schema=False)
@app.get("/chat", include_in_schema=False)
def serve_chat_ui():
    """Serve the single-page chat UI."""
    if FRONTEND_INDEX.exists():
        return FileResponse(FRONTEND_INDEX, media_type="text/html")
    return {"message": "Tutorial Hell Navigator API is running. UI index.html not found."}


@app.get("/api")
def api_root():
    return {
        "service": "Tutorial Hell Navigator API",
        "docs": "/docs",
        "health": "/health",
        "chat_ui": "/",
        "endpoints": {
            "navigate": "POST /navigate",
            "stream_post": "POST /navigate/stream",
            "stream_get": "GET /navigate/stream?query=...",
            "telemetry": "GET /telemetry/trajectories",
            "feedback": "POST /api/feedback",
            "tools_catalog": "GET /tools/catalog",
            "review": "POST /api/review",
        },
    }


@app.get("/health", response_model=HealthStatus)
def health_check():
    pg_count = get_pgvector_indexed_count()
    pg_is_live = False
    try:
        store = get_pgvector_store()
        pg_is_live = store.is_live
    except Exception:
        pass

    return HealthStatus(
        status="healthy",
        model=PRIMARY_MODEL,
        concurrency_limit=DEFAULT_CONCURRENCY_LIMIT,
        available_tools=[tool.__name__ for tool in AVAILABLE_TOOLS],
        indexed_chunks=get_indexed_count(),
        vector_store="Qdrant",
        pgvector_indexed_chunks=pg_count,
        pgvector_is_live=pg_is_live,
    )


@app.post("/navigate", response_model=NavigatorResponse)
async def navigate(request: QueryRequest) -> NavigatorResponse:
    start_time = time.perf_counter()
    try:
        response = await generate_structured_response_async(
            request.query,
            topic=request.topic,
            category=request.category,
            backend=request.backend or "qdrant",
        )
        latency_ms = (time.perf_counter() - start_time) * 1000

        retrieved_chunks = getattr(response, "_retrieved_chunks", [])
        topic = request.topic or getattr(response, "_topic", None)
        if not topic and retrieved_chunks:
            topic = retrieved_chunks[0].get("topic")

        retrieval_ms = getattr(response, "_retrieval_ms", None)
        rerank_ms = getattr(response, "_rerank_ms", None)
        ttft_ms = getattr(response, "_ttft_ms", None)
        prompt_tokens = getattr(response, "_prompt_tokens", None)
        completion_tokens = getattr(response, "_completion_tokens", None)
        token_source = getattr(response, "_token_source", None)

        log_query_trajectory(
            query=request.query,
            retrieved_chunks=retrieved_chunks,
            response_summary=response.summary,
            is_refusal=response.is_refusal,
            cited_chunk_ids=response.cited_chunk_ids,
            latency_ms=latency_ms,
            refusal_reason=response.refusal_reason,
            topic=topic,
            retrieval_ms=retrieval_ms,
            rerank_ms=rerank_ms,
            ttft_ms=ttft_ms,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            token_source=token_source,
        )
        return response
    except Exception as e:
        error_id = uuid.uuid4().hex[:8]
        logger.error("[ErrorRef: %s] Navigation error for query '%s': %s", error_id, request.query[:50], e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Navigation failed (Error Reference: {error_id})",
        )


@app.post("/navigate/stream")
async def navigate_stream_post(request: QueryRequest):
    return StreamingResponse(
        stream_response_sse(
            request.query,
            topic=request.topic,
            category=request.category,
            backend=request.backend or "qdrant",
        ),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/navigate/stream")
async def navigate_stream_get(
    query: str = Query(..., min_length=3, description="Roadblock or error description"),
    topic: Optional[str] = Query(None, description="Topic filter for metadata search"),
    category: Optional[str] = Query(None, description="Category filter for metadata search"),
    backend: str = Query("qdrant", description="Vector backend: 'qdrant' or 'pgvector'"),
):
    return StreamingResponse(
        stream_response_sse(query, topic=topic, category=category, backend=backend),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/tools/catalog")
def get_catalog(signature: Optional[str] = None):
    if signature:
        return search_error_catalog(signature)
    return {
        "registered_tools": [tool.__name__ for tool in AVAILABLE_TOOLS],
        "common_signatures": [
            "psycopg2", "cors", "ModuleNotFoundError", "docker",
            "jwt", "sqlite", "git merge", "TLE", "EADDRINUSE",
        ],
    }


@app.get("/telemetry/trajectories")
def get_trajectories(limit: int = Query(default=20, ge=1, le=100)):
    records = get_recent_trajectories(limit=limit)
    return {
        "count": len(records),
        "trajectories": records,
    }


@app.post("/api/feedback", response_model=FeedbackResponse)
def submit_feedback(request: FeedbackRequest) -> FeedbackResponse:
    """Record user thumbs-up/down, unstick metric, and comments for real-user testing telemetry."""
    try:
        log_user_feedback(
            query=request.query,
            rating=request.rating,
            unstuck=request.unstuck,
            comment=request.comment,
            cited_chunk_ids=request.cited_chunk_ids,
            session_id=request.session_id,
        )
        return FeedbackResponse(status="ok", message="Feedback recorded successfully")
    except Exception as e:
        logger.warning("Failed to save feedback: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to record feedback",
        )


@app.get("/api/feedback")
def retrieve_feedback(limit: int = Query(default=20, ge=1, le=100)):
    """Retrieve the most recent logged user feedback."""
    records = get_recent_feedback(limit=limit)
    return {
        "count": len(records),
        "feedback": records,
    }


@app.get("/api/feedback/summary")
def retrieve_feedback_summary():
    """Retrieve aggregated Phase 0 success metrics (unstick rate and sentiment)."""
    return get_feedback_summary()


@app.get("/api/chunks/{chunk_id}")
def retrieve_chunk_details(chunk_id: str):
    """Retrieve the full verbatim source text and metadata of a cited chunk."""
    chunk = get_chunk_by_id(chunk_id)
    if not chunk:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Chunk ID '{chunk_id}' not found in corpus.",
        )
    return {
        "chunk_id": chunk.get("chunk_id"),
        "source_file": chunk.get("source_file"),
        "chunk_index": chunk.get("chunk_index"),
        "char_count": chunk.get("char_count", len(chunk.get("text", ""))),
        "text": chunk.get("text", ""),
    }


@app.post("/api/review", response_model=ReviewResult)
def review_response_endpoint(request: ReviewRequest) -> ReviewResult:
    """Audit a generated response for hallucinated code, unsupported claims, and ungrounded steps."""
    try:
        return audit_response(
            query=request.query,
            response=request.response,
            retrieved_chunks=request.retrieved_chunks,
        )
    except Exception as e:
        logger.error("Review auditing failed: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Response audit failed: {e}",
        )




