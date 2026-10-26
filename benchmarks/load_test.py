import sys
import time
import math
import argparse
import asyncio
from typing import List, Dict, Any
import httpx

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from app.main import app
    HAS_APP = True
except ImportError:
    HAS_APP = False


def calculate_percentile(sorted_data: List[float], percentile: float) -> float:
    """Calculate the p-th percentile from an already sorted list of numbers."""
    if not sorted_data:
        return 0.0
    if len(sorted_data) == 1:
        return sorted_data[0]
    rank = (len(sorted_data) - 1) * (percentile / 100.0)
    low = math.floor(rank)
    high = math.ceil(rank)
    if low == high:
        return sorted_data[int(rank)]
    return sorted_data[low] * (high - rank) + sorted_data[high] * (rank - low)


async def send_request(
    client: httpx.AsyncClient,
    sem: asyncio.Semaphore,
    url: str,
    query: str,
    is_stream: bool,
    req_id: int,
    timeout: float = 60.0,
) -> Dict[str, Any]:
    async with sem:
        start = time.perf_counter()
        try:
            if is_stream:
                async with client.stream("POST", url, json={"query": query}, timeout=timeout) as resp:
                    chunks = 0
                    async for _ in resp.aiter_lines():
                        chunks += 1
                    latency = (time.perf_counter() - start) * 1000.0
                    return {"id": req_id, "status": resp.status_code, "latency_ms": latency, "chunks": chunks}
            else:
                resp = await client.post(url, json={"query": query}, timeout=timeout)
                latency = (time.perf_counter() - start) * 1000.0
                return {"id": req_id, "status": resp.status_code, "latency_ms": latency, "chunks": 1}
        except Exception as e:
            latency = (time.perf_counter() - start) * 1000.0
            return {"id": req_id, "status": "FAILED", "latency_ms": latency, "chunks": 0, "error": str(e)}


async def run_benchmark(
    url: str = "http://localhost:8000/navigate",
    query: str = "How do I fix a CORS error in FastAPI?",
    total_requests: int = 5,
    concurrency_limit: int = 3,
    is_stream: bool = False,
    timeout: float = 60.0,
    force_in_process: bool = False,
) -> Dict[str, Any]:
    sem = asyncio.Semaphore(concurrency_limit)

    use_asgi = force_in_process
    if not force_in_process:
        try:
            async with httpx.AsyncClient(timeout=2.0) as test_client:
                r = await test_client.get(url.rsplit("/", 1)[0] + "/health")
                if r.status_code != 200:
                    use_asgi = True
        except Exception:
            use_asgi = True

    transport = httpx.ASGITransport(app=app) if (use_asgi and HAS_APP) else None
    base_url = "http://testserver" if use_asgi else None

    if use_asgi:
        endpoint = "/navigate/stream" if is_stream else "/navigate"
        target_url = f"http://testserver{endpoint}"
    else:
        if is_stream and not url.endswith("/stream"):
            target_url = url.rstrip("/") + "/stream"
        else:
            target_url = url

    client_opts: Dict[str, Any] = {"timeout": timeout}
    if transport:
        client_opts["transport"] = transport
        client_opts["base_url"] = base_url

    print("-" * 60)
    print("Benchmark Configuration:")
    print(f"  Target:        {target_url} ({'ASGI in-memory' if use_asgi else 'HTTP network'})")
    print(f"  Mode:          {'SSE Streaming' if is_stream else 'Structured JSON'}")
    print(f"  Total Requests: {total_requests}")
    print(f"  Concurrency:   {concurrency_limit}")
    print(f"  Sample Prompt: '{query[:40]}...'")
    print("-" * 60)

    start_time = time.perf_counter()

    async with httpx.AsyncClient(**client_opts) as client:
        tasks = [
            send_request(
                client=client,
                sem=sem,
                url=target_url,
                query=query,
                is_stream=is_stream,
                req_id=i + 1,
                timeout=timeout,
            )
            for i in range(total_requests)
        ]
        results = await asyncio.gather(*tasks)

    elapsed = time.perf_counter() - start_time
    rps = total_requests / elapsed if elapsed > 0 else 0

    status_counts: Dict[Any, int] = {}
    latencies: List[float] = []

    for r in results:
        code = r["status"]
        status_counts[code] = status_counts.get(code, 0) + 1
        if code == 200:
            latencies.append(r["latency_ms"])

    latencies.sort()
    success_count = len(latencies)
    success_rate = (success_count / total_requests) * 100.0

    p50 = calculate_percentile(latencies, 50)
    p90 = calculate_percentile(latencies, 90)
    p95 = calculate_percentile(latencies, 95)
    p99 = calculate_percentile(latencies, 99)
    min_lat = latencies[0] if latencies else 0.0
    max_lat = latencies[-1] if latencies else 0.0
    avg_lat = sum(latencies) / len(latencies) if latencies else 0.0

    print("Results:")
    print(f"  Duration:      {elapsed:.2f}s")
    print(f"  Throughput:    {rps:.2f} req/s")
    print(f"  Success Rate:  {success_count}/{total_requests} ({success_rate:.1f}%)")
    print(f"  Status Codes:  {status_counts}")

    failures = [r for r in results if r["status"] != 200]
    if failures:
        print("\nErrors:")
        for f in failures[:3]:
            print(f"  Req #{f['id']} (status={f['status']}): {f.get('error')}")

    print("\nLatency Breakdown (ms):")
    print(f"  Min:  {min_lat:8.1f}")
    print(f"  P50:  {p50:8.1f}")
    print(f"  P90:  {p90:8.1f}")
    print(f"  P95:  {p95:8.1f}")
    print(f"  P99:  {p99:8.1f}")
    print(f"  Max:  {max_lat:8.1f}")
    print(f"  Avg:  {avg_lat:8.1f}")
    print("-" * 60)

    return {
        "total_requests": total_requests,
        "concurrency_limit": concurrency_limit,
        "elapsed_seconds": elapsed,
        "rps": rps,
        "success_rate": success_rate,
        "status_counts": status_counts,
        "latencies": {
            "min": min_lat,
            "p50": p50,
            "p90": p90,
            "p95": p95,
            "p99": p99,
            "max": max_lat,
            "avg": avg_lat,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Navigator Concurrency & Load Tester")
    parser.add_argument("--url", default="http://localhost:8000/navigate", help="Target endpoint")
    parser.add_argument("-n", "--requests", type=int, default=3, help="Total requests to send")
    parser.add_argument("-c", "--concurrency", type=int, default=2, help="Concurrency limit")
    parser.add_argument("-q", "--query", default="How do I fix a CORS error in FastAPI?", help="Query prompt")
    parser.add_argument("--stream", action="store_true", help="Test the SSE streaming endpoint")
    parser.add_argument("--in-process", action="store_true", help="Force ASGI in-memory transport")
    parser.add_argument("--timeout", type=float, default=60.0, help="Request timeout in seconds")

    args = parser.parse_args()

    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

    summary = asyncio.run(
        run_benchmark(
            url=args.url,
            query=args.query,
            total_requests=args.requests,
            concurrency_limit=args.concurrency,
            is_stream=args.stream,
            timeout=args.timeout,
            force_in_process=args.in_process,
        )
    )

    if summary["success_rate"] == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
