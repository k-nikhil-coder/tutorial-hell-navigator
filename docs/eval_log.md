# Evaluation Log & Experiment Notebook

This document archives the complete progression of empirical experiments, metric definitions, baseline comparisons, and calibration audits conducted during the 100-Day AI Sprint for **Tutorial Hell Navigator**.

---

## 1. Metric Definitions

To ensure evaluation rigor and prevent metric drift, retrieval metrics are strictly defined:

- **Evidence Coverage@K**: The fraction of `required_evidence` items covered within top $K$ candidates. An item counts as covered if a retrieved chunk contains its verbatim span or one of its acceptable alternatives:
  $$\text{Evidence Coverage}@K = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{\sum_{i=1}^{M_q} \mathbb{I}(\text{item } i \text{ covered in top } K)}{M_q}$$
- **Hit@K**: Binary indicator of whether at least one required evidence item is covered in the top $K$ retrieved chunks:
  $$\text{Hit}@K = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \mathbb{I}\left(\sum_{i=1}^{M_q} \mathbb{I}(\text{item } i \text{ covered in top } K) \ge 1\right)$$
- **Mean Reciprocal Rank (MRR)**: Evaluates ranking quality based on the rank of the first covered evidence item:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{1}{\text{rank of first covered item in } q}$$
  *(Rank 1 = 1.0, Rank 2 = 0.50, Rank 3 = 0.333, unretrieved = 0.0)*

*(Note: In historical v1 logs, "Recall@K" referred to Hit@K binary chunk matching. Under the v2 schema, both Evidence Coverage@K and Hit@K are tracked independently).*

---

## 2. Historical Retrieval Metrics (n=23 labeled questions, v1 Legacy)

Measured on 23 questions in [`eval/gold_set.json`](../eval/gold_set.json) with human-labeled `expected_chunk_ids`. Each question is worth ~4.3 points of recall. No confidence intervals were computed. **No held-out test split exists for v1**—all tuning and reporting used the same 23 questions.

| Pipeline | Recall@3 (n=23) | Recall@5 (n=23) | MRR (n=23) |
| :--- | :---: | :---: | :---: |
| Dense-only (`gemini-embedding-001`) | 60.9% (14/23) | 78.3% (18/23) | 0.568 |
| Hybrid (Dense + BM25 + RRF) | 69.6% (16/23) | 78.3% (18/23) | 0.573 |
| Hybrid + Cross-Encoder Reranker | 65.2% (15/23) | 82.6% (19/23) | 0.578 |
| Hybrid + Reranker + 384-token chunks | 78.3% (18/23) | 78.3% (18/23) | 0.667 |

**Differences between pipelines:**
- Hybrid vs Dense-only: +8.7 points Recall@3 (+2 questions)
- 384-token sweep vs 512-token baseline: +13.0 points Recall@3 (+3 questions), but -4.3 points Recall@5 (-1 question)
- Reranker vs Hybrid: -4.3 points Recall@3 (-1 question), +4.3 points Recall@5 (+1 question)

*At n=23, a single question changes any metric by ~4.3 points. These differences are not statistically validated.*

---

## 3. Three-Way Baseline Comparison (n=30 questions with labels)

Benchmarked on 30 labeled questions using a pinned model (`gemini-flash-lite-latest`, no fallback chain):

| Configuration | Avg Prompt Tokens | Valid Citations | Ground-Truth Hits | P50 Latency |
| :--- | :---: | :---: | :---: | :---: |
| Zero-retrieval (LLM weights only) | 277 | 0 | 0 | 3,140 ms |
| Full-corpus-in-context (~35k tokens) | 33,279 | 123 | 40 | 4,201 ms |
| Current pipeline (Hybrid + Reranker, K=3) | 1,833 | 64 | 29 | 3,031 ms |

Full-corpus-in-context achieves more ground-truth citation hits (40 vs 29) by giving the LLM access to all 92 chunks. The retrieval pipeline's advantage is **18× fewer prompt tokens** and ~1,170 ms lower P50 latency. At this corpus size, the retrieval stack is a cost/latency optimization, not an accuracy improvement.

---

## 4. Day 41: Qdrant vs In-Memory Simulation Fallback (n=30 Gold Set Questions)

Comparative evaluation across 30 questions (22 technical targets + 8 refusal controls) using identical 3,072-dimensional embeddings (`gemini-embedding-001`):

| Vector Engine & Mode | Recall@3 | Recall@5 | MRR | Evidence Coverage@3 | Mean Latency | P95 Latency | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| Qdrant (Dense Cosine) | 63.64% | 81.82% | 0.6167 | 54.55% | 24.45 ms | 7.00 ms | Mean skewed by ~540 ms cold-start outlier; warm P50/P95 is 6.6–7.0 ms |
| Qdrant (Hybrid RRF: Dense + BM25) | 68.18% | 81.82% | 0.6174 | 53.79% | 12.72 ms | 13.57 ms | Local BM25 tokenization + RRF |
| In-Memory Simulation (Dense Cosine) | 63.64% | 81.82% | 0.6167 | 54.55% | 0.88 ms | 1.13 ms | *In-memory simulation fallback (`pgvector_is_live: false`), in-process math, not live database* |
| In-Memory Simulation (Hybrid RRF) | 68.18% | 81.82% | 0.6174 | 53.79% | 7.06 ms | 7.85 ms | *In-memory simulation fallback* |
| In-Memory Simulation + SQL Metadata Filter | 63.64% | 81.82% | **0.6265** | 54.55% | **0.72 ms** | **0.92 ms** | *In-memory simulation fallback; filter leaked benchmark category labels* |

**Methodology & Disclosures:**
- **In-Memory Fallback Disclosure:** The pgvector rows above ran against an in-process Python fallback (`pgvector_is_live: false`), calculating exact cosine similarities in memory. Real database network queries over PostgreSQL sockets were not measured here.
- **Trivial Parity:** Dense cosine search between Qdrant and the in-memory fallback produces identical recall and MRR rankings because both compute exact cosine distances over identical vectors. Approximate HNSW index behavior against a live PostgreSQL instance remains untested.
- **SQL Metadata Filter Caveat:** Combining SQL filtering on `topic` pushed MRR to 0.6265, but the topic was extracted from the benchmark's own `category` label (benchmark label leakage), which is invalid in production unless an upfront classifier provides the topic.

---

## 5. Week 6 Review: What Actually Moved the Score?

Consolidated empirical summary of architectural experiments during Week 6 (Days 36–42):

1. **Hybrid Retrieval (Dense + BM25 + Reciprocal Rank Fusion, $k=60$):**
   - **Baseline:** Dense-only achieved 60.9% Recall@3 (14/23) and 0.568 MRR.
   - **Measured Effect:** Boosted Recall@3 to 69.6% (+8.7 points) and MRR to 0.573 by reliably matching exact code tokens (`CORSMiddleware`, `psycopg2`).
   - **Cost & Latency:** Zero API cost, adds ~6 ms local BM25 tokenization latency.
   - **Verdict:** **KEEP.** Essential foundation for technical syntax retrieval.

2. **Cross-Encoder Reranker (`ms-marco-MiniLM-L-6-v2`):**
   - **Baseline:** Hybrid RRF achieved 69.6% Recall@3 and 78.3% Recall@5.
   - **Measured Effect:** Pushed Recall@5 to 82.6% (+1 question, 19/23) and MRR to 0.578 (+0.005), but lowered Recall@3 to 65.2% (-1 question, 15/23).
   - **Cost & Latency:** Adds ~500 ms local CPU inference latency per query.
   - **Verdict:** **PROVISIONAL.** Kept under evaluation; unproven at K=3 until sealed test set evaluation.

3. **384-Token Chunk Size Sweep (with 60-Token Overlap):**
   - **Baseline:** 512-token ceiling chunks (67 chunks, mean ~440 tokens) achieved 65.2% Recall@3 and 0.578 MRR.
   - **Measured Effect:** Moved Recall@3 to 78.3% (+3 questions, 18/23) and MRR to 0.667, but Recall@5 fell from 82.6% to 78.3% (-1 question, 18/23). 92 chunks total with a 384-token cap and mean of ~334 tokens across 8 source files.
   - **Cost & Latency:** Tuned and measured on the same 23 questions (promising lead, not final proof).
   - **Verdict:** **PROVISIONAL LEAD.** Requires validation on unseen test questions.

4. **PostgreSQL + pgvector Dual-Storage & SQL Metadata Filtering:**
   - **Baseline:** Qdrant standalone vector DB (63.64% Recall@3, 81.82% Recall@5, 0.6167 MRR on $N=30$).
   - **Measured Effect:** Tested only as an in-memory cosine fallback. Exact parity with Qdrant is mathematically trivial on identical vectors. The SQL filter MRR gain leaked benchmark labels.
   - **Verdict:** **UNTESTED AGAINST A LIVE DATABASE (IN-MEMORY SIMULATION ONLY).** Live HNSW indexing and socket latency need dedicated benchmarking.

5. **Failure Audit & Error Analysis:**
   - **Baseline:** 8 out of 23 queries flagged as retrieval misses at $K=3$ in `hybrid_rerank_retrieval_report.json` (GS-04, 06, 11, 12, 13, 14, 15, 88).
   - **Measured Effect:** Reviewing the 8 misses against chunk text revealed 4 wrong labels (GS-06, 11, 14, 15), 2 overlapping chunks (GS-12, 88), 1 real retrieval failure (GS-04), and 1 corpus gap (GS-13).
   - **Methodological Note:** Because labels were corrected after observing failure cases, no "corrected accuracy" is claimed. Legacy v1 evaluation reports are marked as invalidated.
   - **Verdict:** **PERMANENT PROTOCOL.** Always audit failure logs before adjusting model architectures.

---

## 6. Day 43: Benchmark v2 & Structural Index Ceiling Discovery

Day 43 introduced the **Expanded Multi-Contributor Labeled Gold Benchmark v2** (65 questions, 40 dev / 25 sealed test split with SHA256 ID protection in `eval/test_ids.sha256`):
- **Provenance Origins:** 35 questions from student study group discussions (marked `paraphrased, no public source`), 18 from StackOverflow (`CC BY-SA 4.0`), and 12 from Reddit discussions. Labeled across 6 peer contributors (`contributor_1` through `contributor_6`) and project curator Kumbham Nikhil.
- **Answerability:** 45 answerable questions with verbatim evidence spans and 20 refusal controls with empty evidence.

### The Structural Ceiling Discovery (45.16% Explained)

On the 40-question dev split (31 answerable questions, 9 refusal controls), hybrid-rerank scored:
- **Hit@3:** 45.16% (14 of 31)
- **Evidence Coverage@3:** 45.16% (14 of 31)
- **MRR:** 0.3763
- **Refusal Rate on Out-of-Scope:** 88.9% (8 of 9)

**Auditing the 17 Misses:**
When verifying all 31 answerable dev questions against `corpus/processed/chunks_384.json` (92 chunks from 8 source files), **17 of the 31 required evidence spans do not appear in any indexed chunk**:
- Missing from index: `GS-V2-13`, `14`, `15`, `16`, `17`, `25`, `26`, `27`, `28`, `29`, `30`, `31`, `32`, `36`, `37`, `38`, `39`.
- **Cause:** These 17 questions reference evidence in 3 source files that exist in `corpus/raw/` but were omitted from the 8-file `chunks_384.json` build: `fastapi_validation.md`, `docker_compose.md`, and `postgresql_psycopg2.md`.
- **Structural Ceiling:** Because 17 questions cannot be answered from the current index, the theoretical maximum retrieval score on the dev split is **14 of 31 (45.16%)**.
- **Retriever Performance:** The hybrid-rerank pipeline retrieved **14 of 14 indexable questions (100% of available ceiling)**, with 0 retrieval failures on indexed material. The 45.16% score reflects an index corpus gap, not a retrieval defect.

---

## 7. Day 44: Heuristic Evaluation Judge & Reviewer Calibration

Day 44 calibrated an automated evaluator against human grades on 50 questions across 4 binary axes:

1. **Rubric Separation:**
   - **Human Rubrics:**
     - *Faithfulness:* Response claims are supported by retrieved technical context (evaluated by human curator).
     - *Citation Validity:* Every actionable step cites an authentic chunk ID present in retrieved context.
     - *Code Correctness:* Code is free of known dangerous anti-patterns (deprecated imports, raw SQL f-strings, committed credentials).
     - *Adherence:* Respects task criteria and negative constraints, including refusing out-of-scope queries.
   - **Judge Proxies:**
     - *Faithfulness:* Token overlap against retrieved chunk text.
     - *Citation Validity:* Set membership check (`cited_chunk_ids.issubset(retrieved_chunk_ids)`).
     - *Code Correctness:* Static regex pattern matching on known anti-patterns.
     - *Adherence:* Rule-based refusal check and banned phrase scanning.

2. **Critical Limitation (No Command Execution):**
   The judge does not execute commands in a sandboxed runtime. It only catches known static patterns and checks citation metadata.

3. **Source Confound & FAIL Provenance:**
   - All 50 calibration pairs (34 PASS, 16 FAIL) were synthetic pairs authored in `scripts/build_judge_calibration_data.py`.
   - **0 pairs were real model outputs.** All 16 FAIL pairs were synthetic bad answers written by hand to test known anti-patterns. A heuristic checker finding bugs planted by the author measures rule coverage on known anti-patterns, not real-world model error distributions.
   - *Grading Order:* Pairs were hand-graded with human criteria before the automated judge was executed against them. Both were committed together in `ebfcc05`.

4. **First-Run Calibration Results:**
   - **Observed Agreement:** **84.0%** (42 of 50 pairs).
   - **95% Wilson Score Confidence Interval:** **[71.5%, 91.7%]**. Note that the lower bound (71.5%) does not clear the $\ge 80\%$ calibration gate.
   - **Cohen's Kappa ($\kappa$):** **0.6324** (Substantial agreement).
   - **Confusion Matrix:** 30 TP, 12 TN, 4 FP, 4 FN (Precision: 88.2%, Recall: 88.2%, Specificity: 75.0%, F1: 88.2%). Recorded in `eval/judge_calibration_report.json`.
   - **Dimension Breakdown:** Faithfulness = 80.0%, Citation Validity = 84.0%, Code Correctness = 82.0%, Adherence = 78.0%.

5. **Reproducibility & Post-Hoc Tuning:**
   - Pre-tuning code and report are tagged at `git tag judge-v1-firstrun` (commit [`ebfcc05`](https://github.com/k-nikhil-coder/tutorial-hell-navigator/commit/ebfcc05)).
   - Adjusting regex rules after observing the 8 disagreements drove measured agreement to 100% on the same 50 pairs. This 100% measures memorization/overfitting on the training set and is not a valid generalization claim.

6. **Offline Audit Endpoint Scope:**
   `POST /api/review` is an offline auditing endpoint. The runtime `/navigate` endpoint does not execute or block on this reviewer inline.

---

## 8. Day 45: 10-File Corpus Rebuild & Dev Split Evaluation (Ceiling Resolved)

On Day 45, the structural index ceiling discovered on Day 43 was resolved:

1. **Tag & Snapshot:**
   - Tagged historical 8-file state: `git tag index-8files`.
   - Archived 8-file dev results in `eval/gold_benchmark_v2_dev_results_8files.json`.

2. **Full Ingestion & Chunking:**
   - Rebuilt `corpus/processed/chunks_384.json` from all 10 Tier-1 files (`docker_compose.md`, `docker_compose_best_practices.md`, `docker_production_guide.md`, `fastapi_background_tasks.md`, `fastapi_cors.md`, `fastapi_fullstack_guide.md`, `fastapi_validation.md`, `postgresql_psycopg2.md`, `pydantic_models.md`, `pydantic_validation.md`).
   - Settings strictly unchanged: `RecursiveCharacterTextSplitter.from_tiktoken_encoder("cl100k_base", chunk_size=384, chunk_overlap=60)`.
   - Result: 97 chunks generated across 10 files (mean char count: ~1,304 chars).
   - Rebuilt dual dense (3,072 dims via `gemini-embedding-001`) and BM25 sparse indexes in Qdrant (`tutorial_navigator_chunks_sweep` and `tutorial_navigator_chunks`) and pgvector in-memory store.

3. **Pre-Evaluation Span Coverage Assertion (`eval/check_span_coverage.py`):**
   - Implemented automated pytest checking that every answerable question's verbatim evidence span appears in at least one indexed chunk.
   - Dev split: 31/31 (100%) covered.
   - Sealed test split: 14/14 (100%) covered (verified silently, count only, zero question text leaked).

4. **Source Kind Classification:**
   - Tagged each question with `source_kind: "official" | "owner_authored" | "out_of_scope"` in `eval/gold_benchmark_v2.json`.
   - Dev split breakdown: 13 official docs, 18 owner-authored guides, 9 out-of-scope controls.

5. **Dev Split Evaluation Results (Hybrid-Rerank, K=3):**
   - **Overall (n=31):**
     - Hit@3: **93.55%** (29/31), 95% Wilson CI: **[79.28%, 98.21%]**
     - Evidence Coverage@3: **93.55%** (29/31)
     - Hit@5: **100.0%** (31/31)
     - MRR: **0.8172** (95% Bootstrap CI: **[0.7124, 0.9167]**)
     - Out-of-Scope Refusal Rate: **88.89%** (8/9)
   - **By Source Kind:**
     - *Official Docs (n=13):* Hit@3 = **84.62%** (11/13), 95% Wilson CI: **[57.77%, 95.67%]**, MRR = **0.7051** (95% CI: [0.5256, 0.8718])
     - *Owner-Authored Guides (n=18):* Hit@3 = **100.0%** (18/18), 95% Wilson CI: **[82.41%, 100.0%]**, MRR = **0.8981** (95% CI: [0.7778, 1.0])
   - **Error Analysis of the 2 Misses:**
     - `GS-V2-02` (FastAPI CORS allowed origins): retrieved at Rank #4 (RR = 0.25).
     - `GS-V2-07` (FastAPI background tasks dependency injection): retrieved at Rank #4 (RR = 0.25).
     - Both questions hit within top 5, yielding 100% Hit@5.

6. **Protocol Discipline:**
   - No retrieval thresholds, reranker models, or chunking parameters were modified.
   - The sealed test split (25 questions) was not executed.

---

## 9. Day 45: Frozen Blind LLM Judge Calibration (Pre-Registered Experiment)

To resolve the overfitting confound identified on Day 44 (where rule-tuning against the 50 development pairs drove measured agreement to 100%), a pre-registered blind calibration was executed on Day 45:

### 1. Dataset Construction & Mix (n=30 Fresh Pairs)
- **Source Questions:** 30 questions drawn exclusively from the dev split in `eval/gold_benchmark_v2.json` (25 technical questions across FastAPI, Docker, PostgreSQL, Pydantic, and 5 out-of-scope controls). Zero questions from the sealed test split. Zero pairs repeated from the Day 44 dataset.
- **Fresh Live Generation:** All responses were generated live by the production model (`gemini-flash-lite-latest`) using hybrid-rerank context over the 10-file corpus.
- **Balanced Composition:**
  - **15 Untouched Real Model Outputs:** Baseline live model responses without human modification.
  - **15 Single-Defect Injected Outputs:** Derived by introducing exactly one targeted defect into a real model output.
- **Defect Family Selection:** Defect families were pre-chosen by the author before running the judge, explicitly incorporating 6 families for which `app/reviewer.py` has no heuristic rule:
  1. *Wrong CLI flag spelling* (e.g. `uvicorn --relod`, `docker compose up --detatch`) — [No judge rule]
  2. *Wrong default port* (e.g. stating PostgreSQL listens by default on port 3306 or FastAPI on port 5000) — [No judge rule]
  3. *Semantic contradiction of cited chunk* (e.g. claiming distinct ports on localhost share the same origin, or reversing Docker Compose `HOST:CONTAINER` port mapping) — [No judge rule]
  4. *Real but irrelevant chunk citation* (e.g. citing a Docker chunk for Pydantic validation) — [No judge rule]
  5. *Missing required prerequisite step* (e.g. running psycopg2 Python code without installing `psycopg2-binary`) — [No judge rule]
  6. *Wrong HTTP status code* (e.g. claiming validation errors return HTTP 200 instead of HTTP 422) — [No judge rule]
  7. *Rule-matched anti-patterns* (`from pydantic import BaseSettings`, f-string SQL injection, CORS wildcard with credentials, hallucinated chunk ID, false answer on out-of-scope) — [Judge has rule]

### 2. Blind Protocol & Pre-Execution Commit
- **Shuffled & Blinded:** Pairs were deterministically shuffled (seed 45) and assigned IDs `D45-01` through `D45-30` in `eval/judge_day45_pairs.json`, stripped of all injection metadata and judge outputs. The injection key was saved separately in `eval/injection_key_d45.json`.
- **Pre-Execution Commit:** Human grades for all 4 binary criteria (faithfulness, groundedness, code correctness, adherence) and overall PASS/FAIL were committed to version control in `eval/hand_grades_d45.json` (commit `a6645a2`) **BEFORE** the judge was executed.
- **Frozen State Tag:** The repository was tagged with `git tag judge-frozen-d45`.
- **Single Run:** The judge was executed once against the blind dataset (`eval/judge_day45_report.json`) with strictly zero rule modifications afterward.

### 3. Empirical Results & Findings

| Metric | Target | Measured Result | Interpretation / Assessment |
| :--- | :---: | :---: | :--- |
| **Observed Agreement** | $\ge 80.0\%$ | **46.67%** (14/30) | ❌ **Failed:** Drops sharply from overfitted 100% on unseen pairs |
| **95% Wilson Confidence Interval** | - | **[30.23%, 63.86%]** | Upper bound (63.9%) falls well below the 80% gate |
| **Cohen's Kappa ($\kappa$)** | $> 0.60$ | **-0.0667** | **Poor (Less than chance agreement)** |
| **Confusion Matrix (PASS = Pos)** | - | **TP: 3, TN: 11, FP: 4, FN: 12** | High false-negative rate on clean outputs |
| **Precision / Recall / F1 (PASS)** | - | **42.86% / 20.00% / 27.27%** | Precision 0.429, Recall 0.200 |
| **Recall on FAIL (Defect Catch Rate)** | - | **73.33%** (11/15) | Catches known rules, blind to subtle semantic bugs |
| ↳ *Rule-Matched Families* | - | **100.0%** (4/4) | Perfect recall when a hand-crafted regex exists |
| ↳ *Novel Families (No Rule)* | - | **60.0%** (6/10) | Misses flag typos, port mixups, and status codes |
| **Natural False Alarm Rate** | - | **73.33%** (11/15) | 11 clean model outputs falsely failed by heuristic judge |
| **Human vs. Injection Key Agreement** | - | **93.33%** (28/30) | High consistency between human grading and injection key |

### 4. Root Causes of Heuristic Collapse
1. **Brittleness on Natural Model Formats (False Alarm Rate: 73.3%):**
   - The judge's command-prefix checker validates only single shell executables (`KNOWN_SAFE_COMMAND_PREFIXES`). When the model output inline Python snippets (e.g., `from fastapi import BackgroundTasks...` or `app.add_middleware(...)`) or YAML blocks (`healthcheck: ...`, `depends_on: ...`) in the `command` field, the judge failed them as unrecognized executables.
   - For proper out-of-scope refusals, because the retriever returned nonzero semantic context chunks, the judge triggered its false-refusal heuristic (`"False refusal: system refused despite relevant technical context being retrieved"`), penalizing correct refusals.
2. **Blindness on Unmodeled Defects (Miss Rate: 40% on Novel Families):**
   - Because the judge does not execute commands in a sandboxed runner, it cannot detect misspelled flags (`--relod`, `--detatch`) or missing prerequisite dependencies (`pip install psycopg2-binary`).
   - Because token-overlap does not model semantics, factual contradictions (e.g. port 3306 vs 5432, HTTP 200 vs 422) pass undetected.
3. **Conclusion:** Static regex and token-overlap heuristics are fundamentally unsuitable as a standalone LLM judge. They overfit rapidly to training examples ($\kappa = 1.0$), but generalize poorly to real-world model outputs ($\kappa = -0.0667$). An execution sandbox and model-graded semantic evaluations are required for robust verification.


---

# Day 46: Automated CI Evaluation Gate & Reviewer Parser Bug Resolution

**Date:** 2026-11-08  
**Sprint Day:** Day 46 of 100  
**Phase:** Phase 1 (Trustworthy Evaluation & CI Gating)  
**Author:** Kumbham Nikhil  

---

### 1. Motivation & Objectives
On Day 45, two critical findings emerged:
1. Retrieval on the complete 10-file corpus reached 93.55% Hit@3 on the dev split (84.6% official docs, 100% owner guides), but lacked automated regression protection in continuous integration.
2. The heuristic evaluation judge collapsed under blind evaluation ($\kappa = -0.067$), driven primarily by a parser bug that treated multi-line Python, YAML, and Dockerfile syntax as invalid shell executables (73.3% false alarms on clean outputs) and penalized valid out-of-scope refusals.

Day 46 focuses on two engineering milestones:
1. **Automated CI Evaluation Gate:** Build and integrate a GitHub Actions workflow that executes the gold benchmark dev split on every PR and main push, failing builds if retrieval metrics regress.
2. **Reviewer Parser Bug Resolution:** Fix the code snippet parser and refusal accounting in `app/reviewer.py`, validating the fix against the Day 45 dev dataset.

---

### 2. Automated Per-Question CI Evaluation Gate (`eval/ci_eval_gate.py`)

A standalone CI regression harness was built and integrated into `.github/workflows/ci.yml`. Rather than relying on arbitrary percentage thresholds (where a single question swing on 13 official docs questions swings the score by 7.7% and breaks the build, and where Evidence Coverage@3 simply duplicates Hit@3 for single-span benchmarks), the CI gate enforces a deterministic **Per-Question Regression Check** against `eval/gold_benchmark_v2_dev_results.json`:

| Check | Scope | Enforced Requirement | Baseline Status | Status |
| :--- | :--- | :---: | :---: | :---: |
| **Span Coverage** | All 45 answerable questions | 100.0% gold spans in indexed corpus | 31/31 dev, 14/14 test | ✅ PASS |
| **Per-Question Retrieval** | 31 dev answerable questions | All 29 baseline hits maintained (0 regressions) | 29/31 hits (11/13 official, 18/18 owner) | ✅ PASS |
| **Per-Question Refusal** | 9 dev out-of-scope questions | All 8 baseline refusals maintained (0 leaks) | 8/9 refusals maintained | ✅ PASS |
| **Test ID Protection** | Held-out 25-question split | Match `test_ids.sha256` digest | `15c7f63b96...` | ✅ PASS |

If any question regresses from Hit to Miss, or any out-of-scope query leaks, `eval/ci_eval_gate.py` prints an actionable per-question diff and exits with code 1, automatically blocking CI merges.

---

### 3. Reviewer Parser Bug Fix & Dev Calibration (n=30)

#### Root-Cause Remediation in `app/reviewer.py`
1. **Multi-Syntax Snippet Classification:** Added `is_code_or_config_snippet()` to detect Python statements (`import`, `from`, `def`, `class`, `app.`, `@`, `cursor.`), YAML/Compose configurations (`version:`, `services:`, `healthcheck:`, `depends_on:`), and Dockerfile instructions (`FROM`, `RUN`, `COPY`, `WORKDIR`). These are evaluated for syntax and security patterns without checking single shell binary prefixes.
2. **Local Script Execution Support:** Relative paths (`./run_tests`, `.\script.ps1`) and standard build tools (`make`) are now recognized as valid CLI invocations.
3. **Refusal Gate Awareness:** Out-of-scope refusals are verified against `OUT_OF_BOUNDS_KEYWORDS` and refusal criteria, eliminating false refusal penalties when contextual chunks are returned by the retriever.
4. **CORS Warning Phrase Disambiguation:** Differentiated explanatory warnings ("cannot use wildcard origins with credentials") from actual policy violations.

#### Before vs. After on Day 45 Dev Dataset (n=30)

| Metric | Day 45 Frozen First-Run | Day 46 Post-Fix (Dev) | Absolute Change |
| :--- | :---: | :---: | :---: |
| **Observed Agreement** | 46.67% (14/30) | **70.00%** (21/30) | **+23.33 pts** (in-sample) |
| **Cohen's Kappa ($\kappa$)** | -0.0667 (Poor) | **0.4000** (Moderate) | **+0.4667** |
| **95% Wilson CI** | [30.2%, 63.9%] | **[52.1%, 83.3%]** | Lower bound $> 50\%$ |
| **Clean False Alarm Rate** | 73.33% (11/15) | **0.00%** (0/15) | **-73.33 pts** (15/15 pass) |
| **Defects Flagged / Recall** | 66.67% (10/15) | **40.00%** (6/15) | **-26.67 pts** (4 accidental catches eliminated) |
| **Missed Defects** | 33.33% (5/15) | **60.00%** (9/15) | +4 novel defects correctly identified as missed |

> [!WARNING]
> **In-Sample Disclosure:** The 70.0% agreement is strictly in-sample. The bug fixes were developed after inspecting the 30 Day 45 failure traces. Tuning heuristic rules on known failures is how the judge previously reached 100% on Day 44 before collapsing to 46.7% on blind data. A new blind evaluation batch is required to verify true out-of-sample generalization.
> Furthermore, defect recall dropped from 67% to 40% (6 caught, 9 missed) because the 4 novel catches on Day 45 were accidental hits triggered by the command parser choking on multi-line syntax, not genuine defect detection.

---

### 4. Phase 1 Architectural Trade-off: Retrieval vs. Full-Context

| Dimension | Hybrid-Rerank RAG | Full-Corpus In-Context | Impact / Assessment |
| :--- | :---: | :---: | :--- |
| **Prompt Tokens / Query** | **~2,235 tokens** | ~37,284 tokens | **~17x token reduction** (94.0% reduction) |
| **Turnaround Latency (P50)** | **~3,031 ms** (end-to-end) | ~4,201 ms (end-to-end) | **~1.4x faster turnaround** (retrieval-only is ~501 ms) |
| **Top-3 Evidence Coverage** | **93.55%** (29/31) | 100.0% (est.) | High fidelity with 2 minor chunk displacements |
| **Top-5 Evidence Coverage** | **100.00%** (31/31) | 100.0% | Perfect evidence capture within candidate pool |
| **Correctness Trade-off** | **87.5% AI-assisted hand grade** (35/40) | 85.0% AI-assisted hand grade (34/40) | **No detectable difference on dev** (CI `[-10.0%, +15.0%]`, $p=1.00$); **kept per [`decision_rule.md`](decision_rule.md)** (**caching not evaluated.**) |

---

# Day 47–48: Head-to-Head Dev Benchmark — Hybrid-Rerank RAG vs. Full-Context Baseline

**Date:** 2026-11-09 to 2026-11-10  
**Sprint Days:** Days 47–48 of 100  
**Phase:** Phase 1 (Trustworthy Evaluation & Baseline Validation)  
**Author:** Kumbham Nikhil  

---

### 1. Objective & Motivation
Throughout Phase 1, the central architectural trade-off remained open:
> *Does the hybrid-rerank RAG pipeline (Dense + BM25 + RRF + Cross-Encoder) actually provide value over simply stuffing the full 10-file corpus (~33k tokens) into Gemini's context window?*

To evaluate this on the Gold Benchmark v2 DEV split (40 questions: 31 answerable, 9 out-of-scope controls) under live model generation:
1. **Pipeline A (`hybrid-rerank`):** Retrieves candidate chunks, reranks them with `cross-encoder/ms-marco-MiniLM-L-6-v2`, and injects top-3 chunks (`~2,235` prompt tokens mean).
2. **Pipeline B (`full-context`):** Injects all 97 chunks from the complete 10-file verified corpus (`~33,298` prompt tokens mean) directly into the model context.
3. **Blind Grading & Key Generation:** Anonymized all 80 responses into a blind evaluation sheet ([`eval/grading_sheet_fullcontext_vs_hybrid.csv`](../eval/grading_sheet_fullcontext_vs_hybrid.csv)) with **per-question randomized** system aliases (`System-A`, `System-B`, seed=42) and a separate decryption key ([`eval/grading_key_fullcontext_vs_hybrid.json`](../eval/grading_key_fullcontext_vs_hybrid.json)).
4. **Automated Checks (Before Unblinding):** Recorded both the **LLM Schema-Format Pass Rate** (`40/40` vs `39/40`) and the offline **Reviewer Agent** audit (`39/40` vs `39/40`). Because Day 45–46 showed the Reviewer Agent misses real bugs, I completed AI-assisted human hand-grading on all 80 blinded responses before unblinding.

---

### 2. Automated Benchmark & Cost Metrics (n=40 Dev Questions)

| Evaluation Metric | Hybrid-Rerank RAG | Full-Context Baseline | Delta / Architectural Impact |
| :--- | :---: | :---: | :--- |
| **AI-Assisted Blind Hand Grade (Truth)** | **87.50%** (35/40) | **85.00%** (34/40) | **No detectable difference on dev** (+1 question, 95% CI `[-10.0%, +15.0%]`, $p = 1.0000$) |
| **Reviewer Agent Pass Rate (Automated)** | 97.50% (39/40) | 97.50% (39/40) | 0.0 pts (Missed 5 RAG & 6 Full-Context bugs) |
| **LLM Schema-Format Pass Rate** | **100.00%** (40/40) | 97.50% (39/40) | +2.50 pts (`+0.0250`, 95% CI `[+0.0000, +0.0750]` came from format check, *not* Reviewer Agent) |
| **Prompt Tokens (Mean, API Usage Metadata)** | **2,234.9 tokens** | 33,298.0 tokens | **14.9x Token Reduction (93.3% savings)** |
| **Turnaround Latency (P50)** | **6,125.6 ms** | 10,134.6 ms | **1.65x Faster Response Turnaround** |
| **Turnaround Latency (Mean)** | **5,972.0 ms** | 8,918.3 ms | **1.49x Faster Mean Latency** |
| **Time to First Token (TTFT P95)** | **2,274.0 ms** | 5,037.1 ms | **2.21x Faster Initial Token Delivery** |
| **API Rate-Limit / Quota Errors** | **0 errors** | 5 quota delays | Full-context repeatedly hits input token/min limits |
| **Cost per 1,000 Queries (Est.)** | **~$0.17** | ~$2.50 | **$2.33 saved per 1k queries** |

*(Correction to Day 47 README/log text: earlier wording juxtaposed the `39/40` Reviewer Agent score with the `+0.0250` bootstrap difference from the `40/40 vs 39/40` schema-format metric, and called Phase 1 settled on automated parity before blind hand-grading.)*

---

### 3. Automated Reviewer False Positives vs. Blind Inspection Findings

- **Automated Reviewer Agent False Flag (`GS-V2-03`):** Both systems scored `0.80` (FAIL) on the Reviewer Agent regex (`cors_wildcard_with_credentials`) simply because their anti-pattern warnings quoted `allow_origins=['*']` with `allow_credentials=True` while advising against it. Both passed blind human grading.
- **Unflagged Bugs Caught in Blind Grading:** The Reviewer Agent passed outputs that failed human review (`GS-V2-08`, `27`, `28`, `31`, `38`, `39`, `50`, `51`, `52` across the two systems).

---

### 4. Phase 1 Decision Rule Applied ([`decision_rule.md`](decision_rule.md)): **Keep Hybrid-Rerank on Cost & Margin**

Under the formalized Phase 1 decision rule in [`docs/decision_rule.md`](decision_rule.md):
> *"Keep the Hybrid-Rerank retrieval stack if dev quality is within 10 percentage points (95% CI includes `0`) and RAG is cheaper per query; revisit this architectural choice once the corpus grows past ~100k tokens."*

#### Applied Decision Rationale:
1. **Inconclusive Dev Quality Within 10-Point Margin:** Single-grader AI-assisted blind grading shows **35/40 (87.5%) vs. 34/40 (85.0%)** (`+2.5%`, 95% bootstrap CI `[-10.0%, +15.0%]`, McNemar exact $p = 1.0000$). At `n=40`, there is no detectable quality difference, the 95% CI includes `0`, and the lower bound meets the 10-point tolerance.
2. **Per-Query Cost & Latency Advantage (Caching Not Evaluated):** Full-context consumes **14.9x more uncached prompt tokens** per call (`33,298` vs `2,235`), adds ~2.9s to mean latency (`8,918 ms` vs `5,972 ms`) and ~2.8s to P95 TTFT (`5,037 ms` vs `2,274 ms`), and repeatedly triggers rate-limit exhaustion. **Caching not evaluated.**
3. **Re-Evaluation Trigger (~100k Tokens):** Adding Python, NumPy, and pandas in Lane B roughly triples the corpus past **~100k tokens**, which triggers a formal re-evaluation of the retrieval-vs-context trade-off.
4. **Applied Verdict & Pre-Declared Test Protocol:** **Keep Hybrid-Rerank RAG** per [`docs/decision_rule.md`](decision_rule.md). On the 25 held-out test questions (`--final`), run **`hybrid-rerank` only** (no full-context on test), report all proportions with **95% Wilson score confidence intervals**, make zero post-run edits, and log/retry errored quota questions only.

---

### 5. Artifacts Produced & Verified
- [`eval/hybrid_rerank_dev_results.json`](../eval/hybrid_rerank_dev_results.json): Full 40-question end-to-end dev benchmark results for hybrid-rerank.
- [`eval/full_context_dev_results.json`](../eval/full_context_dev_results.json): Full 40-question end-to-end dev benchmark results for full-context baseline.
- [`eval/phase1_comparison_analysis.json`](../eval/phase1_comparison_analysis.json): Reviewer Agent automated audit (`39/40` vs `39/40`).
- [`eval/grading_sheet_fullcontext_vs_hybrid.csv`](../eval/grading_sheet_fullcontext_vs_hybrid.csv): 80-row per-question randomized blind grading sheet with AI-assisted notes and owner-verified grades.
- [`eval/grading_key_fullcontext_vs_hybrid.json`](../eval/grading_key_fullcontext_vs_hybrid.json): Decryption key mapping anonymized aliases back to true system modes.

---

### 6. Unblinded AI-Assisted Hand-Grading Results (n=80 Evaluations across 40 Dev Questions)

All 80 responses were graded blind before unblinding using **AI-assisted** inspection (starting from AI-proposed defect notes checked and finalized by the owner prior to applying [`eval/grading_key_fullcontext_vs_hybrid.json`](../eval/grading_key_fullcontext_vs_hybrid.json)).

> [!IMPORTANT]
> **Per-Question Shuffle Note:** `System-A` and `System-B` were shuffled **independently per question** (seed=42), not fixed globally. For 7 of the 9 failing questions, `System-B` was `hybrid-rerank`; however, on **`GS-V2-31`** and **`GS-V2-51`**, **`System-A` was `hybrid-rerank`** and **`System-B` was `full-context`** (verified directly by matching `response_summary` strings against the raw JSON outputs).

| Human Evaluation Metric | Hybrid-Rerank RAG | Full-Context Baseline | Net Difference |
| :--- | :---: | :---: | :---: |
| **Overall Pass Grade** | **35 / 40 (87.5%)** | **34 / 40 (85.0%)** | **+1 question (+2.5%)** |
| **Answer Correctness (`answer_ok`)** | 37 / 40 (92.5%) | 38 / 40 (95.0%) | -1 question (-2.5%) |
| **Code Correctness (`code_ok`)** | **37 / 40 (92.5%)** | 35 / 40 (87.5%) | **+2 questions (+5.0%)** |
| *Automated Reviewer Agent (Before)* | *39 / 40 (97.5%)* | *39 / 40 (97.5%)* | *0.0 pts (GS-V2-03 false flag)* |
| *LLM Schema Format Check (Before)* | *40 / 40 (100.0%)* | *39 / 40 (97.5%)* | *+1 question (+2.5%)* |

#### Paired Contingency Table & Defect Attribution (n=40 Questions)
- **Both Systems Passed:** 31 questions (77.5%)
- **Hybrid Won (Pass vs. Fail — 4 questions):**
  - `GS-V2-08`: Full-context (`System-A`) had `NameError` from undefined annotation `'background_tasks'` instead of `BackgroundTasks`.
  - `GS-V2-27`: Full-context (`System-A`) caught `except psycopg2.errors.SyntaxError`, which does not catch `UndefinedColumn` from `SELECT invalid_syntax`.
  - `GS-V2-28`: Full-context (`System-A`) generated a one-line nested `with conn: with conn.cursor() as cur: cur.execute('...')` statement (`SyntaxError` in Python).
  - `GS-V2-51`: Full-context (`System-B`) answered the Banker's algorithm from pre-training knowledge while claiming it was out of corpus.
- **Full-Context Won (Fail vs. Pass — 3 questions):**
  - `GS-V2-31`: Hybrid (`System-A`) triggered a **false refusal** on an in-scope question even though the right psycopg2 chunk was cited.
  - `GS-V2-38`: Hybrid (`System-B`) produced an unexecuted snippet defining `ManagerSchema` where omitted field default `None` bypasses `@field_validator` (**empirically verified in Python/Pydantic v2**: `ManagerSchema(operation_type='UPDATE_BACKGROUND_COLOR')` passes silently without raising `ValueError` unless `validate_default=True` is enabled).
  - `GS-V2-52`: Hybrid (`System-B`) refused cleanly in text, but pointed to unrelated `man 2 mprotect`.
- **Both Systems Failed (2 questions):**
  - `GS-V2-39`: Hybrid (`System-B`) triggered a **false refusal** claiming lack of context on model validators despite citing `pydantic_validation` chunks; Full-context (`System-A`) falsely claimed field validators fail on the first error and called `from_exception_data` missing `type` keys.
  - `GS-V2-50`: Full-context (`System-A`) suggested `pip install vllm` and Hybrid (`System-B`) generated `--tensor-parallel-size 4` install + launch commands while stating the query was out of corpus.
- **Statistical Significance:**
  - Mean Difference: **$+2.50\%$** (+1 net question)
  - 95% Bootstrap Confidence Interval: **$[-10.00\%, +15.00\%]$** (10,000 paired resamples)
  - McNemar Exact Binomial Test: **$p = 1.0000$** (4 vs. 3 discordant pairs; statistically indistinguishable)

---

### 7. Day 47 vs. Day 48 CI Gate Output Reconciliation (Errata)

On Day 47 (2026-11-09), an assistant chat summary incorrectly printed legacy-style metrics (`Dev Hit@3: 92.50% (37/40)`, `Refusal Rate: 100.00% (9/9)`, `MRR: 0.8354`) when summarizing the `eval/ci_eval_gate.py` execution. Inspection of the actual Day 47 step log (`.system_generated/steps/4046/output.txt`), `eval/gold_benchmark_v2_dev_results.json`, an isolated detached-worktree run of `b28a03e`, and Day 48 `HEAD` (`eval/diff_day46_vs_head.md`) confirms that:
- **Which run was wrong:** Only the Day 47 chat summary message (`92.50% / 100.00% / 0.8354`) was erroneous.
- **Verified actual CI Gate output (both Day 47 and Day 48 `b28a03e` vs `HEAD`):** **Hit@3 = 29/31 (93.55%)**, **Official Docs Hit@3 = 11/13 (84.62%)**, **Owner Guides Hit@3 = 18/18 (100.00%)**, **Refusal Rate = 8/9 (88.89%)**, **Hit@5 = 31/31 (100.00%)**, **MRR = 0.8172**, with **0 per-question differences** across all 40 dev questions.
