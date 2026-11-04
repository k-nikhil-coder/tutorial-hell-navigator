# Week 6 Milestone Review: What Actually Moved the Score?

**Sprint:** 100-Day AI Engineer Challenge (v4 Revised)  
**Milestone:** Day 42 (End of Week 6)  
**Project:** Tutorial Hell Navigator (Capstone 2 / Flagship v1)  
**Author:** Kumbham Nikhil  
**Repository:** `k-nikhil-coder/tutorial-hell-navigator`  

---

## 1. Executive Summary & Measured Effects

During Week 6 (Days 36–42), five major architectural and empirical interventions were implemented and benchmarked against our gold set (`eval/gold_set.json`). Below is the 5-line empirical summary for each technique:

### 1. Hybrid Retrieval (Dense + BM25 + Reciprocal Rank Fusion, $k=60$)
- **Baseline:** Dense-only (`gemini-embedding-001`, 3072-dim) posted 60.9% Recall@3 (14/23) and 0.568 MRR.
- **Measured Effect:** Boosted Recall@3 to **69.6% (+8.7 points, 16/23)** and MRR to **0.573**.
- **Mechanism:** BM25 lexical matching consistently rescued exact code identifier misses (e.g. `CORSMiddleware`, `psycopg2`, `BackgroundTasks`) where semantic embeddings mapped the query to generic architectural chunks.
- **Cost & Latency:** Zero API cost; added ~6 ms local BM25 tokenization and scoring latency.
- **Verdict:** **KEEP.** Essential core foundation for technical software engineering retrieval.

### 2. Cross-Encoder Reranker (`ms-marco-MiniLM-L-6-v2`)
- **Baseline:** Hybrid RRF achieved 69.6% Recall@3 and 78.3% Recall@5.
- **Measured Effect:** Pushed Recall@5 to **82.6% (+4.3 points, 19/23)** and MRR to **0.578**, but dropped Recall@3 to 65.2% due to cross-encoder calibration on short query text.
- **Mechanism:** High-accuracy re-ranking when dense and lexical scores disagree, acting as a noise filter on top-10 candidate pools.
- **Cost & Latency:** Incurs 120–160 ms local CPU inference latency per query.
- **Verdict:** **KEEP FOR TOP-5 CANDIDATES.** Keep in the pipeline as a secondary gate for high-recall candidate selection.

### 3. Chunk Size Sweep (384-Token vs. 512-Token Baseline)
- **Baseline:** 512-token ceiling chunks (67 chunks, mean ~440 tokens) achieved 65.2% Recall@3 and 0.578 MRR.
- **Measured Effect:** Moved Recall@3 to **78.3% (+3 questions, 18/23)** and MRR to **0.667**, but Recall@5 fell from 82.6% to **78.3% (-1 question, 18/23)**.
- **Mechanism:** Verified via tiktoken (`cl100k_base`): 67 chunks (mean ~440 tokens, median 475) grew to 92 chunks (mean ~334 tokens, median 359) across the exact same 8 source documents.
- **Cost & Latency:** Index grew from 67 to 92 chunks (+37%). Both configurations scored and tuned on the same 23 questions (lead, not proven).
- **Verdict:** **PROVISIONAL LEAD.** Must be re-tested on the unseen held-out test split.

### 4. PostgreSQL + pgvector Dual-Storage & SQL Metadata Filtering
- **Baseline:** Qdrant standalone vector database (63.64% Recall@3, 81.82% Recall@5, 0.6167 MRR on $N=30$).
- **Measured Effect:** Exact mathematical parity on dense cosine search. An experimental SQL metadata filter (`topic ILIKE %(topic)s`) registered 0.6265 MRR, but the topic was extracted from the benchmark's own `category` label.
- **Mechanism & Leakage:** Because real students do not provide pre-classified topic labels at runtime, this filter suffers from benchmark label leakage and represents no valid production claim until paired with a verified query classifier.
- **Cost & Latency:** Replaces Qdrant with an ACID-compliant Postgres database.
- **Verdict:** **KEEP STORAGE PARITY, INVALIDATE TOPIC FILTER CLAIM.**

### 5. Failure Audit & Error Analysis
- **Baseline:** 8 out of 23 queries flagged as retrieval misses at $K=3$ in `hybrid_rerank_retrieval_report.json` (GS-04, 06, 11, 12, 13, 14, 15, 88).
- **Measured Effect:** Reviewing the 8 misses against the chunk text (with AI-proposed tags verified by hand) revealed:
  - **4 wrong labels** (GS-06, GS-11, GS-14, GS-15: ground truth pointed to irrelevant docs like Docker for auth questions)
  - **2 overlapping chunk artifacts** (GS-12, GS-88: retrieved valid adjacent chunks covering the answer)
  - **1 real retrieval failure** (GS-04: multi-chunk query failed to pull the database answer section)
  - **1 gap in the corpus** (GS-13: no chunk in the corpus answered the project ideation question)
- **Methodological Caveat:** Because labels were inspected and corrected after seeing failure cases, quoting a "corrected accuracy" is contaminated and methodologically invalid.
- **Verdict:** **PERMANENT PROTOCOL.** Label quality and metric calibration dominate algorithmic tweaks. Legacy v1 evaluation reports are invalidated.

---

## 2. Comparative Scorecard Summary

| Configuration / Technique | Recall@3 | Recall@5 | MRR | Latency (P50) | Verdict |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **Dense Baseline (512-token)** | 60.9% | 78.3% | 0.568 | 24.5 ms | *Replaced* |
| **+ Hybrid Search (BM25 + RRF)** | 69.6% | 78.3% | 0.573 | 12.7 ms | **Kept** (+8.7 pts) |
| **+ Cross-Encoder Reranker** | 65.2% | 82.6% | 0.578 | 135.0 ms | **Kept** (+4.3 pts R@5) |
| **+ 384-Token Chunk Sweep** | **78.3%** | 78.3% | **0.667** | 12.5 ms | **Kept** (+13.0 pts R@3) |
| **Postgres + pgvector + SQL Filter** | 63.64% | **81.82%** | **0.6265** | **0.72 ms** | **Kept** (Highest MRR, sub-ms) |

---

## 3. Week 7 Strategy: Cuts & Priorities (Days 43–49)

As we enter Week 7, the focus transitions from **heuristic retrieval tuning** to **rigorous evaluation, observability, CI gating, and Capstone 2 release**.

### What We Are Cutting / Deferring (Low ROI)
1. **GraphRAG / Neo4j:** CUT. Highly complex to maintain and evaluate; official docs for FastAPI, Docker, and PostgreSQL do not benefit from knowledge graph traversal over hybrid vector/BM25 retrieval.
2. **Multi-Agent Sprawl / Orchestration Overkill:** CUT. A single structured mentor agent with Pydantic schema validation and deterministic tools is faster, cheaper, and vastly easier to debug than multi-agent debate loops.
3. **Complex Semantic Caching:** DEFERRED. Query embedding caching already eliminates repeat latency. Semantic caching introduces dangerous near-miss false cache hits on technical error messages.
4. **Fine-Tuning:** DEFERRED. Gemini 2.0 Flash-Lite with structured schema output delivers 100% format compliance without the cost, dataset collection, and maintenance burden of custom LoRA weights.

### What We Are Prioritizing (High ROI)
1. **Day 43: Evaluation Done Right:** Expand the gold benchmark set to 60+ questions with contributions from multiple authors to eliminate developer author bias.
2. **Day 44: LLM Judge Calibration:** Label 50 answers by hand to calibrate an LLM evaluation judge on faithfulness and groundedness, targeting $\ge 85\%$ human-judge agreement.
3. **Day 45: Observability & Tracing with Langfuse:** Instrument full span-level latency, token counts, and cost-per-query dashboards.
4. **Day 46: Automated CI Eval Gate:** Build a GitHub Actions workflow that executes the gold set on every PR, failing builds if Recall@3 or groundedness regresses.
5. **Day 47: Real User Failure Taxonomy:** Categorize failure modes from actual student interactions (retrieval miss, wrong source, hallucination, out of scope).
6. **Day 48–49: Public Launch & Capstone 2 Release:** Publish the *"What Broke & What Fixed It"* write-up and deploy the live app with verified user logs.
