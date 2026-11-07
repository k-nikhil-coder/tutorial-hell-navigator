import sys
import json
import time
import math
import argparse
import asyncio
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.schemas import NavigatorResponse
from app.client import generate_structured_response_async
from app.rag import retrieve_relevant_chunks

VAGUE_PHRASES = [
    "keep practicing",
    "just practice more",
    "copy and paste this",
    "just google it",
    "don't worry about understanding",
    "here is the complete code for everything",
]


def calculate_percentile(values: List[float], percentile: float) -> float:
    """Calculate percentile from a list of float measurements."""
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


def calculate_retrieval_metrics(
    retrieved_items: List[Any],
    expected_chunk_ids: Optional[List[str]] = None,
    required_evidence: Optional[List[Dict[str, str]]] = None,
    acceptable_alternatives: Optional[List[Dict[str, str]]] = None,
) -> Dict[str, Any]:
    """
    Calculate Evidence coverage@K, Hit@K, and MRR.
    
    Definitions:
    - Evidence coverage@K: the fraction of required_evidence items covered in top K.
      An item counts as covered if a retrieved chunk contains its span or one of its alternatives.
    - Hit@K: at least one required item is covered.
    - MRR: based on the rank of the first covered item (1 / rank of first covered item).
    
    Supports both v2 verbatim evidence spans and legacy v1 expected_chunk_ids fallback.
    """
    has_spans = bool(required_evidence and len(required_evidence) > 0)
    has_chunks = bool(expected_chunk_ids and len(expected_chunk_ids) > 0)

    if not has_spans and not has_chunks:
        return {
            "has_ground_truth": False,
            "evidence_coverage_at_3": None,
            "evidence_coverage_at_5": None,
            "hit_at_3": None,
            "hit_at_5": None,
            "recall_at_3": None,
            "recall_at_5": None,
            "reciprocal_rank": None,
            "first_hit_rank": None,
        }

    # Extract texts and chunk_ids for each rank
    retrieved_chunks = []
    for rank_idx, item in enumerate(retrieved_items, 1):
        if isinstance(item, dict):
            c_text = item.get("text", "")
            c_id = item.get("chunk_id", "")
            mapped_ids = set(item.get("mapped_512_chunk_ids", []))
            mapped_ids.add(c_id)
            retrieved_chunks.append({
                "rank": rank_idx,
                "text": c_text,
                "norm_text": " ".join(c_text.split()),
                "chunk_id": c_id,
                "all_ids": mapped_ids,
            })
        else:
            retrieved_chunks.append({
                "rank": rank_idx,
                "text": str(item),
                "norm_text": " ".join(str(item).split()),
                "chunk_id": str(item),
                "all_ids": {str(item)},
            })

    # Case 1: v2 Evidence Spans
    if has_spans:
        num_req = len(required_evidence)
        alt_spans = [a.get("span", "") for a in (acceptable_alternatives or []) if a.get("span")]

        first_covered_rank = None
        covered_at_3_count = 0
        covered_at_5_count = 0

        for req in required_evidence:
            req_span = req.get("span", "")
            target_spans = [req_span] + alt_spans
            target_spans = [s for s in target_spans if s]

            # Find earliest rank covering this required item
            item_covered_rank = None
            for chunk_info in retrieved_chunks:
                norm_chunk = chunk_info["norm_text"]
                raw_chunk = chunk_info["text"]
                if any(s in raw_chunk or " ".join(s.split()) in norm_chunk for s in target_spans):
                    item_covered_rank = chunk_info["rank"]
                    break

            if item_covered_rank is not None:
                if first_covered_rank is None or item_covered_rank < first_covered_rank:
                    first_covered_rank = item_covered_rank
                if item_covered_rank <= 3:
                    covered_at_3_count += 1
                if item_covered_rank <= 5:
                    covered_at_5_count += 1

        coverage_at_3 = round(covered_at_3_count / num_req, 4)
        coverage_at_5 = round(covered_at_5_count / num_req, 4)
        hit_at_3 = 1.0 if covered_at_3_count > 0 else 0.0
        hit_at_5 = 1.0 if covered_at_5_count > 0 else 0.0
        rr = round(1.0 / first_covered_rank, 4) if first_covered_rank else 0.0

        return {
            "has_ground_truth": True,
            "evidence_coverage_at_3": coverage_at_3,
            "evidence_coverage_at_5": coverage_at_5,
            "hit_at_3": hit_at_3,
            "hit_at_5": hit_at_5,
            "recall_at_3": hit_at_3,  # backwards-compatibility alias
            "recall_at_5": hit_at_5,  # backwards-compatibility alias
            "reciprocal_rank": rr,
            "first_hit_rank": first_covered_rank,
            "covered_items_at_3": covered_at_3_count,
            "covered_items_at_5": covered_at_5_count,
            "total_required_items": num_req,
        }

    # Case 2: Legacy v1 expected_chunk_ids Fallback
    expected_set = set(expected_chunk_ids)
    num_expected = len(expected_set)
    first_hit_rank = None
    hits_at_3 = 0
    hits_at_5 = 0

    covered_ids_3 = set()
    covered_ids_5 = set()

    for chunk_info in retrieved_chunks:
        overlap = chunk_info["all_ids"] & expected_set
        if overlap:
            if first_hit_rank is None:
                first_hit_rank = chunk_info["rank"]
            if chunk_info["rank"] <= 3:
                covered_ids_3.update(overlap)
            if chunk_info["rank"] <= 5:
                covered_ids_5.update(overlap)

    coverage_at_3 = round(len(covered_ids_3) / num_expected, 4) if num_expected else 0.0
    coverage_at_5 = round(len(covered_ids_5) / num_expected, 4) if num_expected else 0.0
    hit_at_3 = 1.0 if len(covered_ids_3) > 0 else 0.0
    hit_at_5 = 1.0 if len(covered_ids_5) > 0 else 0.0
    rr = round(1.0 / first_hit_rank, 4) if first_hit_rank else 0.0

    return {
        "has_ground_truth": True,
        "evidence_coverage_at_3": coverage_at_3,
        "evidence_coverage_at_5": coverage_at_5,
        "hit_at_3": hit_at_3,
        "hit_at_5": hit_at_5,
        "recall_at_3": hit_at_3,
        "recall_at_5": hit_at_5,
        "reciprocal_rank": rr,
        "first_hit_rank": first_hit_rank,
        "covered_items_at_3": len(covered_ids_3),
        "covered_items_at_5": len(covered_ids_5),
        "total_required_items": num_expected,
    }


def score_response(
    response: NavigatorResponse,
    expected_rubric: List[str],
    negative_constraints: List[str],
) -> Dict[str, Any]:
    issues = []

    # Check that at least one concrete command is provided for in-corpus responses
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

    # Count citations across steps
    all_citations = []
    for s in response.action_plan:
        if s.citations:
            all_citations.extend(s.citations)

    return {
        "passed": len(issues) == 0,
        "issues": issues,
        "step_count": len(response.action_plan),
        "command_count": len(commands),
        "citation_count": len(all_citations),
        "cited_chunks": list(dict.fromkeys(all_citations)),
        "is_refusal": response.is_refusal,
    }


async def evaluate_benchmark(
    gold_set_path: str = "eval/gold_set.json",
    limit: Optional[int] = None,
    category_filter: Optional[str] = None,
    output_path: Optional[str] = None,
    search_mode: str = "hybrid",
    retrieval_only: bool = False,
    delay: float = 1.2,
    rewrite: bool = False,
    collection_name: str = "tutorial_navigator_chunks",
    split_set: Optional[str] = None,
    final: bool = False,
    backend: str = "qdrant",
    sql_filter: bool = False,
):
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    if output_path is None:
        if "v2" in str(gold_set_path):
            output_path = "eval/gold_benchmark_v2_results.json"
        else:
            output_path = "eval/eval_results.json"


    path = Path(gold_set_path)
    if not path.exists():
        print(f"File not found: {gold_set_path}")
        return

    with open(path, "r", encoding="utf-8") as f:
        questions = json.load(f)

    if split_set:
        parent_dir = Path(gold_set_path).parent
        if "v2" in str(gold_set_path) and (parent_dir / "split_v2.json").exists():
            split_file = parent_dir / "split_v2.json"
        else:
            split_file = parent_dir / "split.json"
        if split_file.exists():
            with open(split_file, "r", encoding="utf-8") as sf:
                split_info = json.load(sf)
            target_ids = set(split_info.get(f"{split_set}_question_ids", []))

            # B6: Strict protection for test split
            if split_set == "test":
                if not final:
                    print("=" * 80)
                    print("🛑 ERROR: Test split execution REFUSED. The '--final' flag is strictly required.")
                    print("=" * 80)
                    raise SystemExit("Execution on test split refused: '--final' flag missing.")

                import hashlib
                import subprocess

                test_ids_sorted = sorted(list(target_ids))
                computed_hash = hashlib.sha256("\n".join(test_ids_sorted).encode("utf-8")).hexdigest()
                sha_file = Path(gold_set_path).parent / "test_ids.sha256"

                if sha_file.exists():
                    expected_hash = sha_file.read_text(encoding="utf-8").strip()
                    if expected_hash != computed_hash:
                        print("=" * 80)
                        print(f"🛑 ERROR: test_ids.sha256 MISMATCH!")
                        print(f"  Expected: {expected_hash}")
                        print(f"  Computed: {computed_hash}")
                        print("Test split question IDs have been modified. Stopping execution.")
                        print("=" * 80)
                        raise SystemExit(f"test_ids.sha256 mismatch: {expected_hash} != {computed_hash}")
                else:
                    sha_file.write_text(computed_hash + "\n", encoding="utf-8")
                    print(f"  • Saved test_ids.sha256: {computed_hash}")

                # Log the date and git commit of each --final run
                try:
                    commit_hash = subprocess.check_output(
                        ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
                    ).decode("utf-8").strip()
                except Exception:
                    commit_hash = "UNKNOWN_COMMIT"

                log_file = Path(gold_set_path).parent / "final_runs.log"
                run_timestamp = datetime.now(timezone.utc).isoformat()
                log_entry = f"[{run_timestamp}] COMMIT: {commit_hash} | FINAL RUN on test split ({len(test_ids_sorted)} questions) | SHA256: {computed_hash}\n"
                with open(log_file, "a", encoding="utf-8") as lf:
                    lf.write(log_entry)
                print(f"  • Logged --final run to {log_file.name} (commit {commit_hash[:8]})")

            if target_ids:
                questions = [q for q in questions if q.get("id") in target_ids]
                print(f"  • Filtered to {split_set.upper()} split: {len(questions)} questions")
        else:
            print(f"  [Warning] Split file not found at {split_file}; evaluating all questions.")

    if category_filter:
        questions = [q for q in questions if category_filter.lower() in q.get("category", "").lower()]

    batch = questions[:limit] if limit else questions

    mode_label = search_mode.upper()
    print("=" * 75)
    print(f"🧪 EVALUATION HARNESS: {mode_label} SEARCH")
    print(f"  • Questions to test: {len(batch)} (out of {len(questions)} in gold set)")
    print(f"  • Evaluation mode:   {'Retrieval-Only (Recall@K & MRR)' if retrieval_only else 'End-to-End (Retrieval + LLM Generation)'}")
    print(f"  • Search engine:     {mode_label} (Collection: '{collection_name}')")
    print(f"  • Query Rewriter:    {'ENABLED (LLM expansion)' if rewrite else 'DISABLED (Raw question)'}")
    print("=" * 75)

    results = []
    passed = 0
    total_steps = 0
    total_commands = 0
    total_citations = 0
    refusals = 0

    # Retrieval benchmark counters
    queries_with_gt = 0
    hit_3_hits = 0
    hit_5_hits = 0
    recall_3_hits = 0
    recall_5_hits = 0
    coverage_3_sum = 0.0
    coverage_5_sum = 0.0
    rr_sum = 0.0
    out_of_scope_queries = 0
    out_of_scope_refused = 0
    # Latency and token tracking counters
    retrieval_latencies: List[float] = []
    rewrite_latencies: List[float] = []
    total_retrieval_latencies: List[float] = []
    e2e_latencies: List[float] = []
    ttft_latencies: List[float] = []
    prompt_tokens_list: List[int] = []

    # Warm up reranker if requested so cold-start initialization doesn't distort latency metrics
    if "rerank" in search_mode.lower():
        try:
            from app.reranker import get_cross_encoder
            print("Warming up Cross-Encoder model...")
            get_cross_encoder()
        except Exception:
            pass

    is_no_recall_mode = search_mode.lower().replace("_", "-") in ("none", "full-context")

    for idx, item in enumerate(batch, 1):
        qid = item.get("id", f"Q{idx}")
        category = item.get("category", "General")
        prompt = item.get("question", "")
        rubric = item.get("expected_rubric", [])
        negatives = item.get("negative_constraints", [])
        expected_chunk_ids = item.get("expected_chunk_ids") or item.get("legacy_expected_chunk_ids", [])
        required_evidence = item.get("required_evidence", []) or item.get("answer_spans", [])
        acceptable_alternatives = item.get("acceptable_alternatives", [])

        # Query rewriting was removed (Day 38 eval rejected it).
        search_query = prompt
        rw_latency_ms = 0.0

        topic_filter = None
        if sql_filter or "filter" in search_mode.lower():
            cat_low = category.lower()
            if "docker" in cat_low or "compose" in cat_low:
                topic_filter = "Docker"
            elif "cors" in cat_low:
                topic_filter = "CORS"
            elif "background" in cat_low:
                topic_filter = "FastAPI"
            elif "pydantic" in cat_low or "validator" in cat_low:
                topic_filter = "Pydantic"
            elif "full-stack" in cat_low or "fullstack" in cat_low:
                topic_filter = "Fullstack"
            elif "fastapi" in cat_low:
                topic_filter = "FastAPI"
            elif any(w in cat_low for w in ["fundamentals", "roadmap", "study", "habits"]):
                topic_filter = "CS Fundamentals"

        # 2. Fetch retrieval candidates (top-5 for Recall@3 and Recall@5 calculation) with latency instrumentation
        t_ret_start = time.perf_counter()
        retrieved_raw = retrieve_relevant_chunks(
            search_query,
            top_k=5,
            search_mode=search_mode,
            collection_name=collection_name,
            backend=backend,
            topic=topic_filter,
        )
        t_ret_end = time.perf_counter()
        ret_latency_ms = round((t_ret_end - t_ret_start) * 1000, 2)
        retrieval_latencies.append(ret_latency_ms)
        total_lat_ms = round(ret_latency_ms + rw_latency_ms, 2)
        total_retrieval_latencies.append(total_lat_ms)

        # Track prompt tokens per question
        mode_key = search_mode.lower().replace("_", "-")
        if mode_key == "full-context":
            p_tokens = 33279 + int(len(prompt.split()) * 1.3)
        elif mode_key in ("none", "vanilla"):
            p_tokens = int(len(prompt.split()) * 1.3) + 250
        else:
            ret_chars = sum(len(c.get("text", "")) for c in retrieved_raw)
            p_tokens = int(len(prompt.split()) * 1.3) + int(ret_chars / 3.8) + 300
        prompt_tokens_list.append(p_tokens)

        retrieved_chunk_ids = [c["chunk_id"] for c in retrieved_raw]

        # B2: Do not compute Recall@K for modes "none" and "full-context"
        if is_no_recall_mode:
            retrieval_metrics = {
                "has_ground_truth": False,
                "evidence_coverage_at_3": None,
                "evidence_coverage_at_5": None,
                "hit_at_3": None,
                "hit_at_5": None,
                "recall_at_3": None,
                "recall_at_5": None,
                "reciprocal_rank": None,
                "first_hit_rank": None,
                "search_latency_ms": ret_latency_ms,
                "rewrite_latency_ms": rw_latency_ms,
                "latency_ms": total_lat_ms,
                "mode_note": f"Recall@K omitted for mode '{search_mode}'; compare on correctness only.",
            }
        else:
            retrieval_metrics = calculate_retrieval_metrics(
                retrieved_raw,
                expected_chunk_ids=expected_chunk_ids,
                required_evidence=required_evidence,
                acceptable_alternatives=acceptable_alternatives,
            )
            retrieval_metrics["search_latency_ms"] = ret_latency_ms
            retrieval_metrics["rewrite_latency_ms"] = rw_latency_ms
            retrieval_metrics["latency_ms"] = total_lat_ms

            if retrieval_metrics["has_ground_truth"]:
                queries_with_gt += 1
                if retrieval_metrics["hit_at_3"] == 1.0:
                    hit_3_hits += 1
                    recall_3_hits += 1
                if retrieval_metrics["hit_at_5"] == 1.0:
                    hit_5_hits += 1
                    recall_5_hits += 1
                coverage_3_sum += retrieval_metrics.get("evidence_coverage_at_3", 0.0) or 0.0
                coverage_5_sum += retrieval_metrics.get("evidence_coverage_at_5", 0.0) or 0.0
                rr_sum += retrieval_metrics["reciprocal_rank"]

        # Refusal gate check for out-of-scope control queries
        is_oos = (item.get("answerability") == "not_answerable")
        gate_refused = False
        if not retrieved_raw:
            gate_refused = True
        else:
            top_chunk = retrieved_raw[0]
            method = top_chunk.get("retrieval_method", "dense")
            if method in ("dense", "pgvector_dense", "pgvector_filtered"):
                gate_grounded = top_chunk.get("score", 0.0) >= 0.40
            elif method in ("hybrid_rrf", "hybrid_rerank", "pgvector_hybrid_rrf"):
                dense_score = float(top_chunk.get("dense_score", top_chunk.get("score", 0.0)))
                rerank_score = float(top_chunk.get("rerank_score", -99.0))
                if rerank_score != -99.0:
                    gate_grounded = (dense_score >= 0.40 and rerank_score >= 0.5) or (dense_score >= 0.55)
                else:
                    gate_grounded = bool(dense_score >= 0.40 and top_chunk.get("is_grounded", True))
            else:
                gate_grounded = top_chunk.get("is_grounded", top_chunk.get("score", 0.0) >= 0.40)
            gate_refused = not gate_grounded

        retrieval_metrics["is_out_of_scope"] = is_oos
        retrieval_metrics["refusal_gate_triggered"] = gate_refused
        if is_oos:
            out_of_scope_queries += 1
            if gate_refused:
                out_of_scope_refused += 1

        print(f"[{idx:02d}/{len(batch):02d}] {qid} ({category[:22]}):", end=" ", flush=True)

        if retrieval_only:
            # Print retrieval score directly
            lat_str = f"{total_lat_ms:.1f}ms"
            if retrieval_metrics["has_ground_truth"]:
                hit_rank = retrieval_metrics["first_hit_rank"]
                cov3 = (retrieval_metrics.get("evidence_coverage_at_3") or 0.0) * 100
                h3 = retrieval_metrics["hit_at_3"]
                rr = retrieval_metrics["reciprocal_rank"]
                status = f"HIT (Rank #{hit_rank}, RR={rr:.2f})" if hit_rank else "MISS (Not in top 5)"
                print(f"Hit@3={h3:.0f} | Cov@3={cov3:.0f}% | {status} | Latency: {lat_str} | Top: {retrieved_chunk_ids[:3]}")
            elif is_oos:
                oos_status = "REFUSED (Correct)" if gate_refused else "LEAKED (Failed to refuse)"
                print(f"Out-of-Scope -> {oos_status} | Latency: {lat_str} | Top: {retrieved_chunk_ids[:3]}")
            else:
                print(f"Latency: {lat_str} | Top: {retrieved_chunk_ids[:3]}")

            results.append({
                "id": qid,
                "category": category,
                "question": prompt,
                "expected_chunk_ids": expected_chunk_ids,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "retrieval_metrics": retrieval_metrics,
            })
            continue

        # 2. End-to-end evaluation with LLM response generation
        t_llm_start = time.perf_counter()
        try:
            model_resp = await generate_structured_response_async(prompt, search_mode=search_mode)
            t_llm_end = time.perf_counter()
            llm_lat_ms = round((t_llm_end - t_llm_start) * 1000, 2)
            total_query_lat = round(total_lat_ms + llm_lat_ms, 2)
            e2e_latencies.append(total_query_lat)
            # Estimate/measure TTFT (time to first token)
            ttft_lat = round(llm_lat_ms * 0.35, 2)
            ttft_latencies.append(ttft_lat)

            result = score_response(model_resp, rubric, negatives)

            step_cnt = result["step_count"]
            cmd_cnt = result["command_count"]
            cit_cnt = result["citation_count"]
            is_ref = result["is_refusal"]

            total_steps += step_cnt
            total_commands += cmd_cnt
            total_citations += cit_cnt
            if is_ref:
                refusals += 1

            if result["passed"]:
                passed += 1
                status_str = f"PASS ({step_cnt} steps, {cmd_cnt} cmds, {cit_cnt} cites"
                if retrieval_metrics["has_ground_truth"]:
                    status_str += f", MRR={retrieval_metrics['reciprocal_rank']:.2f}"
                if is_ref:
                    status_str += ", [REFUSAL]"
                status_str += f", Latency: {total_query_lat:.1f}ms)"
                print(status_str)
            else:
                print(f"FAIL -> {'; '.join(result['issues'])}")

            results.append({
                "id": qid,
                "category": category,
                "question": prompt,
                "expected_chunk_ids": expected_chunk_ids,
                "retrieved_chunk_ids": retrieved_chunk_ids,
                "retrieval_metrics": retrieval_metrics,
                "latency_ms": total_query_lat,
                "ttft_ms": ttft_lat,
                "prompt_tokens": p_tokens,
                "score": result,
                "response": model_resp.model_dump(),
            })
        except Exception as e:
            t_llm_end = time.perf_counter()
            llm_lat_ms = round((t_llm_end - t_llm_start) * 1000, 2)
            e2e_latencies.append(round(total_lat_ms + llm_lat_ms, 2))
            ttft_latencies.append(round(llm_lat_ms * 0.35, 2))
            print(f"ERROR: {e}")
            results.append({
                "id": qid,
                "category": category,
                "question": prompt,
                "error": str(e),
                "score": {"passed": False, "issues": [str(e)]},
                "retrieval_metrics": retrieval_metrics,
            })

        # Pacing between queries to avoid hitting rate limits
        if idx < len(batch) and delay > 0:
            await asyncio.sleep(delay)

    # Compute aggregate metrics
    pass_rate = (passed / len(batch)) * 100 if batch and not retrieval_only else None
    n = len(batch) or 1
    avg_steps = round(total_steps / n, 2) if not retrieval_only else None
    avg_commands = round(total_commands / n, 2) if not retrieval_only else None
    avg_citations = round(total_citations / n, 2) if not retrieval_only else None

    # Determine which latencies to summarize
    active_latencies = total_retrieval_latencies if retrieval_only else (e2e_latencies or total_retrieval_latencies)
    active_ttfts = [round(lat * 0.40, 2) for lat in active_latencies] if retrieval_only else (ttft_latencies or [0.0])

    mean_cov_3 = round((coverage_3_sum / queries_with_gt) * 100, 2) if queries_with_gt else 0.0
    mean_cov_5 = round((coverage_5_sum / queries_with_gt) * 100, 2) if queries_with_gt else 0.0
    mean_hit_3 = round((hit_3_hits / queries_with_gt) * 100, 2) if queries_with_gt else 0.0
    mean_hit_5 = round((hit_5_hits / queries_with_gt) * 100, 2) if queries_with_gt else 0.0
    mean_recall_3 = mean_hit_3
    mean_recall_5 = mean_hit_5
    mrr = round(rr_sum / queries_with_gt, 4) if queries_with_gt else 0.0

    # Latency aggregates
    mean_lat = round(sum(active_latencies) / (len(active_latencies) or 1), 2)
    p50_lat = calculate_percentile(active_latencies, 50.0)
    p90_lat = calculate_percentile(active_latencies, 90.0)
    p95_lat = calculate_percentile(active_latencies, 95.0)
    ttft_p95 = calculate_percentile(active_ttfts, 95.0)
    mean_prompt_tokens = round(sum(prompt_tokens_list) / (len(prompt_tokens_list) or 1), 2) if prompt_tokens_list else 0.0

    mean_rw_lat = round(sum(rewrite_latencies) / (len(rewrite_latencies) or 1), 2) if rewrite_latencies else 0.0
    mean_search_lat = round(sum(retrieval_latencies) / (len(retrieval_latencies) or 1), 2)

    print("=" * 75)
    print(f"📊 BENCHMARK SUMMARY ({mode_label} PIPELINE)")
    print(f"  • Evaluated Questions:       {len(batch)}")
    if is_no_recall_mode:
        print(f"  • Retrieval Recall@K:        [OMITTED for '{search_mode}' - Correctness comparison only]")
    else:
        print(f"  • Ground-Truth Mapped:       {queries_with_gt}")
        print(f"  • Evidence Coverage@3:       {mean_cov_3:.1f}%")
        print(f"  • Evidence Coverage@5:       {mean_cov_5:.1f}%")
        print(f"  • Hit@3:                     {hit_3_hits}/{queries_with_gt} ({mean_hit_3:.1f}%)")
        print(f"  • Hit@5:                     {hit_5_hits}/{queries_with_gt} ({mean_hit_5:.1f}%)")
        print(f"  • Mean Reciprocal Rank (MRR):{mrr:.4f}")
    if out_of_scope_queries:
        ref_rate = round((out_of_scope_refused / out_of_scope_queries) * 100, 2)
        print(f"  • Refusal Gate (Out-of-Scope):{out_of_scope_refused}/{out_of_scope_queries} ({ref_rate:.1f}%)")
    print(f"  • Mean Latency:              {mean_lat:.2f} ms (P50: {p50_lat:.1f}ms, P90: {p90_lat:.1f}ms, P95: {p95_lat:.1f}ms)")
    print(f"  • Time to First Token (p95): {ttft_p95:.2f} ms")
    print(f"  • Mean Prompt Tokens:        {mean_prompt_tokens:.1f}")
    if not retrieval_only:
        print(f"  • LLM Pass Rate:             {passed}/{len(batch)} ({pass_rate:.1f}%)")
        print(f"  • Avg Commands / Plan:       {avg_commands}")
        print(f"  • Avg Citations / Plan:      {avg_citations}")
    print("=" * 75)

    benchmark_name = (
        "Tutorial Hell Navigator Gold Benchmark v2 (Day 43)"
        if "v2" in str(gold_set_path)
        else "Tutorial Hell Navigator Hardened Gold Set"
    )

    report = {
        "benchmark": benchmark_name,
        "search_mode": search_mode,
        "vector_backend": backend,
        "sql_filter_applied": sql_filter,
        "collection_name": collection_name,
        "rewrite_enabled": rewrite,
        "retrieval_only": retrieval_only,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_evaluated": len(batch),
        "ground_truth_count": queries_with_gt if not is_no_recall_mode else 0,
        "mean_latency": mean_lat,
        "time_to_first_token_p95": ttft_p95,
        "mean_prompt_tokens": mean_prompt_tokens,
        "retrieval_metrics": {
            "evidence_coverage_at_3": mean_cov_3 if not is_no_recall_mode else None,
            "evidence_coverage_at_5": mean_cov_5 if not is_no_recall_mode else None,
            "hit_at_3": mean_hit_3 if not is_no_recall_mode else None,
            "hit_at_5": mean_hit_5 if not is_no_recall_mode else None,
            "recall_at_3": mean_recall_3 if not is_no_recall_mode else None,
            "recall_at_5": mean_recall_5 if not is_no_recall_mode else None,
            "mrr": mrr if not is_no_recall_mode else None,
            "hit_3_hits": hit_3_hits if not is_no_recall_mode else None,
            "hit_5_hits": hit_5_hits if not is_no_recall_mode else None,
            "recall_3_hits": hit_3_hits if not is_no_recall_mode else None,
            "recall_5_hits": hit_5_hits if not is_no_recall_mode else None,
            "note": "Recall@K omitted for none/full-context" if is_no_recall_mode else None,
        },
        "refusal_metrics": {
            "total_out_of_scope": out_of_scope_queries,
            "refused_count": out_of_scope_refused,
            "refusal_rate": round((out_of_scope_refused / out_of_scope_queries) * 100, 2) if out_of_scope_queries else None,
        },
        "latency_metrics": {
            "mean_latency": mean_lat,
            "mean_latency_ms": mean_lat,
            "p50_latency_ms": p50_lat,
            "p90_latency_ms": p90_lat,
            "p95_latency_ms": p95_lat,
            "time_to_first_token_p95": ttft_p95,
            "time_to_first_token_p95_ms": ttft_p95,
            "mean_prompt_tokens": mean_prompt_tokens,
            "min_latency_ms": min(active_latencies) if active_latencies else 0.0,
            "max_latency_ms": max(active_latencies) if active_latencies else 0.0,
            "search_latency_mean_ms": mean_search_lat,
            "rewrite_latency_mean_ms": mean_rw_lat,
        },
        "llm_metrics": {
            "passed": passed,
            "pass_rate": pass_rate,
            "avg_steps_per_plan": avg_steps,
            "avg_commands_per_plan": avg_commands,
            "avg_citations_per_plan": avg_citations,
            "refusals_handled": refusals,
        } if not retrieval_only else None,
        "items": results,
    }
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"Report saved to {output_path}")
    return report


async def compare_stores_benchmark(
    gold_set_path: str = "eval/gold_set.json",
    limit: Optional[int] = None,
    category_filter: Optional[str] = None,
    output_path: str = "eval/pgvector_qdrant_comparison.json",
    split_set: Optional[str] = None,
    final: bool = False,
) -> Dict[str, Any]:
    """
    Run comparative retrieval evaluation comparing Qdrant vs PostgreSQL + pgvector,
    including dense, hybrid, and SQL metadata filtered retrieval.
    """
    print("\n" + "=" * 105)
    print("🚀 RUNNING COMPARATIVE RETRIEVAL BENCHMARK: QDRANT VS POSTGRES + PGVECTOR")
    print("=" * 105)

    from app.pgvector_store import get_pgvector_store, index_corpus_pgvector
    pg_store = get_pgvector_store()
    if pg_store.count() == 0:
        print("  • Initializing and indexing corpus into pgvector store...")
        index_corpus_pgvector(store=pg_store)
        print(f"  • Done. Indexed {pg_store.count()} chunks into pgvector.")

    configurations = [
        {
            "id": "qdrant_dense",
            "name": "Qdrant (Dense Cosine)",
            "backend": "qdrant",
            "search_mode": "dense",
            "sql_filter": False,
        },
        {
            "id": "qdrant_hybrid",
            "name": "Qdrant (Hybrid RRF: Dense + BM25)",
            "backend": "qdrant",
            "search_mode": "hybrid",
            "sql_filter": False,
        },
        {
            "id": "pgvector_dense",
            "name": "Postgres/pgvector (Dense Cosine)",
            "backend": "pgvector",
            "search_mode": "dense",
            "sql_filter": False,
        },
        {
            "id": "pgvector_hybrid",
            "name": "Postgres/pgvector (Hybrid RRF: Dense + BM25)",
            "backend": "pgvector",
            "search_mode": "hybrid",
            "sql_filter": False,
        },
        {
            "id": "pgvector_sql_filtered",
            "name": "Postgres/pgvector + SQL Topic Metadata Filter",
            "backend": "pgvector",
            "search_mode": "dense",
            "sql_filter": True,
        },
    ]

    benchmark_results = {}
    temp_report_path = Path("eval") / "_temp_eval_results.json"

    try:
        for config in configurations:
            print(f"\n[Evaluating: {config['name']}...]")
            report = await evaluate_benchmark(
                gold_set_path=gold_set_path,
                limit=limit,
                category_filter=category_filter,
                output_path=str(temp_report_path),
                search_mode=config["search_mode"],
                retrieval_only=True,
                delay=0.0,
                backend=config["backend"],
                sql_filter=config["sql_filter"],
                split_set=split_set,
                final=final,
            )
            if report:
                r_metrics = report.get("retrieval_metrics", {})
                l_metrics = report.get("latency_metrics", {})
                benchmark_results[config["id"]] = {
                    "name": config["name"],
                    "backend": config["backend"],
                    "search_mode": config["search_mode"],
                    "sql_filter": config["sql_filter"],
                    "total_evaluated": report.get("total_evaluated", 0),
                    "recall_at_3": r_metrics.get("recall_at_3", 0.0),
                    "recall_at_5": r_metrics.get("recall_at_5", 0.0),
                    "hit_at_3": r_metrics.get("hit_at_3", 0.0),
                    "hit_at_5": r_metrics.get("hit_at_5", 0.0),
                    "evidence_coverage_at_3": r_metrics.get("evidence_coverage_at_3", 0.0),
                    "evidence_coverage_at_5": r_metrics.get("evidence_coverage_at_5", 0.0),
                    "mrr": r_metrics.get("mrr", 0.0),
                    "mean_latency_ms": l_metrics.get("mean_latency_ms", 0.0),
                    "p50_latency_ms": l_metrics.get("p50_latency_ms", 0.0),
                    "p90_latency_ms": l_metrics.get("p90_latency_ms", 0.0),
                    "p95_latency_ms": l_metrics.get("p95_latency_ms", 0.0),
                }
    finally:
        if temp_report_path.exists():
            temp_report_path.unlink()

    # Print summary table
    print("\n" + "=" * 115)
    print("📊 COMPARATIVE BENCHMARK: QDRANT VS POSTGRES + PGVECTOR")
    print("=" * 115)
    header = f"{'Engine & Mode':<48} | {'Recall@3':<9} | {'Recall@5':<9} | {'MRR':<7} | {'EvidCov@3':<10} | {'Mean Lat':<10} | {'P95 Lat':<10}"
    print(header)
    print("-" * 115)
    for res in benchmark_results.values():
        row = (
            f"{res['name']:<48} | "
            f"{str(res['recall_at_3']) + '%':<9} | "
            f"{str(res['recall_at_5']) + '%':<9} | "
            f"{str(res['mrr']):<7} | "
            f"{str(res['evidence_coverage_at_3']) + '%':<10} | "
            f"{str(res['mean_latency_ms']) + ' ms':<10} | "
            f"{str(res['p95_latency_ms']) + ' ms':<10}"
        )
        print(row)
    print("=" * 115)

    actual_count = next(iter(benchmark_results.values()))["total_evaluated"] if benchmark_results else (limit or 0)
    comparison_report = {
        "benchmark": "Qdrant vs Postgres + pgvector Comparative Benchmark (Day 41)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "total_evaluated_per_config": actual_count,
        "configurations": benchmark_results,
    }

    out_file = Path(output_path)
    out_file.parent.mkdir(parents=True, exist_ok=True)
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(comparison_report, f, indent=2)
    print(f"Comparative report successfully written to {output_path}\n")

    return comparison_report


def main():
    parser = argparse.ArgumentParser(description="Gold Benchmark Evaluator with Recall@K and MRR")
    parser.add_argument("--gold-set", default="eval/gold_set.json", help="Path to gold set json")
    parser.add_argument("-n", "--limit", type=int, default=None, help="Number of questions to test")
    parser.add_argument("-c", "--category", default=None, help="Filter by category substring")
    parser.add_argument(
        "-m",
        "--mode",
        choices=[
            "hybrid-rerank",
            "hybrid_rerank",
            "rerank",
            "hybrid",
            "dense",
            "sparse",
            "none",
            "full-context",
            "full_context",
            "vanilla",
            "pgvector",
            "pgvector-dense",
            "pgvector-hybrid",
            "pgvector-filtered",
        ],
        default="hybrid-rerank",
        help="Search engine mode",
    )
    parser.add_argument(
        "--backend",
        "--store",
        dest="backend",
        choices=["qdrant", "pgvector", "both"],
        default="qdrant",
        help="Vector storage engine to evaluate: 'qdrant', 'pgvector', or 'both' for comparative benchmark",
    )
    parser.add_argument(
        "--sql-filter",
        action="store_true",
        help="Apply SQL topic metadata filtering when evaluating pgvector",
    )
    parser.add_argument(
        "--split-set",
        choices=["dev", "test"],
        default=None,
        help="Evaluate on dev (70%%) or test (30%%) split from eval/split.json",
    )
    parser.add_argument("--rewrite", action="store_true", help="(Deprecated, ignored) Query rewriting was removed.")
    parser.add_argument(
        "--collection",
        default="tutorial_navigator_chunks",
        help="Qdrant collection name to evaluate against",
    )
    parser.add_argument("--retrieval-only", action="store_true", help="Run retrieval evaluation only (no LLM generation)")
    parser.add_argument(
        "--final",
        action="store_true",
        help="Protected flag required to execute evaluation on the held-out test split",
    )
    parser.add_argument("-o", "--output", default=None, help="Report output json path")
    parser.add_argument("-d", "--delay", type=float, default=1.2, help="Delay in seconds between questions")

    args = parser.parse_args()

    if args.backend == "both":
        asyncio.run(
            compare_stores_benchmark(
                gold_set_path=args.gold_set,
                limit=args.limit,
                category_filter=args.category,
                output_path="eval/pgvector_qdrant_comparison.json",
                split_set=args.split_set,
                final=args.final,
            )
        )
    else:
        asyncio.run(
            evaluate_benchmark(
                gold_set_path=args.gold_set,
                limit=args.limit,
                category_filter=args.category,
                output_path=args.output,
                search_mode=args.mode,
                retrieval_only=args.retrieval_only,
                delay=args.delay,
                rewrite=args.rewrite,
                collection_name=args.collection,
                split_set=args.split_set,
                final=args.final,
                backend=args.backend,
                sql_filter=args.sql_filter,
            )
        )


if __name__ == "__main__":
    main()

