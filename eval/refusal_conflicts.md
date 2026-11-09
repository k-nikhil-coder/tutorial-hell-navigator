# Refusal Conflicts Analysis: Lane A vs Lane B Expansion

**Date:** Day 47  
**Branch:** `feat/python-data-corpus`  
**Purpose:** Audit existing refusal and out-of-scope benchmark questions across `eval/` to identify semantic and evaluation conflicts introduced by Lane B's scope expansion (Tier 5 Python Basics, Tier 6 NumPy, Tier 7 pandas).

---

## 1. Background & Conflict Mechanism

- **Lane A Baseline (`main`):** Scope is strictly frozen to Tier 1 (FastAPI, Docker, Pydantic v2, PostgreSQL). Any question addressing general Python syntax, runtime internals, data science libraries (NumPy, pandas), or machine learning is classified as `not_answerable` and must trigger a refusal (`is_refusal = True`).
- **Lane B Objective (`feat/python-data-corpus`):** Adds isolated collections for **T5 (Python Basics)**, **T6 (NumPy)**, and **T7 (pandas)**.
- **Evaluation Risk:** If benchmark questions marked as refusals in Lane A match documentation ingested in Lane B, an expanded system would attempt to ground and answer them, failing Lane A refusal evaluation gates if evaluated against a shared benchmark.

---

## 2. Identified Refusal & Out-of-Scope Conflicts

### Conflict 1: `GS-V2-65` (Split: `test`)
- **Question:** *"Explain how Python 3.12 handles Debian PEP 668 externally managed environment markers and sys.breakpointhook overriding."*
- **Current Topic:** `Python Runtime Internals`
- **Current Answerability:** `not_answerable` (Refusal)
- **Current Judge Criteria:** `"Must refuse answering non-T1 CPython runtime internals and PEP 668 OS packaging."`
- **Conflict Details:**
  - Lane A treats Debian PEP 668 (`EXTERNALLY-MANAGED` marker files in `python3.12`) and virtual environment creation as non-T1 runtime behavior, classifying `corpus/raw/python_debugging.md` as OUT of Tier 1.
  - Lane B introduces **T5 (Python Basics)**, which explicitly covers virtual environment setup, `venv`, pip isolation, and standard environment configuration.
  - If T5 includes environment debugging, `GS-V2-65` shifts from an out-of-scope refusal to an answerable or partially answerable question under T5.
- **Resolution Recommendation:**
  - **Do NOT edit `gold_benchmark_v2.json`.**
  - Lane B must maintain a separate evaluation benchmark (`gold_benchmark_v3_data.json`) that isolates Lane B questions from Lane A's frozen gates.

---

### Conflict 2: `GS-25` (Legacy `gold_set_v2.json` / `gold_set.json`, Split: `dev`)
- **Question:** *"I've learned basic Python, NumPy, pandas, and introductory machine learning. What should I build to move from notebooks to an end-to-end ML application?"*
- **Current Topic:** Project Architecture / Transition out of Tutorial Hell
- **Current Answerability:** `not_answerable` (Refusal / Out-of-Scope in Tier 1)
- **Current Judge Criteria:**
  - *"End-to-end scope: Data prep -> Model training -> Pipeline serialization -> FastAPI serving -> Docker container"*
  - *"Why standalone Jupyter notebooks are invisible to recruiters without API interfaces"*
- **Conflict Details:**
  - The student query explicitly cites **NumPy**, **pandas**, and **basic Python**.
  - In Lane A, the query is ungrounded because NumPy, pandas, and ML model training are absent from the Tier 1 corpus.
  - In Lane B, ingesting official NumPy and pandas documentation creates strong lexical and semantic hits for this query. The retriever may fetch NumPy/pandas chunks rather than identifying the career/ML architectural nature of the prompt.
- **Resolution Recommendation:**
  - Keep `GS-25` classified as refusal in Lane A.
  - In Lane B, ensure query categorization distinguishes library usage questions (T6/T7) from high-level project transition advice.

---

### Conflict 3: Pure Python Basics & Standard Data Structures
- **Observed Pattern:**
  - In Lane A, questions like *"How do I format an f-string?"*, *"How does list slicing work?"*, or *"Why did my dictionary raise a KeyError?"* are ungrounded and must refuse.
  - However, in Lane A dev questions (e.g. `GS-V2-29`, `GS-V2-30`, `GS-V2-38`), Python constructs appear inside database or validation queries (e.g. *"Why should developers never format SQL queries using Python f-strings?"* or *"How can a Python list be passed into a SQL query in psycopg2 using ANY?"*).
  - When Lane B indexes the official Python 3 tutorial (covering lists, dicts, tuples, slicing, and string formatting), retrieval routing must prevent generic Python chunks from diluting domain-specific database or validation chunks in Tier 1.
- **Resolution Recommendation:**
  - Use collection-level namespace filtering (`collection_name='python_data_chunks'` vs `collection_name='tutorial_navigator_chunks'`).
  - Lane B searches should never query the Lane A collection unless multi-collection routing is explicitly requested by the student.

---

## 3. Audit Summary & Action Items

| Refusal ID | Benchmark File | Split | Topic | Lane A Status | Lane B Potential Conflict | Action Taken |
|---|---|---|---|---|---|---|
| **GS-V2-65** | `eval/gold_benchmark_v2.json` | `test` | Python Runtime Internals | `not_answerable` | Direct conflict with T5 environment isolation / PEP 668 | **Listed here; benchmark file NOT edited.** |
| **GS-25** | `eval/gold_set_v2.json` | `dev` | ML Project Transition | `not_answerable` | Lexical overlap with NumPy, pandas, Jupyter | **Listed here; benchmark file NOT edited.** |
| **Generic Python** | Domain boundary | N/A | General Python Syntax | Unindexed (Refusal) | In scope under T5 | **Isolated in Lane B collection.** |

**Rule Compliance Check:**
- Zero edits made to `eval/gold_benchmark_v2.json`, `eval/gold_set.json`, or `eval/gold_set_v2.json`.
- Zero test split questions run or modified.
- All conflicts documented transparently for owner review.
