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
