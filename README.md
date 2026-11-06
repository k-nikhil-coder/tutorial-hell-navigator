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
structured, step-by-step action plans with inline source citations. It attempts to refuse to answer
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

Detailed historical progression, ablations, baseline comparisons, and failure audits are documented in [`docs/eval_log.md`](docs/eval_log.md). Below is the current measured state of the system:

### Current Benchmark Status

| Metric | Target | Current Pipeline | Baseline / Ceiling | Status |
| :--- | :---: | :---: | :---: | :--- |
| **Dev Split Hit@3 (v2)** | $\ge 80\%$ | **45.16%** (14/31) | 45.16% structural ceiling | ⚠️ **Corpus gap:** 17 of 31 spans reference unindexed files |
| **Dev Split Evidence Coverage@3** | $\ge 80\%$ | **45.16%** (14/31) | 45.16% structural ceiling | 100% retrieval on indexable spans (14/14 retrieved) |
| **Dev Split MRR** | — | **0.3763** | — | Evaluated on Hybrid-Rerank (384-token chunks) |
| **Out-of-Scope Refusal Rate** | $\ge 90\%$ | **88.9%** (8/9) | 0% (zero-refusal baseline) | 1 technical query (`GS-V2-48`) leaked past gate |
| **Judge First-Run Agreement** | $\ge 80\%$ | **84.0%** (42/50) | 95% Wilson CI: [71.5%, 91.7%] | Substantial ($\kappa = 0.6324$); lower bound misses 80% gate |
| **P50 Generation Latency** | $< 3,000\text{ ms}$ | **3,031 ms** | 4,201 ms (full context) | Saves ~18× prompt tokens vs full corpus |

> [!IMPORTANT]
> **Understanding the 45.16% Retrieval Score (Structural Index Ceiling):**
> The 40-question dev split contains 31 answerable questions. Auditing chunk text reveals that **17 of these 31 questions** reference evidence in 3 source files (`fastapi_validation.md`, `docker_compose.md`, `postgresql_psycopg2.md`) that exist in `corpus/raw/` but were omitted from the current 8-file `chunks_384.json` index.
> The theoretical maximum retrieval score on this index is therefore **14 of 31 (45.16%)**. The hybrid-rerank pipeline retrieved **14 of 14 indexable questions (100% of available ceiling)** with zero misses on indexed material. Indexing the 3 missing files is required before higher recall can be measured.

> [!NOTE]
> **Heuristic Judge Calibration & Overfitting Disclosure:**
> The first-run inter-rater calibration between human grades and the automated judge scored 84.0% observed agreement ($\kappa = 0.6324$, 95% CI [71.5%, 91.7%]). While subsequent post-hoc rule adjustments drove measured agreement to 100% ($\kappa = 1.0$) on these same 50 pairs, that number represents training-set memorization and is not a valid generalization claim. All 16 FAIL pairs were synthetic bad answers written by hand to test known anti-patterns (0 real model outputs). The judge is a heuristic regex/token-overlap checker and does not execute commands. Full details and pre-tuning commit tags are documented in [`docs/eval_log.md`](docs/eval_log.md).

---

## Known Limitations

1. **Gold Benchmark v2 (Peer Contributors & Sealed Split).** The evaluation benchmark has been expanded from the tiny 23/30-question developer set to 65 questions labeled across 6 peer contributors (`contributor_1` through `contributor_6`) and project author Kumbham Nikhil. The dataset is split into a 40-question dev split and a sealed 25-question test split with question ID hash protection in `test_ids.sha256`.

2. **Full-context baseline is competitive.** The entire corpus (~35k tokens) fits in one LLM call. Full-corpus-in-context produces more ground-truth hits than the retrieval pipeline. The RAG stack is justified only by token cost savings at scale.

3. **Uncalibrated refusal gate.** The refusal gate uses a heuristic rule: `(dense_score >= 0.40 AND rerank_score >= 0.5) OR (dense_score >= 0.55)` for Qdrant/hybrid-rerank, and a weaker `dense_score >= 0.40` alone on pgvector. None of these thresholds have been calibrated on a validation set. While the gate catches 8 of 9 (88.9%) out-of-scope dev questions, adjacent topics (e.g. career advice matching roadmap text) can leak through without semantic calibration.

4. **Offline Reviewer Agent Heuristics vs. Sandboxed Runtime.** The reviewer agent is an offline audit endpoint relying on static regexes, token overlap, and chunk ID verification. It does not execute commands in a sandboxed runtime. While post-hoc rule adjustments scored 100% on the 50 development pairs, the honest first-run calibration was 84.0% ($\kappa = 0.6324$, 95% CI [71.5%, 91.7%]), which does not clear the 80% calibration gate with statistical confidence on unseen examples. Adversarial prompts or code snippets with novel syntax variations easily evade static filters.

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
│   ├── judge.py                         # Heuristic evaluation judge & calibration engine
│   ├── judge_calibration_data.json      # 50 hand-graded pairs (faithfulness, citation validity, adherence)
│   ├── judge_calibration_report.json    # First-run calibration results (84.0% agreement, Cohen's kappa 0.6324)
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
│   ├── eval_log.md        # Comprehensive evaluation log & experiment notebook
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
