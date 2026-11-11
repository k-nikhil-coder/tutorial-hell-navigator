# CI Evaluation Gate Benchmark Diff: Day 46 (commit `b28a03e`) vs HEAD

**Generated On:** 2026-11-10  
**Evaluation Lane:** Lane A (`main` branch)  
**Baseline Commit:** `b28a03e` (`b28a03e7501957a02b248cf13be3981cbc471267` — *feat(day-46): implement automated CI eval gate and resolve reviewer command parser bug*)  
**Comparison Target:** `HEAD` (`d7b5152` + Day 48 working tree updates)  
**Benchmark Gold Set:** `eval/gold_benchmark_v2.json` (`dev` split: 40 questions; `test` split: 25 questions untouched/sealed)  
**Pipeline Mode:** Retrieval-Only `hybrid-rerank` (Dense Qdrant vector retrieval + Sparse BM25 + Cross-Encoder reranking `cross-encoder/ms-marco-MiniLM-L-6-v2`)  
**Corpus State:** 10 Tier-1 Markdown documents, 97 chunks (`corpus/processed/chunks_384.json`)

---

## 1. Executive Summary

Both commit `b28a03e` (executed in an isolated detached `git worktree` populated with the committed 97-chunk corpus and precomputed embedding/BM25 caches) and current `HEAD` ran `python eval/ci_eval_gate.py` against the 40-question `dev` split. Across all 40 questions:

- **Total Dev Split Questions:** 40 (31 answerable, 9 out-of-scope controls)
- **Answerable Breakdown:** 13 `official` docs, 18 `owner_authored` guides
- **Regressions:** 0
- **Improvements:** 0
- **Identical Outcomes (`hit_at_3`, `first_hit_rank`, `refusal_gate_triggered`, and retrieved chunk order):** 40 / 40 (100.0%)
- **Top-3 Hits Maintained:** 29 / 31 (93.55%)
- **Known Misses Maintained:** 2 / 31 (`GS-V2-02` at Rank #4, `GS-V2-07` at Rank #4)
- **Top-5 Hits Maintained:** 31 / 31 (100.00%)
- **Refusals Maintained:** 8 / 9 (88.89%)
- **Known Leak Maintained:** 1 / 9 (`GS-V2-50`)
- **Mean Reciprocal Rank (MRR):** `0.8172` (identical)
- **Gold Benchmark Span Coverage:** 100.0% (verified via `eval/check_span_coverage.py`)

CI gate thresholds in `eval/ci_eval_gate.py` were not modified.

---

## 2. Verbatim Gate Execution Runs

### 2.1 Day 46 Gate Execution (`b28a03e`, isolated detached worktree)
In commit `b28a03e`, `eval/ci_eval_gate.py` enforces five aggregate percentage thresholds (`min_overall_hit_at_3: 80.0`, `min_official_hit_at_3: 80.0`, `min_evidence_coverage_at_3: 80.0`, `min_refusal_rate: 80.0`, `min_hit_at_5: 95.0`).

```text
[INFO] Running Tutorial Hell Navigator CI Evaluation Gate (Day 46)...
======================================================================
[STEP 1] Verifying Gold Benchmark Span Coverage...
======================================================================
eval/check_span_coverage.py::test_dev_answerable_spans_coverage PASSED   [ 50%]
eval/check_span_coverage.py::test_test_split_spans_coverage_silent PASSED [100%]
============================== 2 passed in 0.03s ==============================
[PASS] 100% of answerable gold spans exist in the indexed corpus.

======================================================================
[STEP 2] Running Automated Retrieval Evaluation on Dev Split...
======================================================================
📊 BENCHMARK SUMMARY (HYBRID-RERANK PIPELINE)
  • Evaluated Questions:       40
  • Ground-Truth Mapped:       31
  • Evidence Coverage@3:       93.5%
  • Evidence Coverage@5:       100.0%
  • Hit@3:                     29/31 (93.5%)
  • Hit@5:                     31/31 (100.0%)
  • Mean Reciprocal Rank (MRR):0.8172
  • Refusal Gate (Out-of-Scope):8/9 (88.9%)
  • Mean Latency:              613.08 ms (P50: 608.6ms, P90: 670.8ms, P95: 684.8ms)
  • Time to First Token (p95): 273.93 ms
  • Mean Prompt Tokens:        2234.9

======================================================================
[STEP 3] Auditing Metrics Against CI Regression Thresholds...
======================================================================
Metric                         | Measured     | Target     | Status    
----------------------------------------------------------------------
Overall Dev Hit@3              |  93.55%      | >= 80.0%   | [PASS]
Official Docs Hit@3            |  84.62%      | >= 80.0%   | [PASS]
Evidence Coverage@3            |  93.55%      | >= 80.0%   | [PASS]
Out-of-Scope Refusal Rate      |  88.89%      | >= 80.0%   | [PASS]
Overall Dev Hit@5              | 100.00%      | >= 95.0%   | [PASS]
----------------------------------------------------------------------
Owner-Authored Guides Hit@3: 100.00% (18/18)
Official Docs Breakdown:     84.62% (11/13)
Mean Reciprocal Rank (MRR):  0.8172
Evaluated Items:             40 questions (31 answerable, 9 out-of-scope)

[SUCCESS] ALL CI EVALUATION GATES PASSED! No retrieval regressions detected.
```

### 2.2 HEAD Gate Execution
At `HEAD`, `eval/ci_eval_gate.py` ensures Qdrant is populated (`ensure_qdrant_indexed()`), runs `eval/run_eval.py --retrieval-only --split-set dev`, and runs `audit_per_question_diff()` against `eval/gold_benchmark_v2_dev_results.json`.

```text
[INFO] Running Tutorial Hell Navigator Per-Question CI Evaluation Gate...
======================================================================
[STEP 1] Verifying Gold Benchmark Span Coverage...
======================================================================
eval/check_span_coverage.py::test_dev_answerable_spans_coverage PASSED   [ 50%]
eval/check_span_coverage.py::test_test_split_spans_coverage_silent PASSED [100%]
============================== 2 passed in 0.03s ==============================
[PASS] 100% of answerable gold spans exist in the indexed corpus.

======================================================================
[STEP 2] Verifying Local Qdrant Vector Index...
======================================================================
[PASS] Qdrant index already populated with 97 points.

======================================================================
[STEP 3] Running Automated Retrieval Evaluation on Dev Split...
======================================================================
📊 BENCHMARK SUMMARY (HYBRID-RERANK PIPELINE)
  • Evaluated Questions:       40
  • Ground-Truth Mapped:       31
  • Evidence Coverage@3:       93.5%
  • Evidence Coverage@5:       100.0%
  • Hit@3:                     29/31 (93.5%)
  • Hit@5:                     31/31 (100.0%)
  • Mean Reciprocal Rank (MRR):0.8172
  • Refusal Gate (Out-of-Scope):8/9 (88.9%)
  • Mean Latency:              541.26 ms (P50: 521.5ms, P90: 614.3ms, P95: 707.6ms)
  • Time to First Token (p95): 283.04 ms
  • Mean Prompt Tokens:        2234.9

======================================================================
[STEP 4] Auditing Per-Question Retrieval & Refusal Regressions...
======================================================================
Baseline Unchanged: 29 hits maintained, 8 refusals maintained, 2 known misses.

[PASS] Zero per-question regressions detected across all 40 dev questions.

[SUCCESS] ALL PER-QUESTION CI GATES PASSED! No regressions detected.
```

---

## 3. Aggregate Metrics Comparison & Gate Criteria

Note: `b28a03e` enforced the 5 aggregate thresholds in `THRESHOLDS`; `HEAD` replaced percentage thresholds with deterministic per-question regression checks against `eval/gold_benchmark_v2_dev_results.json` plus 100% span coverage and test ID hash verification. Neither `b28a03e` nor `HEAD` enforces a CI gate threshold on latency or prompt tokens.

| Metric Name | Day 46 (`b28a03e`) | HEAD | Gate Check / Target | Delta | Status |
|---|---|---|---|---|---|
| **Overall Dev Hit@3** | 93.55% (29/31) | 93.55% (29/31) | `b28a03e`: $\ge 80.0\%$; `HEAD`: per-question match | 0.00% | **PASS** |
| **Official Docs Hit@3** | 84.62% (11/13) | 84.62% (11/13) | `b28a03e`: $\ge 80.0\%$; `HEAD`: per-question match | 0.00% | **PASS** |
| **Owner-Authored Guides Hit@3** | 100.00% (18/18) | 100.00% (18/18) | Informational (`HEAD`: per-question match) | 0.00% | **PASS** |
| **Evidence Coverage@3** | 93.55% | 93.55% | `b28a03e`: $\ge 80.0\%$ | 0.00% | **PASS** |
| **Overall Dev Hit@5** | 100.00% (31/31) | 100.00% (31/31) | `b28a03e`: $\ge 95.0\%$ | 0.00% | **PASS** |
| **Out-of-Scope Refusal Rate** | 88.89% (8/9) | 88.89% (8/9) | `b28a03e`: $\ge 80.0\%$; `HEAD`: per-question match | 0.00% | **PASS** |
| **Mean Reciprocal Rank (MRR)** | 0.8172 | 0.8172 | Informational | 0.0000 | **PASS** |
| **Mean Latency (Retrieval-Only)** | 613.08 ms | 541.26 ms | *No CI threshold* (informational runtime jitter) | -71.82 ms | **N/A** |
| **Median Latency (P50)** | 608.60 ms | 521.50 ms | *No CI threshold* | -87.10 ms | **N/A** |
| **90th Percentile Latency (P90)** | 670.80 ms | 614.30 ms | *No CI threshold* | -56.50 ms | **N/A** |
| **95th Percentile Latency (P95)** | 684.80 ms | 707.60 ms | *No CI threshold* | +22.80 ms | **N/A** |
| **Time to First Token (TTFT P95 Est.)** | 273.93 ms | 283.04 ms | *No CI threshold* (`0.40 * latency` in retrieval-only mode) | +9.11 ms | **N/A** |
| **Mean Prompt Tokens (Est.)** | 2,234.93 | 2,234.93 | *No CI threshold* | 0.00 | **N/A** |

---

## 4. Aggregate Metric Definitions (From Source Code)

Each metric above maps directly to calculations in `eval/run_eval.py`, `eval/ci_eval_gate.py`, and `eval/check_span_coverage.py`:

### 4.1 Overall Dev Hit@3 (`hit_at_3`)
- **Definition (`eval/run_eval.py` lines 134, 630):** Percentage of the $N_{\text{answerable}} = 31$ answerable dev questions where at least one `required_evidence` span (or `acceptable_alternatives`) matches verbatim inside the top-3 retrieved chunks ($\text{covered\_at\_3\_count} > 0$, i.e. $\text{first\_hit\_rank} \le 3$).
- **Formula:**
  $$\text{Hit@3} = \frac{1}{N_{\text{answerable}}} \sum_{i=1}^{N_{\text{answerable}}} \mathbb{I}(\text{first\_hit\_rank}_i \le 3) \times 100$$
- **Measured:** $29 / 31 = 93.55\%$.

### 4.2 Official Docs Hit@3 (`official_hit3_pct`)
- **Definition (`b28a03e:eval/ci_eval_gate.py` lines 97–103):** Subset of Hit@3 computed over answerable dev items whose `source_kind == "official"` ($N_{\text{official}} = 13$).
- **Measured:** $11 / 13 = 84.62\%$. The two misses at top-3 are `GS-V2-02` and `GS-V2-07` (both Rank #4).

### 4.3 Owner-Authored Guides Hit@3 (`owner_hit3_pct`)
- **Definition (`b28a03e:eval/ci_eval_gate.py` lines 105–111):** Subset of Hit@3 computed over answerable dev items whose `source_kind == "owner_authored"` ($N_{\text{owner}} = 18$).
- **Measured:** $18 / 18 = 100.00\%$.

### 4.4 Evidence Coverage@3 (`evidence_coverage_at_3`)
- **Definition (`eval/run_eval.py` lines 132, 628):** For each answerable query $i$, computes the fraction of its required evidence items matched within ranks 1–3 (`covered_at_3_count / total_required_items`), then averages across all 31 answerable queries. Since each of the 31 dev answerable questions currently has 1 required item, `evidence_coverage_at_3` equals `hit_at_3` ($93.55\%$).

### 4.5 Overall Dev Hit@5 (`hit_at_5`)
- **Definition (`eval/run_eval.py` lines 135, 631):** Same binary hit rule evaluated over top-5 retrieved chunks ($\text{first\_hit\_rank} \le 5$). Both `GS-V2-02` and `GS-V2-07` hit at Rank #4, giving $31 / 31 = 100.00\%$.

### 4.6 Out-of-Scope Refusal Rate (`refusal_rate`)
- **Definition (`eval/run_eval.py` lines 493–518, 708):** Percentage of the $N_{\text{oos}} = 9$ `not_answerable` dev questions where the retrieval gate refuses (`gate_refused = not gate_grounded`). In `hybrid_rerank` mode, `gate_grounded` is:
  $$\text{gate\_grounded} = (\text{dense\_score} \ge 0.40 \land \text{rerank\_score} \ge 0.50) \lor (\text{dense\_score} \ge 0.55)$$
- **Measured:** $8 / 9 = 88.89\%$. Only `GS-V2-50` leaks past the gate.

### 4.7 Mean Reciprocal Rank (`mrr`)
- **Definition (`eval/run_eval.py` lines 136, 634):** Mean of $1 / \text{first\_hit\_rank}$ over all 31 answerable dev questions (0 if unretrieved in top 5).
- **Measured breakdown:** 22 queries at Rank #1 ($1.0$), 3 at Rank #2 ($0.50$: `GS-V2-01`, `GS-V2-14`, `GS-V2-20`), 4 at Rank #3 ($0.3333$: `GS-V2-06`, `GS-V2-08`, `GS-V2-17`, `GS-V2-27`), 2 at Rank #4 ($0.25$: `GS-V2-02`, `GS-V2-07`):
  $$\text{MRR} = \frac{22(1.0) + 3(0.5) + 4(0.3333) + 2(0.25)}{31} = \frac{25.3332}{31} = 0.8172$$

### 4.8 Latency Metrics & Time to First Token Estimate (`mean_latency`, `p50/p90/p95`, `time_to_first_token_p95`)
- **Definition (`eval/run_eval.py` lines 434–438, 625–641):** In `--retrieval-only` mode, `active_latencies` records the wall-clock retrieval time per query (sparse + dense lookup + cross-encoder rerank). `active_ttfts` is a placeholder heuristic (`round(lat * 0.40, 2)`) because no LLM stream is invoked in retrieval-only mode.

### 4.9 Mean Prompt Tokens Estimate (`mean_prompt_tokens`)
- **Definition (`eval/run_eval.py` lines 446–448, 642):** In retrieval-only mode, prompt tokens per query are estimated analytically without an LLM call as `int(len(prompt.split()) * 1.3) + int(ret_chars / 3.8) + 300`, yielding `2234.93` identically on both runs because retrieved chunks match 100%.

---

## 5. Per-Question Comparison Table (40 Dev Split Questions)

| # | Question ID | Topic | Answerability | Source Kind | Hit@3 (`b28a03e`) | Hit@3 (`HEAD`) | Rank (`b28a03e`) | Rank (`HEAD`) | RR | Outcome (`b28a03e`) | Outcome (`HEAD`) | Diff Status |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01 | GS-V2-01 | FastAPI | answerable | official | 1.0 | 1.0 | 2 | 2 | 0.5 | Grounded (Hit) | Grounded (Hit) | Identical |
| 02 | GS-V2-02 | FastAPI | answerable | official | 0.0 | 0.0 | 4 | 4 | 0.25 | Grounded (Miss @#4) | Grounded (Miss @#4) | Identical |
| 03 | GS-V2-03 | FastAPI | answerable | official | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 04 | GS-V2-04 | FastAPI | answerable | official | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 05 | GS-V2-05 | FastAPI | answerable | official | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 06 | GS-V2-06 | FastAPI | answerable | official | 1.0 | 1.0 | 3 | 3 | 0.3333 | Grounded (Hit) | Grounded (Hit) | Identical |
| 07 | GS-V2-07 | FastAPI | answerable | official | 0.0 | 0.0 | 4 | 4 | 0.25 | Grounded (Miss @#4) | Grounded (Miss @#4) | Identical |
| 08 | GS-V2-08 | FastAPI | answerable | official | 1.0 | 1.0 | 3 | 3 | 0.3333 | Grounded (Hit) | Grounded (Hit) | Identical |
| 09 | GS-V2-09 | FastAPI | answerable | official | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 10 | GS-V2-13 | Docker | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 11 | GS-V2-14 | Docker | answerable | owner_authored | 1.0 | 1.0 | 2 | 2 | 0.5 | Grounded (Hit) | Grounded (Hit) | Identical |
| 12 | GS-V2-15 | Docker | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 13 | GS-V2-16 | Docker | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 14 | GS-V2-17 | Docker | answerable | owner_authored | 1.0 | 1.0 | 3 | 3 | 0.3333 | Grounded (Hit) | Grounded (Hit) | Identical |
| 15 | GS-V2-18 | Docker | answerable | official | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 16 | GS-V2-19 | Docker | answerable | official | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 17 | GS-V2-20 | Docker | answerable | official | 1.0 | 1.0 | 2 | 2 | 0.5 | Grounded (Hit) | Grounded (Hit) | Identical |
| 18 | GS-V2-21 | Docker | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 19 | GS-V2-25 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 20 | GS-V2-26 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 21 | GS-V2-27 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 3 | 3 | 0.3333 | Grounded (Hit) | Grounded (Hit) | Identical |
| 22 | GS-V2-28 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 23 | GS-V2-29 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 24 | GS-V2-30 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 25 | GS-V2-31 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 26 | GS-V2-32 | PostgreSQL | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 27 | GS-V2-36 | Pydantic | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 28 | GS-V2-37 | Pydantic | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 29 | GS-V2-38 | Pydantic | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 30 | GS-V2-39 | Pydantic | answerable | owner_authored | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 31 | GS-V2-40 | Pydantic | answerable | official | 1.0 | 1.0 | 1 | 1 | 1.0 | Grounded (Hit) | Grounded (Hit) | Identical |
| 32 | GS-V2-46 | AI/ML | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |
| 33 | GS-V2-47 | AI/ML | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |
| 34 | GS-V2-48 | AI/ML | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |
| 35 | GS-V2-49 | AI/ML | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |
| 36 | GS-V2-50 | AI/ML | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | LEAKED (Fail) | LEAKED (Fail) | Identical |
| 37 | GS-V2-51 | OS & Systems Theory | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |
| 38 | GS-V2-52 | OS & Systems Theory | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |
| 39 | GS-V2-53 | Database Theory | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |
| 40 | GS-V2-54 | Networking Theory | not_answerable | out_of_scope | N/A | N/A | None | None | N/A | REFUSED (Pass) | REFUSED (Pass) | Identical |

---

## 6. Verified Analysis of Known Outliers

### 6.1 Known Hit@3 Miss #1: `GS-V2-02` (FastAPI CORS Configuration)
- **Question:** *"How do I configure Cross-Origin Resource Sharing (CORS) in a FastAPI Python application?"*
- **Target Gold Span (`fastapi_cors.md`):** *"You can configure it in your **FastAPI** application using the `CORSMiddleware`."*
- **Observed Top-4 Retrieved Chunks:**
  - Rank 1: `fastapi_cors_sweep384_chunk_0`
  - Rank 2: `fastapi_fullstack_guide_sweep384_chunk_3`
  - Rank 3: `fastapi_cors_sweep384_chunk_2`
  - Rank 4: `fastapi_cors_sweep384_chunk_1` (contains gold span -> Hit@5 = 1.0, Hit@3 = 0.0, RR = 0.25)

### 6.2 Known Hit@3 Miss #2: `GS-V2-07` (FastAPI BackgroundTasks Method)
- **Question:** *"Which method is called on a BackgroundTasks instance to schedule a function execution in FastAPI?"*
- **Target Gold Span (`fastapi_background_tasks.md`):** *"Inside of your path operation function, pass your task function to the background tasks object with the method `.add_task()`:"*
- **Observed Top-4 Retrieved Chunks:**
  - Rank 1: `fastapi_background_tasks_sweep384_chunk_2`
  - Rank 2: `fastapi_background_tasks_sweep384_chunk_3`
  - Rank 3: `fastapi_background_tasks_sweep384_chunk_0`
  - Rank 4: `fastapi_background_tasks_sweep384_chunk_1` (contains gold span -> Hit@5 = 1.0, Hit@3 = 0.0, RR = 0.25)

### 6.3 Known Refusal Leak: `GS-V2-50` (AI/ML vLLM Serving)
- **Question:** *"How do I configure vLLM with PagedAttention and tensor parallelism across four NVIDIA A100 GPUs for low-latency serving?"* (`out_of_scope`, `AI/ML`)
- **Observed Top Retrieved Chunk:** `fastapi_fullstack_guide_sweep384_chunk_4`
- **Observed Scores:** `dense_score = 0.5612`, `rerank_score = -9.6891`
- **Cause Verified in Code (`eval/run_eval.py` line 506):** Although the cross-encoder scored the chunk at `-9.6891` (well below `0.50`), the fallback branch `or (dense_score >= 0.55)` evaluated `True` because `0.5612 >= 0.55`, preventing the refusal gate from firing (`refusal_gate_triggered = False`).
