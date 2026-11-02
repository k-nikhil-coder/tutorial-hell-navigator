"""
Tutorial Hell Navigator — Streamlit Chat Interface
Alternative frontend for Day 40 real user testing.

Run with:
    streamlit run frontend/app.py
"""

import os
import json
import httpx
import streamlit as st

API_BASE_URL = os.getenv("API_BASE_URL", "http://127.0.0.1:8000")

st.set_page_config(
    page_title="Tutorial Hell Navigator",
    page_icon="🧭",
    layout="centered",
    initial_sidebar_state="collapsed",
)

st.markdown(
    """
    <style>
    .main { background-color: #080a0f; color: #e2e8f0; }
    .stTextInput>div>div>input { background-color: #111520; color: #fff; border: 1px solid rgba(255,255,255,0.1); }
    .step-card { background-color: #171c2a; border-left: 3px solid #f0b429; padding: 10px 14px; border-radius: 4px; margin: 8px 0; }
    .anti-box { background-color: rgba(239,69,101,0.08); border: 1px solid rgba(239,69,101,0.3); border-radius: 4px; padding: 8px 12px; margin: 6px 0; color: #fca5a5; }
    .chunk-badge { font-family: monospace; font-size: 11px; background: #1e2436; color: #00f5d4; padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(255,255,255,0.1); margin-right: 4px; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("🧭 Tutorial Hell Navigator")
st.caption("Tier 1 Technical Mentor: FastAPI · Docker · Pydantic v2 · PostgreSQL")

# Session state initialization
if "messages" not in st.session_state:
    st.session_state.messages = []
if "feedback_submitted" not in st.session_state:
    st.session_state.feedback_submitted = {}

# Quick prompt chips
col1, col2, col3 = st.columns(3)
with col1:
    if st.button("⚡ CORS Wildcard Bug"):
        st.session_state.preset_query = "Why does FastAPI reject CORS wildcard allow_origins with allow_credentials=True?"
with col2:
    if st.button("🐘 psycopg2 Docker Crash"):
        st.session_state.preset_query = "Why does psycopg2 fail to build inside an Alpine python Dockerfile?"
with col3:
    if st.button("📦 Compose Readiness"):
        st.session_state.preset_query = "How do I make Docker Compose wait for Postgres to be healthy before starting FastAPI?"

# Render message history
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("citations"):
            st.markdown(
                "**Cited Chunks:** "
                + "".join([f'<span class="chunk-badge">{c}</span>' for c in msg["citations"]]),
                unsafe_allow_html=True,
            )

        # Feedback buttons for assistant responses
        if msg["role"] == "assistant":
            fb_key = f"fb_{idx}"
            if fb_key not in st.session_state.feedback_submitted:
                fb_col1, fb_col2, fb_col3 = st.columns([1, 1, 4])
                with fb_col1:
                    if st.button("👍 Helpful", key=f"up_{idx}"):
                        try:
                            httpx.post(
                                f"{API_BASE_URL}/api/feedback",
                                json={"query": msg.get("user_query", ""), "rating": "positive", "cited_chunk_ids": msg.get("citations", [])},
                                timeout=5.0,
                            )
                            st.session_state.feedback_submitted[fb_key] = "positive"
                            st.rerun()
                        except Exception as e:
                            st.warning(f"Feedback error: {e}")
                with fb_col2:
                    if st.button("👎 Needs Work", key=f"down_{idx}"):
                        try:
                            httpx.post(
                                f"{API_BASE_URL}/api/feedback",
                                json={"query": msg.get("user_query", ""), "rating": "negative", "cited_chunk_ids": msg.get("citations", [])},
                                timeout=5.0,
                            )
                            st.session_state.feedback_submitted[fb_key] = "negative"
                            st.rerun()
                        except Exception as e:
                            st.warning(f"Feedback error: {e}")
            else:
                rating = st.session_state.feedback_submitted[fb_key]
                st.caption(f"✓ Feedback recorded ({rating})")

# User chat input
preset = st.session_state.pop("preset_query", None)
user_input = st.chat_input("Describe your roadblock, error message, or architecture query...") or preset

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    with st.chat_message("assistant"):
        with st.spinner("Retrieving grounded context & analyzing..."):
            try:
                res = httpx.post(
                    f"{API_BASE_URL}/navigate",
                    json={"query": user_input},
                    timeout=30.0,
                )
                if res.status_code == 200:
                    data = res.json()
                    is_refusal = data.get("is_refusal", False)
                    summary = data.get("summary", "")
                    action_plan = data.get("action_plan", [])
                    anti_patterns = data.get("anti_patterns_to_avoid", [])
                    key_takeaway = data.get("key_takeaway")
                    cited_chunks = data.get("cited_chunk_ids", [])

                    content_lines = []
                    if is_refusal:
                        content_lines.append(f"🛑 **Out-of-Scope Query Refusal**\n\n{summary}")
                        if data.get("refusal_reason"):
                            content_lines.append(f"\n*Reason:* {data['refusal_reason']}")
                    else:
                        content_lines.append(summary + "\n")
                        if action_plan:
                            content_lines.append("### Recommended Action Plan:")
                            for s_idx, step in enumerate(action_plan, 1):
                                cmd = f"\n```bash\n{step['terminal_command']}\n```" if step.get("terminal_command") else ""
                                content_lines.append(f"**Step {s_idx}: {step['title']}**\n{step['description']}{cmd}")

                        if anti_patterns:
                            content_lines.append("\n### Anti-Patterns to Avoid:")
                            for ap in anti_patterns:
                                content_lines.append(f"- ⚠️ {ap}")

                        if key_takeaway:
                            content_lines.append(f"\n💡 **Key Takeaway:** {key_takeaway}")

                    full_content = "\n\n".join(content_lines)
                    st.markdown(full_content)

                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": full_content,
                        "citations": cited_chunks,
                        "user_query": user_input,
                    })
                    st.rerun()
                else:
                    st.error(f"Error {res.status_code}: {res.text}")
            except Exception as e:
                st.error(f"Failed to connect to backend: {e}")
