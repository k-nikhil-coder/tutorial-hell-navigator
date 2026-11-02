import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
TRAJECTORY_LOG_FILE = LOGS_DIR / "query_trajectories.jsonl"
FEEDBACK_LOG_FILE = LOGS_DIR / "feedback.jsonl"


def init_telemetry():
    """Ensure telemetry log directory exists."""
    LOGS_DIR.mkdir(parents=True, exist_ok=True)


def log_query_trajectory(
    query: str,
    retrieved_chunks: List[Dict[str, Any]],
    response_summary: str,
    is_refusal: bool,
    cited_chunk_ids: List[str],
    latency_ms: float,
    refusal_reason: Optional[str] = None,
) -> Dict[str, Any]:
    """Record query, retrieved context, citations, and refusal state for failure taxonomy analysis."""
    init_telemetry()

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "retrieved_chunks": [
            {
                "chunk_id": c.get("chunk_id", ""),
                "source_file": c.get("source_file", ""),
                "score": round(float(c.get("score", 0.0)), 4),
            }
            for c in retrieved_chunks
        ],
        "retrieved_chunk_ids": [c.get("chunk_id", "") for c in retrieved_chunks],
        "is_refusal": is_refusal,
        "refusal_reason": refusal_reason,
        "cited_chunk_ids": cited_chunk_ids,
        "response_summary": response_summary,
        "latency_ms": round(latency_ms, 2),
    }

    try:
        with open(TRAJECTORY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        print(f"Warning: Failed to write telemetry trajectory: {e}")

    return record


from collections import deque
import logging

logger = logging.getLogger(__name__)


def get_recent_trajectories(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve the most recent logged trajectories using a bounded memory buffer."""
    if not TRAJECTORY_LOG_FILE.exists():
        return []

    recent_lines = deque(maxlen=limit)
    try:
        with open(TRAJECTORY_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    recent_lines.append(line)
        return [json.loads(l) for l in recent_lines]
    except Exception as e:
        logger.warning("Failed to read telemetry trajectories: %s", e)
        return []


def log_user_feedback(
    query: str,
    rating: Optional[str] = None,
    unstuck: Optional[bool] = None,
    comment: Optional[str] = None,
    cited_chunk_ids: Optional[List[str]] = None,
    session_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Record user thumbs-up/down, unstick metric, and comments for real-user testing telemetry."""
    init_telemetry()

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "query": query,
        "rating": rating.lower().strip() if rating else None,
        "unstuck": unstuck,
        "comment": comment.strip() if comment else None,
        "cited_chunk_ids": cited_chunk_ids or [],
        "session_id": session_id,
    }

    try:
        with open(FEEDBACK_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.warning("Failed to write feedback log: %s", e)

    return record


def get_recent_feedback(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve the most recent logged user feedback."""
    if not FEEDBACK_LOG_FILE.exists():
        return []

    recent_lines = deque(maxlen=limit)
    try:
        with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    recent_lines.append(line)
        return [json.loads(l) for l in recent_lines]
    except Exception as e:
        logger.warning("Failed to read feedback log: %s", e)
        return []


def get_feedback_summary() -> Dict[str, Any]:
    """Aggregate feedback telemetry: total count, unstick rate, and rating distribution."""
    if not FEEDBACK_LOG_FILE.exists():
        return {
            "total_records": 0,
            "unstuck_count": 0,
            "stuck_count": 0,
            "unstick_rate_percent": 0.0,
            "positive_ratings": 0,
            "negative_ratings": 0,
        }

    total = 0
    unstuck_count = 0
    stuck_count = 0
    positive = 0
    negative = 0

    try:
        with open(FEEDBACK_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    r = json.loads(line)
                    total += 1
                    if r.get("unstuck") is True:
                        unstuck_count += 1
                    elif r.get("unstuck") is False:
                        stuck_count += 1

                    if r.get("rating") == "positive":
                        positive += 1
                    elif r.get("rating") == "negative":
                        negative += 1

        rated_unstick = unstuck_count + stuck_count
        rate = round((unstuck_count / rated_unstick) * 100, 1) if rated_unstick > 0 else 0.0

        return {
            "total_records": total,
            "unstuck_count": unstuck_count,
            "stuck_count": stuck_count,
            "unstick_rate_percent": rate,
            "positive_ratings": positive,
            "negative_ratings": negative,
        }
    except Exception as e:
        logger.warning("Failed to compute feedback summary: %s", e)
        return {"error": str(e)}
