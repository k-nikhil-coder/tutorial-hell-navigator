# Day 40: Real User Testing Protocol & Telemetry Guide

This guide describes how to run and document the **10 real-user test sessions** for Tutorial Hell Navigator (including watching at least 2 users live over screen-share), as required by Day 40 of the 100-Day AI Engineer sprint.

---

## 1. Running the System Locally

Start the FastAPI application:
```bash
# In tutorial-hell-navigator-main:
.\.venv\Scripts\uvicorn app.main:app --reload --port 8000
```

Open your browser to:
- **Chat UI:** [http://localhost:8000/](http://localhost:8000/) or [http://localhost:8000/chat](http://localhost:8000/chat)
- **Interactive Swagger Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **Live Logs & Feedback Modal:** Click **"📊 Logs & Evals"** in the top navigation bar of the UI.

Alternatively, to run the Streamlit frontend:
```bash
.\.venv\Scripts\streamlit run frontend/app.py
```

---

## 2. Testing Protocol (10 Users)

### Session Format
- **Total Participants:** 10 CS students or junior developers currently building or debugging web projects.
- **Live Screen Shares (Mandatory for $\ge 2$ users):**
  - Conduct a 15–30 minute screen-share session (Google Meet / Zoom).
  - Observe how the user formulates their prompt, whether they copy the suggested commands, and where they get confused.
  - Do not help them solve the prompt; observe whether the navigator's action plan enables unaided completion.

### Recommended 5 Test Scenarios (Tier 1 Scope)

1. **CORS Credential Roadblock (FastAPI):**
   - *User Prompt:* `"My React frontend gets a CORS error: 'Access-Control-Allow-Origin wildcard cannot be used with credentials'. How do I fix this in FastAPI?"`
   - *Expected Behavior:* Explains W3C credential specification; instructs user to replace wildcard with explicit origins (`http://localhost:3000`).
2. **psycopg2 Build Crash (Docker):**
   - *User Prompt:* `"pip install psycopg2-binary fails when building my Alpine Python Docker image. What packages are missing?"`
   - *Expected Behavior:* Identifies missing C-compiler and header dependencies (`gcc`, `musl-dev`, `libpq-dev`, `python3-dev`) or recommends `psycopg2-binary` / `psycopg[binary]`.
3. **Database Readiness Race Condition (Docker Compose):**
   - *User Prompt:* `"FastAPI crashes on boot inside docker-compose because Postgres isn't ready yet, even though I have depends_on: db."`
   - *Expected Behavior:* Explains that `depends_on` only waits for container start, not DB readiness; provides `condition: service_healthy` with a healthcheck `pg_isready`.
4. **Data Validation (Pydantic v2):**
   - *User Prompt:* `"How do I validate in Pydantic v2 that an end_date field is strictly greater than start_date?"`
   - *Expected Behavior:* Recommends `@model_validator(mode="after")` because field validators only see one field at a time.
5. **Out-of-Scope Refusal (Verification):**
   - *User Prompt:* `"How do I use dynamic programming to solve the LeetCode Trapping Rain Water problem?"`
   - *Expected Behavior:* Triggers `is_refusal = True`; politely states that algorithmic puzzle solving is out of scope and refocuses on web engineering.

---

## 3. Gathering User Feedback

On every response, ask the user to click:
- **👍 Helpful** if the diagnosis was accurate and the steps worked.
- **👎 Needs Work** if the steps were incomplete, generic, or failed.
- Enter an optional comment in the text box (e.g., *"Step 2 had a typo in the pip package name"* or *"The explanation of depends_on finally made sense"*).

---

## 4. Inspecting Telemetry & Feedback Logs

Feedback and query trajectories are recorded automatically into:
- `logs/feedback.jsonl`
- `logs/query_trajectories.jsonl`

To inspect recent feedback from the CLI:
```bash
python -c "from app.telemetry import get_recent_feedback; print(get_recent_feedback(10))"
```
Or via HTTP:
```bash
curl http://localhost:8000/api/feedback
```
