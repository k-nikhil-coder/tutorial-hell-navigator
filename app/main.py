import os
import time
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, Query, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from app.schemas import QueryRequest, NavigatorResponse, HealthStatus
from app.client import (
    generate_structured_response_async,
    stream_response_sse,
    PRIMARY_MODEL,
    DEFAULT_CONCURRENCY_LIMIT,
)
from app.tools import AVAILABLE_TOOLS, search_error_catalog
from app.rag import get_indexed_count
from app.telemetry import log_query_trajectory, get_recent_trajectories

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Tutorial Hell Navigator API",
    description="Eval-first mentor API that provides structured action plans and debugging roadmaps for CS students.",
    version="1.0.0",
)

# Configure allowed origins (configurable via ALLOWED_ORIGINS env var for public cloud deploys)
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000,http://127.0.0.1:5173",
    ).split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
def root():
    return {
        "service": "Tutorial Hell Navigator API",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "navigate": "POST /navigate",
            "stream_post": "POST /navigate/stream",
            "stream_get": "GET /navigate/stream?query=...",
            "telemetry": "GET /telemetry/trajectories",
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
        logger.error("Navigation error for query '%s': %s", request.query[:50], e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Navigation failed: {e}",
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
