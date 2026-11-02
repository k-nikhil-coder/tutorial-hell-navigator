import os
import sys
import json
import time
import math
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple, Set
from datetime import datetime, timezone
from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass
if hasattr(sys.stderr, "reconfigure"):
    try:
        sys.stderr.reconfigure(line_buffering=True, encoding="utf-8", errors="replace")
    except Exception:
        pass

load_dotenv()

from google import genai
from google.genai import types, errors
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
import httpx

from app.schemas import NavigatorResponse
from app.rag import retrieve_relevant_chunks, format_retrieved_context

PINNED_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
CHUNKS_FILE = PROJECT_ROOT / "corpus" / "processed" / "chunks_512.json"
CACHE_FILE = PROJECT_ROOT / "data" / "baseline_responses_cache.json"

GROUNDED_QUESTION_IDS = [
    "GS-01", "GS-02", "GS-03", "GS-04", "GS-05", "GS-06", "GS-07", "GS-08",
    "GS-09", "GS-10", "GS-11", "GS-12", "GS-13", "GS-14", "GS-15",
    "GS-17", "GS-18", "GS-19", "GS-20", "GS-22", "GS-23", "GS-24",
    "GS-81", "GS-82", "GS-83", "GS-84", "GS-85", "GS-86", "GS-87", "GS-88",
]

VAGUE_PHRASES = [
    "keep practicing",
    "just practice more",
    "copy and paste this",
    "just google it",
    "don't worry about understanding",
    "here is the complete code for everything",
]

SYSTEM_PROMPT_RAG = (
    "You are Tutorial Hell Navigator, an eval-first technical mentor for computer science students. "
    "Your mission is to transition students from passive tutorial copying to independent software engineering. "
    "You must ground your guidance in the provided verified technical context when available. "
    "\n\nSTRICT CITATION & ACTION RULES:\n"
    "1. CITATIONS: In your action_plan, each ActionableStep MUST include the exact chunk_id (e.g. 'fastapi_fullstack_guide_chunk_2') in its 'citations' list for every technical claim made.\n"
    "2. OUT-OF-CORPUS REFUSAL: If the provided verified context is empty or does not contain information to answer the question, you MUST:\n"
    "   - Set is_refusal = True\n"
    "   - Set refusal_reason = 'Question is out-of-corpus and cannot be verified against the technical documentation.'\n"
    "   - State clearly in the summary that the question is outside the scope of the verified corpus.\n"
    "   - Provide 1 advisory step pointing to standard documentation resources rather than inventing commands.\n"
    "3. ACTIONABLE CLI COMMANDS: For all in-corpus technical guidance, you MUST provide explicit, runnable terminal CLI commands or code snippets in the 'command' field of your action steps (e.g., project initialization, dependency installs, running dev servers, or verification scripts). Never leave commands null when guiding a student through a stack or solution.\n"
    "4. ANTI-PATTERNS: Provide mandatory, concrete anti-patterns and pitfalls to avoid."
)

SYSTEM_PROMPT_ZERO = (
    "You are Tutorial Hell Navigator, an eval-first technical mentor for computer science students. "
    "Your mission is to transition students from passive tutorial copying to independent software engineering. "
    "Answer the student question using your internal pre-trained software engineering knowledge. "
    "You do not have access to an external retrieval database or documentation corpus. "
    "\n\nACTION RULES:\n"
    "1. ACTIONABLE CLI COMMANDS: Provide explicit, runnable terminal CLI commands or code snippets in the 'command' field of your action steps. Never leave commands null when guiding a student through a stack or solution.\n"
    "2. ANTI-PATTERNS: Provide mandatory, concrete anti-patterns and pitfalls to avoid in your action plan.\n"
    "3. CITATIONS: In your action_plan, each ActionableStep has a 'citations' list. If you do not have verified chunk IDs from an external retrieval engine, leave the citations list empty or cite relevant documentation if known."
)


def is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, (errors.ServerError, httpx.RequestError)):
        return True
    if isinstance(exc, errors.ClientError) and exc.code == 429:
        return True
    msg = str(exc).lower()
    return any(term in msg for term in ["503", "unavailable", "resource_exhausted", "rate limit", "timeout", "quota"])


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY environment variable.")
    return genai.Client(api_key=api_key)


def load_corpus_chunks() -> Tuple[List[Dict[str, Any]], Set[str], str]:
    """Load all 67 chunks and build the full-corpus context string."""
    if not CHUNKS_FILE.exists():
        raise FileNotFoundError(f"Corpus chunks not found at {CHUNKS_FILE}")
    with open(CHUNKS_FILE, "r", encoding="utf-8") as f:
        chunks = json.load(f)
    chunk_ids = {c["chunk_id"] for c in chunks}
    context_str = format_retrieved_context(chunks)
    return chunks, chunk_ids, context_str


def load_cache() -> Dict[str, Any]:
    if CACHE_FILE.exists():
        try:
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_cache(cache: Dict[str, Any]):
    try:
        CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to save cache: {e}")


def calculate_percentile(values: List[float], percentile: float) -> float:
    if not values:
        return 0.0
    sorted_v = sorted(values)
    k = (len(sorted_v) - 1) * (percentile / 100.0)
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return round(sorted_v[int(k)], 2)
    d0 = sorted_v[int(f)] * (c - k)
    d1 = sorted_v[int(c)] * (k - f)
    return round(d0 + d1, 2)


@retry(
    retry=retry_if_exception(is_transient_error),
    stop=stop_after_attempt(5),
    wait=wait_exponential(multiplier=2, min=4, max=30),
    reraise=True,
)
def call_pinned_model(
    client: genai.Client,
    prompt: str,
    system_prompt: str,
    model_name: str = PINNED_MODEL,
) -> Tuple[str, float]:
    """Directly call pinned model without fallback chain contamination."""
    t_start = time.perf_counter()
    response = client.models.generate_content(
        model=model_name,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_schema=NavigatorResponse,
            response_mime_type="application/json",
            temperature=0.1,
            system_instruction=system_prompt,
        ),
    )
    latency_ms = round((time.perf_counter() - t_start) * 1000, 2)
    return response.text, latency_ms


def score_response(
    response: NavigatorResponse,
    expected_rubric: List[str],
    negative_constraints: List[str],
    expected_chunk_ids: List[str],
    valid_corpus_chunk_ids: Set[str],
) -> Dict[str, Any]:
    issues = []

    commands = [step.command for step in response.action_plan if step.command]
    if not commands and not response.is_refusal:
        issues.append("Action plan is missing CLI commands or code snippets.")

    if not response.anti_patterns_to_avoid:
        issues.append("Missing anti-patterns section.")

    haystack = (
        response.summary
        + " "
        + " ".join(s.explanation for s in response.action_plan)
        + " "
        + " ".join(response.anti_patterns_to_avoid)
    ).lower()

    for phrase in VAGUE_PHRASES:
        if phrase in haystack:
            issues.append(f"Contains generic advice phrase: '{phrase}'")

    for neg in negative_constraints:
        if neg.lower() in haystack:
            issues.append(f"Hit negative constraint: '{neg}'")

    # Citations analysis
    all_citations = []
    for s in response.action_plan:
        if s.citations:
            all_citations.extend(s.citations)
    cited_chunks = list(dict.fromkeys(all_citations))

    valid_citations = [cid for cid in cited_chunks if cid in valid_corpus_chunk_ids]
    hallucinated_citations = [cid for cid in cited_chunks if cid not in valid_corpus_chunk_ids]

    expected_set = set(expected_chunk_ids)
    ground_truth_hits = [cid for cid in valid_citations if cid in expected_set]

    citation_precision = (
        round(len(ground_truth_hits) / len(cited_chunks), 4) if cited_chunks else 0.0
    )
    citation_recall = (
        round(len(ground_truth_hits) / len(expected_set), 4) if expected_set else 0.0
    )
    hallucination_rate = (
        round(len(hallucinated_citations) / len(cited_chunks), 4) if cited_chunks else 0.0
    )

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "step_count": len(response.action_plan),
        "command_count": len(commands),
        "citation_count": len(cited_chunks),
        "cited_chunks": cited_chunks,
        "valid_citations": valid_citations,
        "hallucinated_citations": hallucinated_citations,
        "ground_truth_hits": ground_truth_hits,
        "citation_precision": citation_precision,
        "citation_recall": citation_recall,
        "hallucination_rate": hallucination_rate,
        "is_refusal": response.is_refusal,
    }


def run_configuration_on_batch(
    config_name: str,
    questions: List[Dict[str, Any]],
    client: genai.Client,
    valid_corpus_ids: Set[str],
    full_corpus_context_str: str,
    cache: Dict[str, Any],
    delay: float = 4.2,
) -> Dict[str, Any]:
    print("\n" + "=" * 78)
    print(f"🚀 RUNNING CONFIGURATION: {config_name.upper()} (Pinned Model: {PINNED_MODEL})")
    print(f"   Questions to evaluate: {len(questions)}")
    print("=" * 78)

    results = []
    passed_count = 0
    refusal_count = 0
    latencies = []
    prompt_token_estimates = []
    total_commands = 0
    total_valid_cites = 0
    total_hallucinated_cites = 0
    total_gt_cites = 0

    for idx, q in enumerate(questions, 1):
        qid = q["id"]
        question_text = q["question"]
        expected_chunk_ids = q.get("expected_chunk_ids", [])
        expected_rubric = q.get("expected_rubric", [])
        negative_constraints = q.get("negative_constraints", [])
        cache_key = f"{config_name}::{qid}"

        retrieved_ids = []

        if cache_key in cache:
            cached_data = cache[cache_key]
            raw_text = cached_data["raw_text"]
            latency_ms = cached_data["latency_ms"]
            prompt_tokens = cached_data["prompt_tokens"]
            retrieved_ids = cached_data.get("retrieved_ids", [])
            resp_model = NavigatorResponse.model_validate_json(raw_text)
            status_source = "[CACHED]"
        else:
            status_source = "[LIVE]"
            if config_name == "zero_retrieval":
                prompt = f"STUDENT QUESTION:\n{question_text}"
                sys_prompt = SYSTEM_PROMPT_ZERO
            elif config_name == "full_corpus":
                prompt = f"VERIFIED CONTEXT:\n{full_corpus_context_str}\n\nSTUDENT QUESTION:\n{question_text}"
                sys_prompt = SYSTEM_PROMPT_RAG
            elif config_name == "current_pipeline":
                # Hybrid Search + Reranker (top K=3)
                top_chunks = retrieve_relevant_chunks(question_text, top_k=3, search_mode="hybrid-rerank")
                retrieved_ids = [c["chunk_id"] for c in top_chunks]
                context_str = format_retrieved_context(top_chunks)
                prompt = f"VERIFIED CONTEXT:\n{context_str}\n\nSTUDENT QUESTION:\n{question_text}"
                sys_prompt = SYSTEM_PROMPT_RAG
            else:
                raise ValueError(f"Unknown config_name: {config_name}")

            prompt_tokens = len(prompt) // 4 + len(sys_prompt) // 4

            try:
                raw_text, latency_ms = call_pinned_model(
                    client=client,
                    prompt=prompt,
                    system_prompt=sys_prompt,
                )
                resp_model = NavigatorResponse.model_validate_json(raw_text)
                cache[cache_key] = {
                    "raw_text": raw_text,
                    "latency_ms": latency_ms,
                    "prompt_tokens": prompt_tokens,
                    "retrieved_ids": retrieved_ids,
                }
                save_cache(cache)
            except Exception as e:
                print(f"[{idx:02d}/{len(questions):02d}] {qid} ERROR: {e}")
                continue

            if idx < len(questions) and delay > 0:
                time.sleep(delay)

        score = score_response(
            response=resp_model,
            expected_rubric=expected_rubric,
            negative_constraints=negative_constraints,
            expected_chunk_ids=expected_chunk_ids,
            valid_corpus_chunk_ids=valid_corpus_ids,
        )

        latencies.append(latency_ms)
        prompt_token_estimates.append(prompt_tokens)
        total_commands += score["command_count"]
        total_valid_cites += len(score["valid_citations"])
        total_hallucinated_cites += len(score["hallucinated_citations"])
        total_gt_cites += len(score["ground_truth_hits"])

        if score["passed"]:
            passed_count += 1
        if score["is_refusal"]:
            refusal_count += 1

        pass_label = "PASS" if score["passed"] else "FAIL"
        cite_info = f"Cites: {score['citation_count']} (Valid: {len(score['valid_citations'])}, GT: {len(score['ground_truth_hits'])}, Hallucinated: {len(score['hallucinated_citations'])})"
        print(
            f"[{idx:02d}/{len(questions):02d}] {qid} {status_source}: {pass_label} | {latency_ms:.1f}ms | ~{prompt_tokens} tokens | {cite_info}"
        )

        results.append({
            "id": qid,
            "question": question_text,
            "expected_chunk_ids": expected_chunk_ids,
            "retrieved_chunk_ids": retrieved_ids,
            "latency_ms": latency_ms,
            "prompt_tokens_est": prompt_tokens,
            "score": score,
            "response": resp_model.model_dump(),
        })

    n = len(results) or 1
    mean_lat = round(sum(latencies) / n, 2)
    p50_lat = calculate_percentile(latencies, 50.0)
    p90_lat = calculate_percentile(latencies, 90.0)
    p95_lat = calculate_percentile(latencies, 95.0)
    pass_rate = round((passed_count / n) * 100, 2)
    avg_tokens = round(sum(prompt_token_estimates) / n)
    avg_commands = round(total_commands / n, 2)

    return {
        "configuration": config_name,
        "pinned_model": PINNED_MODEL,
        "evaluated_count": n,
        "pass_rate_pct": pass_rate,
        "passed_count": passed_count,
        "refusal_count": refusal_count,
        "avg_commands_per_plan": avg_commands,
        "avg_prompt_tokens": avg_tokens,
        "total_valid_citations": total_valid_cites,
        "total_hallucinated_citations": total_hallucinated_cites,
        "total_ground_truth_citations": total_gt_cites,
        "latency_metrics": {
            "mean_latency_ms": mean_lat,
            "p50_latency_ms": p50_lat,
            "p90_latency_ms": p90_lat,
            "p95_latency_ms": p95_lat,
            "min_latency_ms": min(latencies) if latencies else 0.0,
            "max_latency_ms": max(latencies) if latencies else 0.0,
        },
        "items": results,
    }


def main():
    parser = argparse.ArgumentParser(description="Baseline Comparison Benchmark (Zero vs Full vs Current Pipeline)")
    parser.add_argument("--gold-set", default="eval/gold_set.json", help="Path to gold set json")
    parser.add_argument(
        "--config",
        choices=["zero_retrieval", "full_corpus", "current_pipeline", "all"],
        default="all",
        help="Configuration to run",
    )
    parser.add_argument("-n", "--limit", type=int, default=30, help="Number of grounded questions to test")
    parser.add_argument("-d", "--delay", type=float, default=4.2, help="Delay in seconds between requests (15 RPM cap)")
    parser.add_argument("-o", "--output", default="eval/baseline_comparison_report.json", help="Output JSON path")
    args = parser.parse_args()

    # Load questions
    with open(args.gold_set, "r", encoding="utf-8") as f:
        gold_data = json.load(f)

    # Filter strictly to the 30 grounded questions
    grounded_lookup = {q["id"]: q for q in gold_data if q["id"] in GROUNDED_QUESTION_IDS}
    grounded_batch = [grounded_lookup[qid] for qid in GROUNDED_QUESTION_IDS if qid in grounded_lookup]
    if args.limit:
        grounded_batch = grounded_batch[:args.limit]

    print(f"Loaded {len(grounded_batch)} grounded questions for baseline showdown.")

    # Load corpus
    chunks, valid_cids, full_corpus_context_str = load_corpus_chunks()
    print(f"Corpus loaded: {len(chunks)} chunks ({len(full_corpus_context_str)} characters, ~{len(full_corpus_context_str)//4} tokens)")

    client = get_genai_client()
    cache = load_cache()

    configs_to_run = (
        ["zero_retrieval", "full_corpus", "current_pipeline"]
        if args.config == "all"
        else [args.config]
    )

    all_reports = {}
    for cfg in configs_to_run:
        rep = run_configuration_on_batch(
            config_name=cfg,
            questions=grounded_batch,
            client=client,
            valid_corpus_ids=valid_cids,
            full_corpus_context_str=full_corpus_context_str,
            cache=cache,
            delay=args.delay,
        )
        all_reports[cfg] = rep

    # Comparative Summary Table
    print("\n" + "=" * 90)
    print("🏆 THREE-WAY BASELINE SHOWDOWN SUMMARY (PINNED MODEL: " + PINNED_MODEL + ")")
    print("=" * 90)
    print(f"{'Metric':<30} | {'Zero-Retrieval (Weights)':<24} | {'Full-Corpus-in-Context':<24} | {'Current Pipeline (K=3)':<24}")
    print("-" * 90)

    zr = all_reports.get("zero_retrieval")
    fc = all_reports.get("full_corpus")
    cp = all_reports.get("current_pipeline")

    def fmt_val(d, key, suffix=""):
        return f"{d[key]}{suffix}" if d and key in d else "N/A"

    def fmt_lat(d, key):
        return f"{d['latency_metrics'][key]:.1f} ms" if d and "latency_metrics" in d else "N/A"

    print(f"{'Pass Rate':<30} | {fmt_val(zr, 'pass_rate_pct', '%'):<24} | {fmt_val(fc, 'pass_rate_pct', '%'):<24} | {fmt_val(cp, 'pass_rate_pct', '%'):<24}")
    print(f"{'Avg Prompt Tokens':<30} | {fmt_val(zr, 'avg_prompt_tokens'):<24} | {fmt_val(fc, 'avg_prompt_tokens'):<24} | {fmt_val(cp, 'avg_prompt_tokens'):<24}")
    print(f"{'Mean Latency':<30} | {fmt_lat(zr, 'mean_latency_ms'):<24} | {fmt_lat(fc, 'mean_latency_ms'):<24} | {fmt_lat(cp, 'mean_latency_ms'):<24}")
    print(f"{'P50 Latency':<30} | {fmt_lat(zr, 'p50_latency_ms'):<24} | {fmt_lat(fc, 'p50_latency_ms'):<24} | {fmt_lat(cp, 'p50_latency_ms'):<24}")
    print(f"{'P95 Latency':<30} | {fmt_lat(zr, 'p95_latency_ms'):<24} | {fmt_lat(fc, 'p95_latency_ms'):<24} | {fmt_lat(cp, 'p95_latency_ms'):<24}")
    print(f"{'Total Valid Citations':<30} | {fmt_val(zr, 'total_valid_citations'):<24} | {fmt_val(fc, 'total_valid_citations'):<24} | {fmt_val(cp, 'total_valid_citations'):<24}")
    print(f"{'Total Ground-Truth Citations':<30} | {fmt_val(zr, 'total_ground_truth_citations'):<24} | {fmt_val(fc, 'total_ground_truth_citations'):<24} | {fmt_val(cp, 'total_ground_truth_citations'):<24}")
    print(f"{'Total Hallucinated Citations':<30} | {fmt_val(zr, 'total_hallucinated_citations'):<24} | {fmt_val(fc, 'total_hallucinated_citations'):<24} | {fmt_val(cp, 'total_hallucinated_citations'):<24}")
    print(f"{'Refusals Handled':<30} | {fmt_val(zr, 'refusal_count'):<24} | {fmt_val(fc, 'refusal_count'):<24} | {fmt_val(cp, 'refusal_count'):<24}")
    print("=" * 90)

    final_payload = {
        "benchmark": "Three-Way Baseline Showdown",
        "pinned_model": PINNED_MODEL,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_grounded_questions": len(grounded_batch),
        "configurations": all_reports,
    }

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(final_payload, f, indent=2)
    print(f"\nSaved detailed comparison artifact to: {args.output}")


if __name__ == "__main__":
    main()
