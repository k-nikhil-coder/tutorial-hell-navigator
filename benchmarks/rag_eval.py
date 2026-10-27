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

IN_CORPUS_QUERIES = [
    "How do I fix a CORS preflight error in FastAPI when connecting from React?",
    "Why does psycopg2 fail to compile in my Docker container with missing pg_config?",
    "How to mount CORSMiddleware in FastAPI with explicit origins?",
    "What is the multi-stage Dockerfile pattern for Python FastAPI apps?",
    "How do I handle SQLite database locked operational errors in async FastAPI?",
    "How do I fix Docker daemon connection refused on /var/run/docker.sock?",
    "What is the fix for JWT ExpiredSignatureError in Python auth endpoints?",
    "How to resolve git merge conflict markers in a pull request?",
    "How to fix port already in use EADDRINUSE on port 8000 for uvicorn?",
    "How do I diagnose Time Limit Exceeded (TLE) and recursion depth errors in Python?",
    "What are the 7-day milestones to build a FastAPI microservice from scratch?",
    "What is the standard clean architecture directory tree for a FastAPI application?",
    "How do I integrate PostgreSQL and async migrations in a FastAPI app?",
    "How should I organize a fullstack repository with React and FastAPI?",
    "How do I write unit and integration tests using pytest and httpx for FastAPI?",
    "What libraries are needed to compile native C wheels in a Python slim image?",
    "How to use Pydantic v2 schemas for request validation in FastAPI?",
    "How do I configure non-root user and HEALTHCHECK in Dockerfile?",
    "What is the difference between single-stage and multi-stage Docker builds for Python?",
    "How to set up JWT authentication with password hashing in a REST API?",
]

OUT_OF_CORPUS_QUERIES = [
    "How do I bake a moist chocolate cake with buttercream frosting?",
    "Explain the LBW (Leg Before Wicket) rule in cricket.",
    "What is the plot summary of the movie Inception?",
    "How do I prune tomato plants in a home garden?",
    "What are the best tips to train a puppy to stop biting?",
    "How do I brew a proper espresso shot using an espresso machine?",
    "What caused the fall of the Western Roman Empire?",
    "How do I change the engine oil on a Honda Civic?",
    "What are the rules of the Sicilian Defense in chess?",
    "How do I tune an acoustic guitar to standard EADGBE tuning?",
    "How do I fix a leaking bathroom faucet cartridge?",
    "What are the fundamental poses in Hatha yoga for beginners?",
    "How do I roll traditional sushi with nori and seasoned rice?",
    "What permits are required to climb Mount Everest from Nepal?",
    "Why did the dinosaurs go extinct 66 million years ago?",
    "How do I paint a sunset landscape using watercolor techniques?",
    "What is the difference between sourdough and commercial yeast bread?",
    "How do I replace a flat inner tube on a bicycle tire?",
    "What are the top tourist attractions to visit in Kyoto, Japan?",
    "How do astronomers detect supermassive black holes in deep space?",
]


async def evaluate_rag_citations_and_refusal(sample_count: int = 10):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    in_queries = IN_CORPUS_QUERIES[:sample_count]
    out_queries = OUT_OF_CORPUS_QUERIES[:sample_count]

    print("=" * 70, flush=True)
    print(">> TUTORIAL HELL NAVIGATOR - RAG GROUNDING & REFUSAL BENCHMARK", flush=True)
    print(f" In-Corpus Test Set:     {len(in_queries)} queries (FastAPI, Docker, Architecture)", flush=True)
    print(f" Out-of-Corpus Test Set: {len(out_queries)} queries (Baking, Sports, Gardening, Cars)", flush=True)
    print("=" * 70, flush=True)

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
            cite_str = ", ".join(cited) if cited else "None"
            print(f"  [{i:2d}/{len(in_queries)}] Citations: {cite_str:35s} | Q: {q[:45]}...", flush=True)
        except Exception as e:
            print(f"  [{i:2d}/{len(in_queries)}] ERROR: {e} | Q: {q[:45]}...", flush=True)
            in_results.append({"index": i, "query": q, "is_refusal": False, "has_citations": False, "error": str(e)})
        await asyncio.sleep(2.0)  # Safe delay to respect Free Tier 15 RPM limit

    out_results = []
    print("\n[2/2] Testing Out-of-Corpus Refusal Path...", flush=True)
    for i, q in enumerate(out_queries, 1):
        try:
            resp = await generate_structured_response_async(q)
            out_results.append({
                "index": i, "query": q, "is_refusal": resp.is_refusal,
                "refusal_reason": resp.refusal_reason
            })
            refusal_tag = "[REFUSED]" if resp.is_refusal else "[FAILED REFUSAL]"
            print(f"  [{i:2d}/{len(out_queries)}] {refusal_tag:16s} | Q: {q[:45]}...", flush=True)
        except Exception as e:
            print(f"  [{i:2d}/{len(out_queries)}] ERROR: {e} | Q: {q[:45]}...", flush=True)
            out_results.append({"index": i, "query": q, "is_refusal": False, "error": str(e)})
        await asyncio.sleep(2.0)

    # Metrics
    in_grounded = sum(1 for r in in_results if not r["is_refusal"] and r["has_citations"])
    out_refused = sum(1 for r in out_results if r["is_refusal"])

    print("\n" + "=" * 70, flush=True)
    print(">> BENCHMARK VERIFICATION RESULTS", flush=True)
    print("-" * 70, flush=True)
    print(f" Out-of-Corpus Refusal Rate:  {out_refused}/{len(out_queries)} ({out_refused/len(out_queries)*100:.1f}%)", flush=True)
    print(f" In-Corpus Grounding/Citation: {in_grounded}/{len(in_queries)} ({in_grounded/len(in_queries)*100:.1f}%)", flush=True)
    print("=" * 70, flush=True)

    report_path = PROJECT_ROOT / "eval" / "rag_benchmark_report.json"
    report_data = {
        "out_of_corpus_refused": f"{out_refused}/{len(out_queries)}",
        "out_of_corpus_refusal_rate_pct": out_refused / len(out_queries) * 100,
        "in_corpus_grounded": f"{in_grounded}/{len(in_queries)}",
        "in_corpus_grounding_rate_pct": in_grounded / len(in_queries) * 100,
        "in_corpus_results": in_results,
        "out_of_corpus_results": out_results,
    }
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report_data, f, indent=2)
    print(f"Detailed audit log written to eval/{report_path.name}\n", flush=True)
    return report_data


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--count", type=int, default=10, help="Number of queries per set")
    args = parser.parse_args()
    asyncio.run(evaluate_rag_citations_and_refusal(sample_count=args.count))
