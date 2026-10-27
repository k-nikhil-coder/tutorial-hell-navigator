import os
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = PROJECT_ROOT / "logs"
TRAJECTORY_LOG_FILE = LOGS_DIR / "query_trajectories.jsonl"


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


def get_recent_trajectories(limit: int = 20) -> List[Dict[str, Any]]:
    """Retrieve the most recent logged trajectories."""
    if not TRAJECTORY_LOG_FILE.exists():
        return []

    trajectories = []
    try:
        with open(TRAJECTORY_LOG_FILE, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    trajectories.append(json.loads(line))
    except Exception as e:
        print(f"Warning: Failed to read telemetry trajectories: {e}")
        return []

    return trajectories[-limit:]
