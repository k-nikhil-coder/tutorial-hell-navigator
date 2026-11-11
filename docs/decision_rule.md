# Phase 1 Decision Rule & Pre-Declared Test Protocol

**Status:** Active (Pre-Final Freeze Declaration, Day 49) — **Held-out test split is SPENT (`2026-11-11`, executed once on `capstone2-freeze` `16e4413`, no reruns)**  
**Scope:** Lane A (`main` branch, frozen 10-file / 97-chunk Tier 1 corpus)

---

## 1. Retrieval Architecture Decision Rule

We retain the **Hybrid-Rerank** retrieval pipeline (Dense Qdrant + Sparse BM25 + RRF + Cross-Encoder Reranker) instead of replacing it with full-context prompt stuffing if both conditions hold on the development benchmark:

1. **Quality Non-Inferiority on Dev:** Hybrid-Rerank quality is within **10 percentage points** of Full-Context on blind human evaluation (and the 95% paired confidence interval includes `0`).
2. **Per-Query Cost Advantage:** Hybrid-Rerank consumes fewer tokens (and lower per-query input cost) than stuffing the full corpus into prompt context.
3. **Re-Evaluation Trigger:** Revisit this architectural decision when the active corpus grows past **~100k tokens** (e.g., when adding Python, NumPy, and pandas in Lane B).

### Current Dev Observation & Caveats
- **Dev Blind Hand-Grading (n=40, single grader with AI-assisted draft notes):** Hybrid-Rerank scored **35/40 (87.5%)** vs. Full-Context **34/40 (85.0%)** (`+2.5` percentage points, 95% bootstrap CI `[-10.0%, +15.0%]`, McNemar exact $p = 1.0000$). The 95% confidence interval includes `0` and the lower bound sits at `-10.0` points, so dev performance shows no detectable difference within the 10-point tolerance.
- **Per-Query Prompt Cost:** Hybrid-Rerank averaged **2,235 prompt tokens/call** vs. **33,298 prompt tokens/call** for Full-Context (~14.9x reduction at standard uncached input rates).
- **Context Caching Status:** **Caching not evaluated.** Explicit and implicit Gemini context caching pricing has not been benchmarked for full-context vs. RAG on this corpus and remains an open comparison item.

---

## 2. Pre-Declared Held-Out Test Split Protocol (`--final`)

To preserve generalization integrity on the 25 held-out questions (`eval/gold_benchmark_v2.json`, `split == "test"`, verified against `eval/test_ids.sha256`):

1. **Pre-Final Code Freeze Tag:** Tag `capstone2-freeze` on the audited pre-final commit on `main` **before** executing `--final`.
2. **Evaluation Scope:** Run **`hybrid-rerank` only** on the held-out test split (`--split-set test --final -m hybrid-rerank`). Do **not** evaluate `full-context` on the held-out test split.
3. **Statistical Reporting:** Report all held-out test split proportions (retrieval Hit@3, Hit@5, Evidence Coverage@3, Refusal Rate, and LLM pass metrics) with **95% Wilson score confidence intervals**.
4. **Zero Post-Run Edits:** Do not modify application code, prompts, retrieval thresholds, corpus chunks, or benchmark labels after executing `--final`. Test results are recorded exclusively in a **docs-only commit** after the run completes.
5. **Quota / Transient Error Handling:** If Gemini API quota or rate-limit errors occur during `--final`, **retry the errored question IDs only** (never re-running already-succeeded questions to cherry-pick outputs) and log every retried question ID and retry count alongside the final report.
