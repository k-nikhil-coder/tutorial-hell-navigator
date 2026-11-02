# Project Scope Specification: Tutorial Hell Navigator

This document defines the strict operational boundaries, corpus classification, and licensing requirements for the Tutorial Hell Navigator knowledge base and evaluation benchmark.

---

## 1. Tier 1 (T1) Core Scope

**Tier 1 (T1)** is specifically defined as:
> **FastAPI, Docker, Pydantic, and PostgreSQL full-stack web engineering.**

The system is designed to provide actionable, citation-backed technical guidance for students building full-stack Python web applications with FastAPI, Pydantic v2 data models, PostgreSQL relational persistence, and Docker / Docker Compose container orchestration.

Questions within T1 address:
- FastAPI routing, middleware (e.g. CORS), request validation, background tasks, dependency injection, and HTTP status codes.
- Pydantic v2 data models, field/model validators, discriminated unions, schema serialization, and validation error formatting.
- PostgreSQL transactions, atomic operations, connection pooling, psycopg2/asyncpg drivers, parameterized queries, and schema migrations.
- Docker & Docker Compose multi-stage builds, runtime vs build-time dependencies, service readiness healthchecks, and volumes.

---

## 2. Out of Scope

The following domains are explicitly **OUT OF SCOPE** per project requirements. The system must not ingest corpus documents, create gold questions, or provide tutoring in these areas:

1. **AI/ML Engineering:** LLM fine-tuning, PyTorch/TensorFlow, model training pipelines, MLOps, vector database internals.
2. **DSA (Data Structures & Algorithms):** LeetCode / HackerRank problems, algorithm design (e.g., dynamic programming, graph traversal, daily temperatures, monotonic stacks), and time/space complexity analysis.
3. **Competitive Programming:** Contest-specific algorithmic optimizations, codeforces/codechef problem solving.
4. **Career Decisions:** Job offer negotiation, salary advice, company tier ranking, tech stack flame wars, and speculative industry advice.
5. **GitHub Portfolio & Resumes:** Resume reviews, LinkedIn profile formatting, GitHub README showcase aesthetics, and personal branding strategies.
6. **OS / DBMS / Networking Theory:** Abstract academic operating systems theory (scheduling algorithms, paging internals), DBMS theory (relational algebra, formal normal forms theory), and networking protocol theory (OSI 7-layer model proofs, TCP packet dissection), except where directly applied to debugging application network/database boundaries.

---

## 3. Licensing Policy & Removal of Pro Git

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
- **MIT License:** (e.g., FastAPI, Pydantic documentation).
- **Apache 2.0:** (e.g., Docker documentation).
- **BSD / PostgreSQL License:** (e.g., psycopg2 documentation).
- **Internal / Owner-Authored:** Explicitly created for this repository under the project's root license.

---

## 4. Corpus Raw Inventory & T1 Classification

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

## 5. Scope Audit Summary

- **Total Raw Corpus Files:** 13
- **Classified as IN T1 (10 files):** `docker_compose.md`, `docker_compose_best_practices.md`, `docker_production_guide.md`, `fastapi_background_tasks.md`, `fastapi_cors.md`, `fastapi_fullstack_guide.md`, `fastapi_validation.md`, `postgresql_psycopg2.md`, `pydantic_models.md`, `pydantic_validation.md`.
- **Classified as OUT of T1 (3 files):** `cs_engineering_roadmap.pdf`, `git_reference.md`, `python_debugging.md` (plus all external Git / Pro Git book materials).
- **Pro Git Book Status:** Strictly excluded and removed due to non-permissive CC BY-NC-SA 3.0 license.
- **HTTP Verification:** All remote source URLs were tested via live HTTP requests on 2026-11-02; all canonical documentation links returned `HTTP 200`. No fabricated or dead links are present.
