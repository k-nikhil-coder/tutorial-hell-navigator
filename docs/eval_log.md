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
