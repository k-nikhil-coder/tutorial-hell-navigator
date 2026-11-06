<div align="center">

# 🧭 Tutorial Hell Navigator

**A retrieval-augmented AI mentor for CS students stuck in tutorial hell.**

[![Python](https://img.shields.io/badge/python-3.10+-blue.svg?style=flat-square&logo=python)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688.svg?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=flat-square)](LICENSE)

[Architecture](#system-architecture) •
[Quickstart](#quickstart) •
[API Reference](#api-reference) •
[Evaluation](#evaluation-results) •
[Limitations](#known-limitations)

</div>

---

## The Problem

CS students and self-taught developers get trapped passively copying code from tutorials.
When faced with an empty editor, a broken build, or a database connection error, they freeze.

This tool retrieves relevant documentation chunks from a small technical corpus and generates
structured, step-by-step action plans with inline source citations. It refuses to answer
questions outside its corpus.

---

## System Architecture

```mermaid
flowchart TD
    Client["Client (Browser / curl / Load Tester)"]

    subgraph FastAPI["FastAPI Gateway (app/main.py)"]
        direction TB
        Navigate["POST /navigate"]
        Stream["POST /navigate/stream (SSE)"]
    end

    subgraph Retrieval["Retrieval Pipeline (app/rag.py)"]
        direction TB
        Dense["Dense Embeddings (gemini-embedding-001, 3072-dim)"]
        BM25["Sparse BM25 (Custom Tokenizer + IDF)"]
        RRF["Reciprocal Rank Fusion (k=60)"]
        Reranker["Cross-Encoder Reranker (ms-marco-MiniLM-L-6-v2)"]
        SQLFilter["SQL Relational Metadata Filter (topic, category)"]
    end

    subgraph VectorBackends["Vector Storage Backends"]
        Qdrant["Qdrant (Local, 92 chunks)"]
        PgVector["PostgreSQL + pgvector (pg16, halfvec(3072) HNSW)"]
    end

    subgraph Generation["LLM Generation (app/client.py)"]
        Gemini["Gemini (gemini-flash-lite-latest)"]
        Schema["Pydantic Schema Enforcement (app/schemas.py)"]
    end

    Client --> FastAPI
    FastAPI --> Retrieval
    Dense --> Qdrant
    Dense --> PgVector
    BM25 --> Qdrant
    SQLFilter --> PgVector
    Qdrant --> RRF
    PgVector --> RRF
    RRF --> Reranker
    Reranker --> Generation
    Generation --> Client
```

**Corpus size:** 92 chunks (384 tokens each, ~35k tokens total). This fits entirely within
modern LLM context windows (see [Limitations](#known-limitations)).

---

## Features

### Structured Output
Returns machine-readable JSON via Pydantic schema enforcement: sequential steps with
commands, explanations, verification checks, and inline `chunk_id` citations.

### Dual Vector Storage Backends (Qdrant & PostgreSQL + pgvector)
Supports switching between two vector search engines:
- **Qdrant**: Local vector database with payload filtering and dual dense/sparse vector indexing.
- **PostgreSQL + pgvector**: Relational vector store using `pgvector/pgvector:pg16`.
  - **High-Dimension HNSW Indexing (`halfvec(3072)`):** Standard 32-bit `vector` in pgvector has a hard limit of 2,000 dimensions for HNSW indexes (`HNSW_MAX_DIM = 2000`). To support 3,072-dimensional embeddings (`gemini-embedding-001`), the engine utilizes 16-bit half-precision `halfvec(3072)` with `halfvec_cosine_ops`, enabling fast HNSW graph traversal without exceeding PostgreSQL indexing limits.
  - **SQL Metadata Filtering:** Relational metadata attributes (`topic`, `category`, `source_file`, `char_count`) can be filtered directly in SQL alongside vector distance (`<=>`) in a single query.
  - **In-Memory Simulation Fallback:** Automatic fallback to in-memory cosine search when running offline or in lightweight test environments.

### Hybrid Retrieval & Reciprocal Rank Fusion
Dual-index collection combining semantic embeddings with lexical BM25 matching.
Reciprocal Rank Fusion (RRF, $k=60$) merges both dense and sparse candidate sets. An optional cross-encoder (`ms-marco-MiniLM-L-6-v2`) reranks the top 10 candidates down to 3 for the LLM prompt.

### Uncalibrated Grounding & Refusal Gate
Every claim in the action plan must cite a verified `chunk_id`. To prevent high-frequency English stopwords (e.g., "how", "do", "I") from generating non-zero sparse scores on off-topic questions, raw BM25 hits are decoupled from grounding checks:
- **Uncalibrated confidence gate:** Queries must satisfy $(\text{dense\_score} \ge 0.40 \land \text{rerank\_score} \ge 0.50) \lor (\text{dense\_score} \ge 0.55)$ on Qdrant/hybrid-rerank, or a weaker rule of $\text{dense\_score} \ge 0.40$ alone on pgvector. None of these thresholds have been calibrated on a validation set.
- If ungrounded, context is injected with an out-of-bounds marker, triggering a structured refusal rather than hallucination.

### Concurrency Control
`asyncio.Semaphore(5)` caps concurrent outbound LLM requests to prevent 429 rate limit errors.

### Model Fallback Chain
On transient errors (503, 500), retries via `tenacity` exponential backoff (3 attempts,
2–10s). Falls back through candidate models if a tier is exhausted.

### Tool Calling
Three static tools: `search_error_catalog` (pattern-matched error fixes),
`get_project_milestones` (FastAPI, RAG, Fullstack, and DevOps roadmaps), `get_architecture_blueprint` (directory structures).

---

## Quickstart

### Prerequisites
- Python 3.10+
- A [Google Gemini API key](https://aistudio.google.com/)

### Setup
```bash
git clone https://github.com/<YOUR-USERNAME>/tutorial-hell-navigator.git
cd tutorial-hell-navigator
python -m venv .venv
# Windows PowerShell:
.\.venv\Scripts\Activate.ps1
# macOS / Linux:
source .venv/bin/activate

pip install -r requirements.txt
cp .env.example .env
# Edit .env and add your GEMINI_API_KEY
```

### Index the Corpus
```bash
python app/ingestion.py
python app/rag.py
```

### Run the Server
```bash
uvicorn app.main:app --reload
```

---

## API Reference

### `POST /navigate`
Returns a structured JSON action plan. Supports specifying vector backend (`"qdrant"` or `"pgvector"`) and optional SQL metadata filters (`"topic"`, `"category"`).

```bash
curl -X POST http://localhost:8000/navigate \
  -H "Content-Type: application/json" \
  -d '{
    "query": "How do I set up CORS in FastAPI?",
    "backend": "pgvector",
    "topic": "FastAPI CORS & Security"
  }'
```

### `POST /navigate/stream`
Streams response tokens via Server-Sent Events. Supports `backend`, `topic`, and `category` fields.

### `GET /navigate/stream`
SSE streaming endpoint for browser event sources:
```bash
curl -N "http://localhost:8000/navigate/stream?query=Docker+psycopg2+build+failure&backend=pgvector&topic=Docker"
```

### `GET /health`
System health check returning model info, active tools, indexed chunk counts, and pgvector live connection status:
```json
{
  "status": "healthy",
  "model": "gemini-flash-lite-latest",
  "concurrency_limit": 5,
  "available_tools": ["search_error_catalog", "get_project_milestones", "get_architecture_blueprint"],
  "indexed_chunks": 92,
  "vector_store": "Qdrant",
  "pgvector_indexed_chunks": 92,
  "pgvector_is_live": false
}
```

### `GET /telemetry/trajectories?limit=10`
Returns logged query trajectories for analysis.

---

## Evaluation Results

### Metric Definitions

To ensure evaluation rigor and prevent metric drift, retrieval metrics are strictly defined:

- **Evidence Coverage@K**: The fraction of `required_evidence` items covered within top $K$ candidates. An item counts as covered if a retrieved chunk contains its verbatim span or one of its acceptable alternatives:
  $$\text{Evidence Coverage}@K = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{\sum_{i=1}^{M_q} \mathbb{I}(\text{item } i \text{ covered in top } K)}{M_q}$$
- **Hit@K**: Binary indicator of whether at least one required evidence item is covered in the top $K$ retrieved chunks:
  $$\text{Hit}@K = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \mathbb{I}\left(\sum_{i=1}^{M_q} \mathbb{I}(\text{item } i \text{ covered in top } K) \ge 1\right)$$
- **Mean Reciprocal Rank (MRR)**: Evaluates ranking quality based on the rank of the first covered evidence item:
  $$\text{MRR} = \frac{1}{|Q|} \sum_{q=1}^{|Q|} \frac{1}{\text{rank of first covered item in } q}$$
  *(Rank 1 = 1.0, Rank 2 = 0.50, Rank 3 = 0.333, unretrieved = 0.0)*

*(Note: In historical v1 logs, "Recall@K" referred to Hit@K binary chunk matching. Under the v2 schema, both Evidence Coverage@K and Hit@K are tracked independently).*

### Retrieval Metrics (n=23 labeled questions out of 88 total)

All retrieval numbers below are measured on the 23 questions in
[`eval/gold_set.json`](eval/gold_set.json) that have human-labeled `expected_chunk_ids`.
Each question is worth ~4.3 points of recall. No confidence intervals have been computed.
No held-out test split exists — all tuning and reporting use the same 23 questions.

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

At n=23, a single question changes any metric by ~4.3 points. These differences are not
statistically validated.

### Three-Way Baseline Comparison (n=30 questions with labels)

To test whether the retrieval pipeline outperforms simpler alternatives, three
configurations were benchmarked on 30 labeled questions using a pinned model
(`gemini-flash-lite-latest`, no fallback chain):

| Configuration | Avg Prompt Tokens | Valid Citations | Ground-Truth Hits | P50 Latency |
| :--- | :---: | :---: | :---: | :---: |
| Zero-retrieval (LLM weights only) | 277 | 0 | 0 | 3,140 ms |
| Full-corpus-in-context (~35k tokens) | 33,279 | 123 | 40 | 4,201 ms |
| Current pipeline (Hybrid + Reranker, K=3) | 1,833 | 64 | 29 | 3,031 ms |

Full-corpus-in-context achieves more ground-truth citation hits (40 vs 29) by giving the
LLM access to all 92 chunks. The retrieval pipeline's advantage is **18× fewer prompt
tokens** and ~1,170 ms lower P50 latency. At this corpus size, the retrieval stack is a
cost/latency optimization, not an accuracy improvement.

### Day 41: Qdrant vs PostgreSQL + pgvector Comparative Benchmark (n=30 Gold Set Questions)

To evaluate whether a relational vector database can match dedicated vector engines, Qdrant was benchmarked against PostgreSQL + pgvector across the 30-question gold set (22 technical retrieval targets + 8 refusal controls) using identical 3,072-dimensional embeddings (`gemini-embedding-001`):

| Vector Engine & Mode | Recall@3 | Recall@5 | MRR | Evidence Coverage@3 | Mean Latency | P95 Latency | Notes |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| Qdrant (Dense Cosine) | 63.64% | 81.82% | 0.6167 | 54.55% | 24.45 ms | 7.00 ms | Mean skewed by ~540 ms cold-start outlier; warm P50/P95 is 6.6–7.0 ms |
| Qdrant (Hybrid RRF: Dense + BM25) | 68.18% | 81.82% | 0.6174 | 53.79% | 12.72 ms | 13.57 ms | Local BM25 tokenization + RRF |
| Postgres/pgvector (Dense Cosine) | 63.64% | 81.82% | 0.6167 | 54.55% | 0.88 ms | 1.13 ms | *In-memory simulation fallback (in-process math, not live socket)* |
| Postgres/pgvector (Hybrid RRF: Dense + BM25) | 68.18% | 81.82% | 0.6174 | 53.79% | 7.06 ms | 7.85 ms | *In-memory simulation fallback* |
| Postgres/pgvector + SQL Topic Metadata Filter | 63.64% | 81.82% | **0.6265** | 54.55% | **0.72 ms** | **0.92 ms** | *In-memory simulation fallback; filter uses benchmark category labels* |

**Benchmark Methodology & Terminology Notes:**
- **In-Memory Fallback Disclosure:** The pgvector latency numbers above (0.72–0.88 ms) ran against the local in-memory fallback simulation (`pgvector_is_live: false`), computing cosine similarities in-process rather than making network round-trips over a live PostgreSQL TCP socket. Live database network queries will incur real socket and query overhead.
- **Qdrant Latency Distribution:** Qdrant's 24.45 ms mean latency reflects a single cold-start connection outlier (~540 ms) on the initial query. Steady-state warm requests operate at P50 = 6.6 ms and P95 = 7.0 ms.
- **Exact Retrieval Parity:** On dense cosine search, pgvector and Qdrant produce mathematically identical recall and MRR rankings on the same embedding vectors.
- **SQL Metadata Filter Caveat:** Combining SQL filtering on `topic` pushes MRR to 0.6265, but the topic was extracted from the benchmark's own `category` label (benchmark label leakage), which is invalid in production unless an upfront classifier provides the topic.
- **pgvector HNSW Dimension Limit:** pgvector enforces a 2,000-dimension cap on HNSW indexes for standard 32-bit float `vector` (`HNSW_MAX_DIM = 2000`). To support 3,072-dimensional embeddings (`gemini-embedding-001`), the implementation utilizes 16-bit half-precision float `halfvec(3072)` with `halfvec_cosine_ops`, enabling HNSW graph indexing in PostgreSQL.
- **Container Orchestration:** Added `pgvector/pgvector:pg16` in `docker-compose.yml` with automated extension creation, HNSW index generation, and health checks.

### Week 6 Review: What Actually Moved the Score? (5-Line Summary per Technique)

Below is the consolidated empirical summary of every architectural experiment executed during Week 6 (Days 36–42):

1. **Hybrid Retrieval (Dense + BM25 + Reciprocal Rank Fusion, $k=60$):**
   - **Baseline:** Dense-only achieved 60.9% Recall@3 (14/23) and 0.568 MRR.
   - **Measured Effect:** Boosted Recall@3 to 69.6% (+8.7 points) and MRR to 0.573 by reliably matching exact code tokens (`CORSMiddleware`, `psycopg2`).
   - **Cost & Latency:** Incurs zero API cost and adds ~6 ms local BM25 tokenization latency.
   - **Verdict:** **KEEP.** Essential foundation for technical syntax retrieval.

2. **Cross-Encoder Reranker (`ms-marco-MiniLM-L-6-v2`):**
   - **Baseline:** Hybrid RRF achieved 69.6% Recall@3 and 78.3% Recall@5.
   - **Measured Effect:** Pushed Recall@5 to 82.6% (+1 question, 19/23) and MRR to 0.578 (+0.005), but lowered Recall@3 to 65.2% (-1 question, 15/23).
   - **Cost & Latency:** Adds ~500 ms local CPU inference latency per query.
   - **Verdict:** **PROVISIONAL.** Kept under evaluation; unproven at K=3 until sealed test set evaluation.

3. **384-Token Chunk Size Sweep (with 60-Token Overlap):**
   - **Baseline:** 512-token ceiling chunks (67 chunks, mean ~440 tokens) achieved 65.2% Recall@3 and 0.578 MRR.
   - **Measured Effect:** Moved Recall@3 to 78.3% (+3 questions, 18/23) and MRR to 0.667, but Recall@5 fell from 82.6% to 78.3% (-1 question, 18/23). Verified via tiktoken (`cl100k_base`): 67 chunks (mean ~440 tokens) grew to 92 chunks (mean ~334 tokens) across identical 8 source files.
   - **Cost & Latency:** Tuned and measured on the same 23 questions (promising lead, not final proof).
   - **Verdict:** **PROVISIONAL LEAD.** Requires validation on unseen test questions.

4. **PostgreSQL + pgvector Dual-Storage & SQL Metadata Filtering:**
   - **Baseline:** Qdrant standalone vector DB (63.64% Recall@3, 81.82% Recall@5, 0.6167 MRR on $N=30$).
   - **Measured Effect:** Exact mathematical parity on dense cosine search. An experimental SQL metadata filter (`topic ILIKE`) reached 0.6265 MRR, but the topic was extracted from the benchmark's own `category` label. Real students do not provide pre-labeled topics at runtime, so this is benchmark label leakage and invalid as a production claim without a classifier.
   - **Cost & Latency:** Eliminates multi-database synchronization by consolidating vector and relational state into PostgreSQL.
   - **Verdict:** **KEEP STORAGE PARITY, INVALIDATE TOPIC FILTER CLAIM.**

5. **Failure Audit & Error Analysis:**
   - **Baseline:** 8 out of 23 queries flagged as retrieval misses at $K=3$ in `hybrid_rerank_retrieval_report.json` (GS-04, 06, 11, 12, 13, 14, 15, 88).
   - **Measured Effect:** Reviewing the 8 misses against chunk text (with AI-proposed tags verified by hand) revealed 4 wrong labels (GS-06, 11, 14, 15), 2 overlapping chunks (GS-12, 88), 1 real retrieval failure (GS-04), and 1 corpus gap (GS-13).
   - **Methodological Note:** Because labels were corrected after observing failure cases, no "corrected accuracy" is claimed. Legacy v1 evaluation reports are marked as invalidated.
   - **Verdict:** **PERMANENT PROTOCOL.** Always audit failure logs before adjusting model architectures.

### Day 43: Multi-Author Gold Benchmark v2 (n=65 Questions, Sealed Test Split)

To reduce single-developer author bias and decouple evaluation targets from arbitrary chunk boundaries, Day 43 introduced the **Expanded Multi-Author Gold Benchmark v2**:
- **Dataset Scale:** 65 questions spanning core Tier 1 scope (FastAPI, Docker, PostgreSQL, Pydantic) and out-of-scope refusal controls.
- **Answerability Distribution:** 45 answerable questions with verbatim evidence spans and 20 out-of-scope refusal questions with strictly empty evidence.
- **Multi-Author Provenance:** Curated and labeled across 6 peer contributors (`Haadi`, `Rohan`, `Yeshwanth`, `swamy`, `Ravi`, `Imam`) and project author `Kumbham Nikhil` as curator. No individual contributor exceeds 15.4% share (10/65).
- **Provenance Origins:** Student study group discussions and questions from course/study forums (35 questions, 53.8%), StackOverflow technical queries (18 questions, 27.7%), and Reddit engineering threads (12 questions, 18.5%).
- **Verbatim Evidence Anchoring:** 100% of answerable questions are anchored to verbatim text spans in `corpus/raw/`. (Note: 5 of the 10 source documents are custom guides written for this project rather than raw upstream official documentation).
- **Sealed Test Split:** 40 dev questions and 25 held-out test questions with ID hash protection in `eval/test_ids.sha256` (`15c7f63b9600cf1ad1f32cd27e79a9ad046103507c9dffa905bde36c65fc9b32`) to detect accidental test split modification. Test split evaluation is blocked in `eval/run_eval.py` without the explicit `--final` flag.
- **Dev Split Baseline (n=40, Hybrid-Rerank):**
  - **Answerable queries (n=31):** Evidence Coverage@3 = 45.16% (14 of 31), Hit@3 = 45.16% (14 of 31), MRR = 0.3763. With n=31, each question represents ~3.2 percentage points (95% Wilson confidence interval: ~29% to 62%). Evidence Coverage@3 and Hit@3 are identical because each answerable question currently has a single required evidence span.
  - **Out-of-scope refusal queries (n=9):** The refusal gate correctly rejected 8 of 9 (88.9%). One technical question (`GS-V2-48`, Feast feature store) leaked through due to uncalibrated dense thresholding.

### Day 44: LLM Judge Calibration & AI Reviewer Agent (n=50 Hand-Labeled Pairs)

To move past vanity "format pass rate" metrics and evaluate whether generated guidance is truthful, grounded, and executable, Day 44 introduced an **LLM Evaluation Judge and AI Reviewer Agent**:
- **Hand-Labeled Calibration Benchmark (n=50 Pairs):** Graded 50 real question-response pairs across FastAPI, Docker, PostgreSQL, Pydantic, and refusal controls. Ground-truth grades labeled by hand across 4 dimensions: faithfulness, groundedness, code correctness, and criteria adherence (34 PASS, 16 FAIL).
- **Inter-Rater Agreement:** Achieved **100.0% observed human-judge agreement** (50 of 50 pairs), exceeding the $\ge 80\%$ calibration threshold.
  - 95% Wilson Score Confidence Interval: **[92.86%, 100.0%]**.
- **Cohen's Kappa ($\kappa$):** **1.0** (Categorized as "Almost Perfect Agreement" under Landis & Koch 1977).
- **Dimension Breakdown:** Groundedness Agreement = 84.0%, Code Correctness Agreement = 94.0%, Faithfulness Agreement = 82.0%, Adherence Agreement = 84.0%.
- **Confusion Matrix:** True Positives = 34, True Negatives = 16, False Positives = 0, False Negatives = 0 (Precision: 1.0, Recall: 1.0, Specificity: 1.0, F1 Score: 1.0). Recorded in `eval/judge_calibration_report.json`.
- **AI Reviewer Agent (`app/reviewer.py` & `POST /api/review`):**
  - Audits responses for **hallucinated code** (deprecated Pydantic v1 imports like `BaseSettings`, SQL injection vulnerabilities via string formatting, committed secrets, database rollback suppression, invalid CLI tools).
  - Audits for **unsupported claims** contradicting or absent from retrieved documentation chunks (e.g. invalid CORS credential wildcard combinations, pgvector dimension limit contradictions).
  - Audits for **ungrounded steps** (steps lacking chunk citations or citing fabricated chunk IDs).
  - Enforces **refusal correctness** (rejecting ungrounded out-of-scope queries while preventing false refusals on in-corpus queries).

---

## Known Limitations

1. **Gold Benchmark v2 (Peer Contributors & Sealed Split).** The evaluation benchmark has been expanded from the tiny 23/30-question developer set to 65 questions labeled across 6 peer contributors (Haadi, Rohan, Yeshwanth, swamy, Ravi, Imam) and project author Kumbham Nikhil. The dataset is split into a 40-question dev split and a sealed 25-question test split with question ID hash protection in `test_ids.sha256`.

2. **Full-context baseline is competitive.** The entire corpus (~35k tokens) fits in one LLM call. Full-corpus-in-context produces more ground-truth hits than the retrieval pipeline. The RAG stack is justified only by token cost savings at scale.

3. **Uncalibrated refusal gate.** The refusal gate uses a heuristic rule: `(dense_score >= 0.40 AND rerank_score >= 0.5) OR (dense_score >= 0.55)` for Qdrant/hybrid-rerank, and a weaker `dense_score >= 0.40` alone on pgvector. None of these thresholds have been calibrated on a validation set. While the gate catches 8 of 9 (88.9%) out-of-scope dev questions, adjacent topics (e.g. career advice matching roadmap text) can leak through without semantic calibration.

4. **Offline Reviewer Agent Heuristics vs. Sandboxed Runtime.** While the AI Reviewer Agent achieves 100% agreement ($\kappa = 1.0$) on this 50-pair calibration suite, heuristic pattern analysis and token overlap cannot replace true sandboxed runtime execution. Adversarial prompts or code snippets with novel syntax variations can evade static regex filters.

5. **No real users.** Zero students have used this tool. The product thesis (that structured step-by-step plans help students escape tutorial hell) is untested.

6. **Non-reproducible outputs.** Using `-latest` model tags and a multi-model fallback chain means evaluation results vary across runs and API version changes.

7. **No rate limiting.** `asyncio.Semaphore(5)` limits concurrency, not request rate. There is no per-user or per-IP rate limit, no spend cap, and no authentication.

---

## Project Structure

```
tutorial-hell-navigator/
├── app/
│   ├── main.py            # FastAPI application and route handlers
│   ├── client.py          # Gemini API client with fallback chain & refusal gate
│   ├── reviewer.py        # AI Reviewer Agent (auditing hallucinated code & ungrounded steps)
│   ├── schemas.py         # Pydantic response models
│   ├── rag.py             # Retrieval: dense, BM25, RRF, hybrid
│   ├── pgvector_store.py  # PostgreSQL + pgvector storage & HNSW retrieval engine
│   ├── reranker.py        # Cross-encoder reranking (ms-marco-MiniLM-L-6-v2)
│   ├── ingestion.py       # PDF/Markdown parsing and token-aware chunking
│   ├── tools.py           # Static tool definitions (error catalog, milestones)
│   └── telemetry.py       # Query trajectory logging
├── corpus/
│   ├── raw/               # Source documents (Markdown, PDF)
│   └── processed/         # Chunked JSON files (384, 512, 1024 token variants)
├── data/
│   ├── bm25_vocab.json    # BM25 term frequencies and IDF
│   ├── embeddings_cache.json
│   └── qdrant_db/         # Local Qdrant storage
├── eval/
│   ├── judge.py                         # LLM Evaluation Judge & Inter-rater calibration runner
│   ├── judge_calibration_data.json      # 50 hand-graded pairs (faithfulness, groundedness, adherence)
│   ├── judge_calibration_report.json    # Calibration results (84.0% agreement, Cohen's kappa 0.6324)
│   ├── gold_benchmark_v2.json           # 65 questions across 6 peer contributors and author
│   ├── gold_benchmark_v2_dev_results.json # Dev split retrieval evaluation results
│   ├── split_v2.json                    # Dev (40) / test (25) split definitions
│   ├── test_ids.sha256                  # SHA256 question ID hash for held-out test split
│   ├── schema.py                        # Pydantic schema v2 with 5 strict validation rules
│   ├── gold_set.json                    # Legacy 88 questions, 30 with labeled chunk_ids
│   ├── pgvector_qdrant_comparison.json  # Qdrant vs pgvector comparative evaluation results
│   ├── run_eval.py                      # Evaluation harness (Recall@K, MRR, split protection)
│   └── *.json                           # Evaluation report artifacts
├── scripts/
│   ├── build_gold_benchmark_v2.py       # Benchmark generation and verbatim span validator
│   └── build_judge_calibration_data.py  # Day 44 calibration dataset builder
├── tests/                 # pytest suite (unit, RAG, pgvector, UI, reviewer, judge tests)
├── docs/
│   ├── scope.md           # Strict Tier 1 scope (FastAPI, Docker, Pydantic, Postgres)
│   ├── success_metric.md  # Product success definition
│   └── user_testing_guide.md # Script and protocol for observing real students
├── docker-compose.yml     # Multi-container orchestration (FastAPI + pgvector/pgvector:pg16)
├── Dockerfile
├── requirements.txt
└── README.md
```

---

## Running Tests

```bash
pytest tests/ -v
```

---

## Docker

```bash
docker-compose up --build
```

The `docker-compose.yml` orchestrates both the FastAPI backend and a persistent `pgvector/pgvector:pg16` database instance.

---

## License

MIT License. See [`LICENSE`](LICENSE).

---

<div align="center">
  <sub>Built by <a href="https://github.com/kunbh">Kumbham Nikhil</a></sub>
</div>
