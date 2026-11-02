# README.md vs eval/gold_set.json Question ID Audit & Mismatch Report

**Audit Date:** 2026-11-02  
**Constraint:** `README.md` was NOT edited during this audit.

---

## 1. Executive Summary

A comprehensive comparison between `README.md` and `eval/gold_set.json` was conducted to identify any question ID discrepancies, unindexed queries, or stale counts.

- **Total questions in `eval/gold_set.json`:** 392 questions (94 with ground-truth labels).
- **Explicit Question IDs in current `README.md`:** 0 explicit `GS-` IDs found in the current file text.
- **Explicit Question IDs in historical `README.md` (commits `c18be52` – `eb75aa5`):** 5 IDs (`GS-81`, `GS-83`, `GS-14`, `GS-15`, `GS-85`).
- **Queries presented in `README.md` prose:** 2 natural language queries without IDs ("How do I set up CORS in FastAPI?" and "How do I bake sourdough bread?").

---

## 2. Quantitative Claims Mismatch

| Item | Claim in `README.md` | Actual in `eval/gold_set.json` | Status / Discrepancy |
| :--- | :--- | :--- | :--- |
| **Total Gold Set Size** | "88 questions" (Lines 184, 282) | 392 questions | **MISMATCH:** `README.md` claims 88 total questions, but 304 questions were added in commit `8cf03d1`. |
| **Labeled Questions** | "n=23 labeled questions" (Line 184), "30 with labeled expected_chunk_ids" (Line 282) | 94 questions with `expected_chunk_ids` | **MISMATCH:** 94 questions in `gold_set.json` currently have `expected_chunk_ids` (23 tuned + 7 post-hoc + 15 sample/hard + 49 synthetic defaults). |
| **Held-Out Test Split** | "No held-out test split exists — all tuning and reporting use the same 23 questions" (Line 189) | `eval/split.json` was created (30% test split, 118 test questions) | **MISMATCH:** Prosaic text claims no split exists, though `eval/split.json` was introduced in Phase 1 (and subsequently voided in Status Correction). |

---

## 3. Detailed Question ID Comparison

### 3.1 Historical IDs Mentioned in Earlier README Versions
Prior to commit `429ca14`, the `README.md` featured a table titled *"Specific Keyword Trap Recoveries"* detailing 5 specific IDs:

1. **`GS-81`** (*FastAPI CORS wildcard credentials prohibition*)
   - Present in `gold_set.json`: **YES** (Category: "Hardened Retrieval: Exact-Keyword Trap (CORS Credentials)").
2. **`GS-83`** (*Pydantic `@field_validator('value', mode='before')`*)
   - Present in `gold_set.json`: **YES** (Category: "Hardened Retrieval: Exact-Keyword Trap (Pydantic Field Validator)").
3. **`GS-14`** (*Docker `psycopg2` compilation & `libpq-dev`*)
   - Present in `gold_set.json`: **YES** (Category: "Projects & independent building: micro-deliverables").
4. **`GS-15`** (*FastAPI relational CRUD & BackgroundTasks*)
   - Present in `gold_set.json`: **YES** (Category: "Projects & independent building: micro-deliverables").
5. **`GS-85`** (*Docker Compose CI caching (`--cache-from`)*)
   - Present in `gold_set.json`: **YES** (Category: "Hardened Retrieval: Multi-Hop Synthesis (Docker Compose & C-Extensions)").

### 3.2 Prose Queries in Current `README.md`
Current `README.md` includes two raw user query examples in text blocks:
1. `"How do I set up CORS in FastAPI?"` (Line 154)
   - Matches intent of `GS-07` ("I have a frontend and a backend running on different ports...") and `GS-81`.
   - Explicit ID omitted in `README.md`.
2. `"How do I bake sourdough bread?"` (Line 93)
   - Used as an illustrative example of an out-of-domain query bypassing the refusal gate.
   - Not indexed in `eval/gold_set.json` (untracked off-topic query).

### 3.3 Question IDs in `eval/gold_set.json` Missing from `README.md`
All 392 question IDs in `eval/gold_set.json` are absent by ID from current `README.md`:
- **Core Evaluation Subset (`GS-01` to `GS-88`):** 88 questions missing from `README.md`.
- **Domain Synthesis Subset (`GS-D1-01` to `GS-D5-02`):** 13 questions missing from `README.md`.
- **Extra Queries Subset (`GS-EXTRA-001` to `GS-EXTRA-080`):** 80 questions missing from `README.md`.
- **Knowledge/Theory Subset (`GS-K1-01` to `GS-K7-07`):** 49 questions missing from `README.md`.
- **Expanded Corpus Subset (`GS-X1-BOT-01` to `GS-X5-20`):** 162 questions missing from `README.md`.

---

## 4. Conclusion
`README.md` was rewritten during Phase 0 to eliminate inflated marketing claims and specific recovery tables, replacing them with generic metric summaries. As a result:
- No question IDs are cited in current `README.md`.
- The aggregate question counts in `README.md` (`n=23`, `88 total`, `30 labeled`) are stale and diverge from `eval/gold_set.json` (392 total, 94 labeled).
