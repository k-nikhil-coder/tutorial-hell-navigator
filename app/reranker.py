import os
import time
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Default model configurations
DEFAULT_CROSS_ENCODER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
DEFAULT_FLASHRANK_MODEL = "ms-marco-MiniLM-L-12-v2"

_cross_encoder_instance = None
_flashrank_instance = None


def get_cross_encoder(model_name: str = DEFAULT_CROSS_ENCODER_MODEL):
    """Lazy loader singleton for sentence_transformers CrossEncoder."""
    global _cross_encoder_instance
    if _cross_encoder_instance is None:
        try:
            from sentence_transformers import CrossEncoder
            logger.info("Initializing CrossEncoder model: %s", model_name)
            _cross_encoder_instance = CrossEncoder(model_name)
        except Exception as e:
            logger.warning("Failed to initialize CrossEncoder (%s), falling back: %s", model_name, e)
            _cross_encoder_instance = None
    return _cross_encoder_instance


def get_flashrank_ranker(model_name: str = DEFAULT_FLASHRANK_MODEL):
    """Lazy loader singleton for FlashRank Ranker."""
    global _flashrank_instance
    if _flashrank_instance is None:
        try:
            from flashrank import Ranker
            logger.info("Initializing FlashRank model: %s", model_name)
            _flashrank_instance = Ranker(model_name=model_name)
        except Exception as e:
            logger.warning("Failed to initialize FlashRank (%s): %s", model_name, e)
            _flashrank_instance = None
    return _flashrank_instance


def rerank_chunks(
    query: str,
    candidate_chunks: List[Dict[str, Any]],
    top_k: int = 3,
    model_name: str = DEFAULT_CROSS_ENCODER_MODEL,
    backend: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Reranks candidate chunks from Hybrid Search using cross-attention joint evaluation.
    
    Args:
        query: User search query.
        candidate_chunks: List of retrieved candidate chunks (e.g., top 10 from Hybrid RRF).
        top_k: Number of highest-relevance chunks to return.
        model_name: Cross-encoder model identifier.
        backend: Preferred backend ('sentence-transformers', 'flashrank', or 'auto').
        
    Returns:
        List of top_k chunk dictionaries sorted descending by cross-encoder score.
    """
    if not candidate_chunks:
        return []

    # Choose backend from environment or argument
    chosen_backend = backend or os.getenv("RERANKER_BACKEND", "auto").lower()
    t_start = time.perf_counter()

    # Attempt 1: SentenceTransformers CrossEncoder
    if chosen_backend in ("sentence-transformers", "auto"):
        ce = get_cross_encoder(model_name)
        if ce is not None:
            try:
                pairs = [(query, chunk.get("text", "")) for chunk in candidate_chunks]
                scores = ce.predict(pairs)
                rerank_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

                results = []
                for i, chunk in enumerate(candidate_chunks):
                    entry = dict(chunk)
                    score_val = float(scores[i])
                    entry["rerank_score"] = round(score_val, 4)
                    entry["score"] = round(score_val, 4)
                    entry["rerank_latency_ms"] = rerank_duration_ms
                    entry["retrieval_method"] = "hybrid_rerank"
                    results.append(entry)

                reranked = sorted(results, key=lambda x: x["rerank_score"], reverse=True)
                return reranked[:top_k]
            except Exception as e:
                logger.warning("CrossEncoder prediction error: %s, trying FlashRank fallback", e)

    # Attempt 2: FlashRank ONNX CPU Reranker
    if chosen_backend in ("flashrank", "auto"):
        fr = get_flashrank_ranker()
        if fr is not None:
            try:
                from flashrank import RerankRequest
                passages = [
                    {"id": idx, "text": chunk.get("text", "")}
                    for idx, chunk in enumerate(candidate_chunks)
                ]
                req = RerankRequest(query=query, passages=passages)
                fr_results = fr.rerank(req)
                rerank_duration_ms = round((time.perf_counter() - t_start) * 1000, 2)

                # Map flashrank score back to original chunk dicts
                score_by_id = {res["id"]: float(res["score"]) for res in fr_results}
                results = []
                for idx, chunk in enumerate(candidate_chunks):
                    entry = dict(chunk)
                    score_val = score_by_id.get(idx, 0.0)
                    entry["rerank_score"] = round(score_val, 4)
                    entry["score"] = round(score_val, 4)
                    entry["rerank_latency_ms"] = rerank_duration_ms
                    entry["retrieval_method"] = "hybrid_rerank"
                    results.append(entry)

                reranked = sorted(results, key=lambda x: x["rerank_score"], reverse=True)
                return reranked[:top_k]
            except Exception as e:
                logger.warning("FlashRank prediction error: %s", e)

    # Fallback: Preserve original order if rerankers fail
    logger.warning("All reranker backends unavailable, falling back to original candidate ordering")
    return candidate_chunks[:top_k]
