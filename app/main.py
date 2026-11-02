import os
import time
import uuid
import logging
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, FileResponse

from app.schemas import (
    QueryRequest,
    NavigatorResponse,
    HealthStatus,
    FeedbackRequest,
    FeedbackResponse,
)
from app.client import (
    generate_structured_response_async,
    stream_response_sse,
    PRIMARY_MODEL,
    DEFAULT_CONCURRENCY_LIMIT,
)
from app.tools import AVAILABLE_TOOLS, search_error_catalog
from app.rag import get_indexed_count, get_chunk_by_id
from app.telemetry import (
    log_query_trajectory,
    get_recent_trajectories,
    log_user_feedback,
    get_recent_feedback,
    get_feedback_summary,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tutorial Hell Navigator API",
    description="Eval-first mentor API that provides structured action plans and debugging roadmaps for CS students.",
    version="1.0.0",
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
    allow_headers=["Authorization", "Content-Type", "Accept"],
)





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
        },
    }


@app.get("/health", response_model=HealthStatus)
def health_check():
    return HealthStatus(
        status="healthy",
        model=PRIMARY_MODEL,
        concurrency_limit=DEFAULT_CONCURRENCY_LIMIT,
        available_tools=[tool.__name__ for tool in AVAILABLE_TOOLS],
        indexed_chunks=get_indexed_count(),
        vector_store="Qdrant",
    )


@app.post("/navigate", response_model=NavigatorResponse)
async def navigate(request: QueryRequest) -> NavigatorResponse:
    start_time = time.perf_counter()
    try:
        response = await generate_structured_response_async(request.query)
        latency_ms = (time.perf_counter() - start_time) * 1000

        retrieved_chunks = getattr(response, "_retrieved_chunks", [])
        log_query_trajectory(
            query=request.query,
            retrieved_chunks=retrieved_chunks,
            response_summary=response.summary,
            is_refusal=response.is_refusal,
            cited_chunk_ids=response.cited_chunk_ids,
            latency_ms=latency_ms,
            refusal_reason=response.refusal_reason,
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
        stream_response_sse(request.query),
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
):
    return StreamingResponse(
        stream_response_sse(query),
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



