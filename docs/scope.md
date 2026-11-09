# Project Scope Specification: Tutorial Hell Navigator

This document defines the strict operational boundaries, corpus classification, and licensing requirements for the Tutorial Hell Navigator knowledge base and evaluation benchmark.

---

## 1. Scope Hierarchy & Technical Boundaries

Work across the project proceeds in strictly separated lanes:
- **Lane A (`main` branch):** Capstone 2 deliverable. The Tier 1 corpus is **frozen** at 10 files and 97 chunks. Lane A metrics and evaluation gates must never be altered by other lanes.
- **Lane B (`feat/python-data-corpus` branch):** Extends coverage to Python, NumPy, and pandas as an **isolated, separate collection**. Lane B must never change a Lane A number.

### Status Classifications

| Tier / Domain | Scope Classification | Status | Notes & Operational Boundaries |
|---|---|---|---|
| **Tier 1 (T1): Web Engineering Core** | FastAPI, Docker, Pydantic v2, PostgreSQL | **Covered now** | Frozen Capstone 2 corpus: 10 files, 97 chunks in `tutorial_navigator_chunks`. |
| **Tier 5 (T5): Python Basics** | Language fundamentals & standard library | **In scope, not yet covered** | Core Python 3 tutorial, data structures, control flow, functions, virtual environments, exception handling. |
| **Tier 6 (T6): NumPy** | Numerical computing & ndarrays | **In scope, not yet covered** | NumPy basics: ndarray creation, vectorization, indexing/slicing, shapes, and broadcasting. |
| **Tier 7 (T7): pandas** | Tabular data manipulation | **In scope, not yet covered** | Series & DataFrames, 10-min overview, indexing/selection (`.loc`/`.iloc`), missing data, groupby, merge/join. |
| **matplotlib** | Data visualization & plotting | **OWNER DECISION** | Under consideration. Owner must decide whether 2D plotting is admitted or creates scope dilution away from data manipulation. |
| **scikit-learn** | Machine learning modeling | **OWNER DECISION** | Under consideration. Borders Out-of-Scope Rule 1 (AI/ML). Owner must decide whether introductory tabular ML pipelines (e.g. regression/trees) are admitted. |
| **Jupyter** | Interactive notebook environments | **OWNER DECISION** | Under consideration. Environment/IDE tool. Owner must decide whether notebook kernel debugging and cell execution errors are admitted. |
| **AI/ML Engineering** | Deep Learning / LLMs / MLOps | **OUT OF SCOPE** | Permanent project restriction (PyTorch, TensorFlow, vLLM, Feast, GPU clustering, etc.). |
| **DSA / Competitive Programming** | LeetCode / Algorithms / Contests | **OUT OF SCOPE** | Permanent project restriction (dynamic programming, segment trees, graph proofs, etc.). |
| **Career / GitHub Aesthetics** | Salary advice, resume ATS, badges | **OUT OF SCOPE** | Permanent project restriction. |

---

## 2. Detailed Tier Specifications

### Tier 1 (T1) Core Web Scope (Covered now)
Questions within T1 address:
- FastAPI routing, middleware (e.g. CORS), request validation, background tasks, dependency injection, and HTTP status codes.
- Pydantic v2 data models, field/model validators, discriminated unions, schema serialization, and validation error formatting.
- PostgreSQL transactions, atomic operations, connection pooling, psycopg2/asyncpg drivers, parameterized queries, and schema migrations.
- Docker & Docker Compose multi-stage builds, runtime vs build-time dependencies, service readiness healthchecks, and volumes.

### Tier 5 (T5) Python Basics (In scope, not yet covered)
Questions within T5 address:
- Python 3 basic data types: integers, floats, booleans, strings, lists, dictionaries, tuples, sets.
- Control flow: `if`/`elif`/`else`, `for` loops, `while` loops, `break`/`continue`/`pass`, and pattern matching.
- Functions: arguments, default values, `*args`, `**kwargs`, return values, docstrings, and lambda expressions.
- Modules and packages: import syntax, module search path, and `__name__ == "__main__"`.
- Exception handling: `try`/`except`/`finally`/`else`, built-in exception hierarchy, raising exceptions, and context managers.
- Environment management: Python virtual environments (`venv`), dependency isolation, and Debian PEP 668 externally managed environment markers.

### Tier 6 (T6) NumPy (In scope, not yet covered)
Questions within T6 address:
- Array creation: `np.array`, `np.zeros`, `np.ones`, `np.arange`, `np.linspace`, and data types (`dtype`).
- Vectorization: element-wise operations, replacing loops with vectorized expressions, and performance implications.
- Indexing and slicing: 1D and multidimensional array slicing, boolean indexing, integer array indexing.
- Array shapes and manipulation: `reshape`, `flatten`, `ravel`, transposing, concatenating, and splitting.
- Broadcasting: broadcasting rules between compatible and incompatible shapes.

### Tier 7 (T7) pandas (In scope, not yet covered)
Questions within T7 address:
- Core data structures: `Series` (1D labeled arrays) and `DataFrame` (2D labeled tabular data).
- Data ingestion and export: reading and writing CSV, Parquet, and SQL sources.
- Indexing and selection: label-based indexing (`.loc`), position-based indexing (`.iloc`), and boolean masking.
- Missing data handling: detecting (`isna`, `notna`), dropping (`dropna`), and imputing (`fillna`) missing values.
- Groupby operations: split-apply-combine paradigm, aggregations (`agg`, `mean`, `sum`, `count`), transformations, and filtering.
- Merging and combining: `merge` (inner, outer, left, right), `join`, and `concat` across rows/columns.

---

## 3. Explicit Out-of-Scope Boundaries

The following domains are explicitly **OUT OF SCOPE** per project requirements. The system must not ingest corpus documents, create gold questions, or provide tutoring in these areas:

1. **AI/ML Engineering:** LLM fine-tuning, PyTorch/TensorFlow, model training pipelines, MLOps, vector database internals.
2. **DSA (Data Structures & Algorithms):** LeetCode / HackerRank problems, algorithm design (e.g., dynamic programming, graph traversal, daily temperatures, monotonic stacks), and time/space complexity analysis.
3. **Competitive Programming:** Contest-specific algorithmic optimizations, codeforces/codechef problem solving.
4. **Career Decisions:** Job offer negotiation, salary advice, company tier ranking, tech stack flame wars, and speculative industry advice.
5. **GitHub Portfolio & Resumes:** Resume reviews, LinkedIn profile formatting, GitHub README showcase aesthetics, and personal branding strategies.
6. **OS / DBMS / Networking Theory:** Abstract academic operating systems theory (scheduling algorithms, paging internals), DBMS theory (relational algebra, formal normal forms theory), and networking protocol theory (OSI 7-layer model proofs, TCP packet dissection), except where directly applied to debugging application network/database boundaries.

---

## 4. Licensing Policy & Removal of Pro Git

### Exclusion of Pro Git
- **Source:** *Pro Git* (by Scott Chacon and Ben Straub).
  - Book URL: `https://git-scm.com/book/en/v2` (HTTP 200, 2026-11-02).
- **License:** Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Unported (`CC BY-NC-SA 3.0`).
  - License URL: `https://creativecommons.org/licenses/by-nc-sa/3.0/` (HTTP 200, 2026-11-02).
- **Status:** **REMOVED / EXCLUDED FROM SCOPE**.
- **Rationale:** The `CC BY-NC-SA 3.0` license is non-permissive due to two incompatible clauses:
  1. *NonCommercial (NC):* Forbids commercial use, preventing any downstream commercial deployment or hosting of the system.
  2. *ShareAlike (SA):* Imposes viral copyleft terms requiring derivative works and benchmarks to be released under the same license.
- **Action:** No content, chapters, or excerpts from *Pro Git* may be added to `corpus/raw/`, ingested into vector stores, or used in evaluation benchmarks.

### Permissive Licensing Standard
All external documentation ingested into the corpus must carry permissive open-source licenses:
- **Python Software Foundation (PSF) License:** (e.g., Python documentation).
- **BSD 3-Clause License:** (e.g., NumPy, pandas documentation).
- **MIT License:** (e.g., FastAPI, Pydantic documentation).
- **Apache 2.0:** (e.g., Docker documentation).
- **BSD / PostgreSQL License:** (e.g., psycopg2 documentation).
- **Internal / Owner-Authored:** Explicitly created for this repository under the project's root license.

---

## 5. Corpus Raw Inventory & T1 Classification

All 13 files currently present in `corpus/raw/` are inventoried below. No files are deleted. Each file is classified as either **IN** or **OUT** of the T1 technical scope:

| # | File Name | T1 Status | Topic & Exact Sections / Pages | Source / Provenance | Verified URL & Status (Checked: 2026-11-02) |
|---|---|---|---|---|---|
| 1 | `cs_engineering_roadmap.pdf` | **OUT** | **CS Roadmap & Debugging Methodology**<br>- Page 1: Pathology of Tutorial Hell, 14-Day Scoped Milestones, What to Learn First vs Postpone.<br>- Page 2: 4-Step Failure Tree Isolation, Core CS Fundamentals: OS, DBMS & Networking. | Internal reference document | N/A (Internal PDF) |
| 2 | `docker_compose.md` | **IN** | **Docker Compose Mechanics**<br>- Volumes vs COPY in Multi-stage Builds (lines 3-35)<br>- depends_on and Service Readiness (lines 36-58)<br>- Build-time Dependencies (lines 59-68)<br>- Multi-stage Builds for Smaller Images (lines 69-92) | Internal technical guide | N/A (Internal Markdown) |
| 3 | `docker_compose_best_practices.md` | **IN** | **Official Docker Compose Overview**<br>- Key benefits of Docker Compose (lines 10-21)<br>- Common use cases: Development, Automated testing, Single host (lines 22-64)<br>- What's next? (lines 65-70) | Docker Documentation (Apache 2.0) | `https://raw.githubusercontent.com/docker/docs/main/content/manuals/compose/intro/features-uses.md` (HTTP 200, 2026-11-02)<br>Canonical: `https://docs.docker.com/compose/intro/features-uses/` (HTTP 200, 2026-11-02) |
| 4 | `docker_production_guide.md` | **IN** | **Production Dockerfile & Compose for Python/PostgreSQL**<br>- 1. Multi-Stage Dockerfile for Python Applications (lines 3-48)<br>- 2. Resolving the psycopg2 Docker Build Crash (lines 51-68)<br>- 3. Docker Compose Orchestration: Frontend, Backend & Database (lines 71-105)<br>- 4. Healthcheck & Database Connection Waiting (lines 107-118)<br>- 5. Production Environment Security & Secrets (lines 120-130) | Internal technical manual | N/A (Internal Markdown) |
| 5 | `fastapi_background_tasks.md` | **IN** | **FastAPI Background Tasks**<br>- Using BackgroundTasks (lines 8-21)<br>- Create a task function (lines 22-30)<br>- Add the background task (lines 31-48)<br>- Dependency Injection (lines 49-65)<br>- Technical Details & Caveats (lines 66-80)<br>- Recap (lines 81-86) | FastAPI Official Tutorial (MIT) | `https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/background-tasks.md` (HTTP 200, 2026-11-02)<br>Canonical: `https://fastapi.tiangolo.com/tutorial/background-tasks/` (HTTP 200, 2026-11-02) |
| 6 | `fastapi_cors.md` | **IN** | **FastAPI CORS Configuration**<br>- Origin & Steps (lines 8-33)<br>- Wildcards & CORSMiddleware (lines 34-75)<br>- Preflight & Simple requests (lines 76-84)<br>- More info (lines 85-89) | FastAPI Official Tutorial (MIT) | `https://raw.githubusercontent.com/fastapi/fastapi/master/docs/en/docs/tutorial/cors.md` (HTTP 200, 2026-11-02)<br>Canonical: `https://fastapi.tiangolo.com/tutorial/cors/` (HTTP 200, 2026-11-02) |
| 7 | `fastapi_fullstack_guide.md` | **IN** | **Full-Stack Architecture Blueprint**<br>- 1. Learning Path from Static Web to Full-Stack (lines 3-27)<br>- 2. Stack Comparison: React + Node vs React + FastAPI (lines 30-43)<br>- 3. Frontend-Backend Communication & CORS (lines 45-92)<br>- 4. Connecting Web Apps to PostgreSQL (lines 94-118)<br>- 5. Docker Compose Fullstack Setup (lines 120-134) | Internal technical guide | N/A (Internal Markdown) |
| 8 | `fastapi_validation.md` | **IN** | **FastAPI Request Validation & Pydantic v2**<br>- Request Validation Errors & Custom Handlers (lines 3-52)<br>- Pydantic v2 Field Validators (lines 53-74)<br>- Discriminated Unions (lines 75-98)<br>- Raising Validation Errors from Custom Validators (lines 99-126) | Internal technical guide | N/A (Internal Markdown) |
| 9 | `git_reference.md` | **OUT** | **Git Operations and Pitfalls**<br>- Removing a Secret from History (lines 3-23)<br>- Aborting a Rebase (lines 24-41)<br>- Local Configuration Files (lines 42-54)<br>- Merge vs Rebase on Shared Branches (lines 55-60)<br>- Restoring a Single File from an Earlier Commit (lines 61-70) | Internal technical notes | N/A (Internal Markdown; Git excluded from T1) |
| 10 | `postgresql_psycopg2.md` | **IN** | **PostgreSQL & psycopg2 Mechanics**<br>- Transactions and Atomic Multi-table Inserts (lines 3-45)<br>- InFailedSqlTransaction recovery (lines 46-63)<br>- Parameterized Queries and IN Lists (lines 64-87)<br>- Connection Pooling Notes (lines 88-95) | Internal technical guide | Canonical: `https://www.psycopg.org/docs/` (HTTP 200, 2026-11-02) |
| 11 | `pydantic_models.md` | **IN** | **Official Pydantic v2 Models**<br>- Basic model usage (lines 3-47)<br>- Model methods and properties (lines 48-124)<br>- Data conversion (lines 125-220)<br>- Extra data & fields (lines 221-310)<br>- Nested models & Cyclic references (lines 311-450)<br>- Dynamic model creation & Generics (lines 451-1852) | Pydantic Official Docs (MIT) | `https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/models.md` (HTTP 200, 2026-11-02)<br>Canonical: `https://docs.pydantic.dev/latest/concepts/models/` (HTTP 200, 2026-11-02) |
| 12 | `pydantic_validation.md` | **IN** | **Official Pydantic v2 Validators**<br>- Field validators: annotated & decorator patterns (lines 1-150)<br>- Model validators: before & after (lines 151-380)<br>- Raising validation errors (lines 381-550)<br>- Validation info & context (lines 551-919) | Pydantic Official Docs (MIT) | `https://raw.githubusercontent.com/pydantic/pydantic/main/docs/concepts/validators.md` (HTTP 200, 2026-11-02)<br>Canonical: `https://docs.pydantic.dev/latest/concepts/validators/` (HTTP 200, 2026-11-02) |
| 13 | `python_debugging.md` | **OUT** | **Python Runtime & Environment Debugging**<br>- ModuleNotFoundError interpreter mismatch (lines 3-26)<br>- Logging Format KeyError (lines 27-46)<br>- Virtual Environment Activation & Debian Externally Managed Environments (lines 47-64)<br>- Reading Tracebacks & pdb (lines 65-87) | Internal technical notes | N/A (Internal Markdown; general Python runtime out of T1) |

---

## 6. Scope Audit Summary

- **Total Raw Corpus Files (Lane A):** 13
- **Classified as IN T1 (10 files):** `docker_compose.md`, `docker_compose_best_practices.md`, `docker_production_guide.md`, `fastapi_background_tasks.md`, `fastapi_cors.md`, `fastapi_fullstack_guide.md`, `fastapi_validation.md`, `postgresql_psycopg2.md`, `pydantic_models.md`, `pydantic_validation.md`.
- **Classified as OUT of T1 (3 files):** `cs_engineering_roadmap.pdf`, `git_reference.md`, `python_debugging.md` (plus all external Git / Pro Git book materials).
- **Pro Git Book Status:** Strictly excluded and removed due to non-permissive CC BY-NC-SA 3.0 license.
- **Lane B Separation Principle:** New collections for Python, NumPy, and pandas created under Lane B reside in independent collections and manifests. No Lane A benchmark or gate is impacted.
