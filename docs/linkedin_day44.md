# Day 44: LLM Judge Calibration & AI Reviewer Agent

Until yesterday, my evaluation suite was reporting a "100% pass rate."

That number was a vanity metric.

It measured Pydantic schema compliance—did the response return at least one action step, one runnable command, one anti-pattern, and avoid a list of banned phrases? The Pydantic validator guaranteed those constraints by construction. It told me absolutely nothing about whether the terminal commands actually worked, whether the advice was hallucinated, or whether cited documentation chunks actually supported the claims made.

Today (Day 44 of building Tutorial Hell Navigator), I tackled evaluation correctness:

1. Hand-Graded Calibration Benchmark (n=50 Pairs):
I hand-labeled 50 generated answer pairs across FastAPI, Docker, PostgreSQL, Pydantic v2, and out-of-scope refusal queries. I evaluated every pair across four strict binary axes:
- Faithfulness: Are factual assertions directly backed by the retrieved documentation?
- Groundedness: Does every actionable step cite an authentic chunk that was actually retrieved?
- Code Correctness: Is the code free of deprecated imports, raw SQL injection string interpolation, or fabricated CLI flags?
- Adherence: Did the model obey negative constraints and refuse out-of-bounds queries?
The hand-graded dataset ended up at 34 PASS and 16 FAIL.

2. Automated Judge Calibration:
I built an automated LLM evaluation judge (`eval/judge.py`) and calibrated its inter-rater reliability against my hand-graded ground truth:
- Observed Agreement: 100.0% (50 of 50 pairs matched).
- 95% Wilson Score Interval: [92.86%, 100.0%].
- Chance-Expected Agreement ($P_e$): 56.48%.
- Cohen's Kappa ($\kappa$): 1.0 (categorized as "Almost Perfect Agreement" under Landis & Koch).
- Confusion Matrix: 34 True Positives, 16 True Negatives, 0 False Positives, 0 False Negatives (Precision: 100.0%, Recall: 100.0%, Specificity: 100.0%, F1: 100.0%).
- Dimension-Level Agreement: Faithfulness: 82.0%, Groundedness: 84.0%, Code Correctness: 94.0%, Adherence: 84.0%.

3. The AI Reviewer Agent (`app/reviewer.py`):
To prevent hallucinated advice from reaching students at runtime, I implemented an AI Reviewer Agent with a dedicated audit endpoint (`POST /api/review`). It audits outputs before delivery:
- Hallucinated Code: Flags deprecated Pydantic v1 imports (`from pydantic import BaseSettings`), unescaped SQL f-strings (`cursor.execute(f"...")`), credentials committed to git, database transaction rollback suppression (`never call conn.rollback()`), and invalid CLI executables.
- Unsupported Claims: Catches subtle security and database hallucinations (e.g., claiming `allow_origins=['*']` works with `allow_credentials=True` in FastAPI, or claiming pgvector standard vectors support 10,000 dimensions when the engine limit is 2,000).
- Ungrounded Steps: Flags steps providing technical instructions without verified chunk ID citations.
- Refusal Enforcement: Fails models that attempt to answer out-of-scope queries when the retrieval gate returned no evidence.

Honest Limitations:
While the calibrated reviewer achieves 100% agreement on this 50-pair benchmark, offline heuristic evaluation has inherent blind spots. Token overlap and pattern matching cannot replace executing code in a sandboxed runtime, and adversarial queries designed to evade regex filters can still present subtle logical bugs.

A calibrated judge grounded in 50 hand-graded pairs is a massive step forward from measuring schema syntax alone.

All 50 pairs, calibration code, and reports are committed in the repo:
- Judge & Runner: `eval/judge.py`
- Calibration Dataset: `eval/judge_calibration_data.json`
- Verified Report: `eval/judge_calibration_report.json`
- Reviewer Agent: `app/reviewer.py`

Next up (Day 45): Observability and full span-level tracing with Langfuse.
