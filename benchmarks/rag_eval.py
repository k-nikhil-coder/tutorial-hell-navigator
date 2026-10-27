import sys
import json
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.client import generate_structured_response_async

# In-corpus technical queries strictly covered by corpus/raw/ (FastAPI, Docker, Architecture)
IN_CORPUS_QUERIES = [
    "How do I fix a CORS preflight error in FastAPI when connecting from React?",
    "Why does psycopg2 fail to compile in my Docker container with missing pg_config?",
    "How to mount CORSMiddleware in FastAPI with explicit origins?",
    "What is the multi-stage Dockerfile pattern for Python FastAPI apps?",
    "How do I handle SQLite database locked operational errors in async FastAPI?",
]

# Near-miss technical queries NOT in corpus (Django, Kubernetes/Helm, Spring Boot, Kafka/Rust, Android)
OUT_OF_CORPUS_QUERIES = [
    "How do I fix a Django migration dependency conflict with django-admin showmigrations?",
    "How do I deploy this microservice to a Kubernetes cluster using a Helm chart?",
    "How do I configure Spring Boot security filters with OAuth2 in Java?",
    "How do I set up Apache Kafka consumer group partitions in a Rust microservice?",
    "How do I debug a NullPointerException in an Android Jetpack Compose app?",
]


async def evaluate_rag_citations_and_refusal(sample_count: int = 5):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    in_queries = IN_CORPUS_QUERIES[:sample_count]
    out_queries = OUT_OF_CORPUS_QUERIES[:sample_count]

    print("=" * 72, flush=True)
    print(">> TUTORIAL HELL NAVIGATOR - RAG GROUNDING & REFUSAL BENCHMARK", flush=True)
    print(f" In-Corpus Test Set:     {len(in_queries)} queries (FastAPI, Docker, Architecture)", flush=True)
    print(f" Near-Miss Test Set:     {len(out_queries)} queries (Django, Kubernetes, Spring, Kafka, Android)", flush=True)
    print("=" * 72, flush=True)

    in_results = []
    print("\n[1/2] Testing In-Corpus Grounding & Inline Citations...", flush=True)
    for i, q in enumerate(in_queries, 1):
        try:
            resp = await generate_structured_response_async(q)
            cited = resp.cited_chunk_ids
            has_cite = len(cited) > 0 or any(len(s.citations) > 0 for s in resp.action_plan)
            in_results.append({
                "index": i, "query": q, "is_refusal": resp.is_refusal,
                "has_citations": has_cite, "cited_chunk_ids": cited
            })
            cite_str = ", ".join(cited) if cited else "None (No false citations)"
            print(f"  [{i}/{len(in_queries)}] Citations: {cite_str:38s} | Q: {q[:42]}...", flush=True)
        except Exception as e:
            print(f"  [{i}/{len(in_queries)}] ERROR: {e} | Q: {q[:42]}...", flush=True)
            in_results.append({"index": i, "query": q, "is_refusal": False, "has_citations": False, "error": str(e)})
        await asyncio.sleep(2.0)  # Rate limit safety delay

    out_results = []
    print("\n[2/2] Testing Near-Miss Technical Refusal Path...", flush=True)
    for i, q in enumerate(out_queries, 1):
        try:
            resp = await generate_structured_response_async(q)
            out_results.append({
                "index": i, "query": q, "is_refusal": resp.is_refusal,
                "refusal_reason": resp.refusal_reason
            })
            refusal_tag = "[REFUSED]" if resp.is_refusal else "[ANSWERED]"
            print(f"  [{i}/{len(out_queries)}] {refusal_tag:12s} | Q: {q[:50]}...", flush=True)
        except Exception as e:
            print(f"  [{i}/{len(out_queries)}] ERROR: {e} | Q: {q[:50]}...", flush=True)
            out_results.append({"index": i, "query": q, "is_refusal": False, "error": str(e)})
        await asyncio.sleep(2.0)

    # Metrics
    in_grounded = sum(1 for r in in_results if not r["is_refusal"] and r["has_citations"])
    out_refused = sum(1 for r in out_results if r["is_refusal"])

    print("\n" + "=" * 72, flush=True)
    print(">> BENCHMARK VERIFICATION RESULTS", flush=True)
    print("-" * 72, flush=True)
    print(f" Near-Miss Refusal Rate:      {out_refused}/{len(out_queries)}", flush=True)
    print(f" In-Corpus Grounding/Citation: {in_grounded}/{len(in_queries)}", flush=True)
    print("=" * 72, flush=True)

    report_path = PROJECT_ROOT / "eval" / "rag_benchmark_report.json"
    report_data = {
        "near_miss_refused": f"{out_refused}/{len(out_queries)}",
        "in_corpus_grounded": f"{in_grounded}/{len(in_queries)}",
        "in_corpus_results": in_results,
        "out_of_corpus_results": out_results,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"Audit log written to eval/{report_path.name}\n", flush=True)
    return report_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--count", type=int, default=5, help="Number of queries per set")
    args = parser.parse_args()
    asyncio.run(evaluate_rag_citations_and_refusal(sample_count=args.count))
