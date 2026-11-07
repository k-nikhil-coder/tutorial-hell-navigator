import os
import sys
import json
import asyncio
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag import retrieve_relevant_chunks, format_retrieved_context
from app.client import generate_structured_response_async

# 30 Dev questions selected (25 technical + 5 out-of-scope)
SELECTED_DEV_QIDS = [
    # FastAPI (8 questions)
    "GS-V2-01", "GS-V2-02", "GS-V2-03", "GS-V2-04",
    "GS-V2-05", "GS-V2-06", "GS-V2-07", "GS-V2-08",
    # Docker (8 questions)
    "GS-V2-13", "GS-V2-14", "GS-V2-15", "GS-V2-16",
    "GS-V2-17", "GS-V2-18", "GS-V2-19", "GS-V2-20",
    # PostgreSQL (6 questions)
    "GS-V2-25", "GS-V2-26", "GS-V2-27", "GS-V2-28",
    "GS-V2-29", "GS-V2-30",
    # Pydantic (3 questions)
    "GS-V2-36", "GS-V2-37", "GS-V2-38",
    # Out-of-scope Refusal Controls (5 questions)
    "GS-V2-46", "GS-V2-47", "GS-V2-48", "GS-V2-49", "GS-V2-50",
]

async def generate_all_raw_pairs():
    with open(PROJECT_ROOT / "eval" / "gold_benchmark_v2.json", "r", encoding="utf-8") as f:
        gold_data = {q["id"]: q for q in json.load(f)}

    # Ensure none are in test split
    for qid in SELECTED_DEV_QIDS:
        q = gold_data[qid]
        assert q["split"] == "dev", f"ERROR: {qid} is in {q['split']} split, must be dev!"

    print(f"Generating fresh live model responses for {len(SELECTED_DEV_QIDS)} dev questions...")
    raw_pairs = []

    for idx, qid in enumerate(SELECTED_DEV_QIDS, 1):
        q_item = gold_data[qid]
        prompt = q_item["question"]
        topic = q_item.get("topic", "General")
        is_oos = q_item.get("answerability") == "not_answerable"

        # Hybrid-rerank retrieval against 10-file 97-chunk index
        chunks = retrieve_relevant_chunks(prompt, top_k=3, search_mode="hybrid-rerank")
        formatted_ctx = format_retrieved_context(chunks)

        print(f"[{idx:02d}/30] Calling Gemini for {qid} ({topic})...", end=" ", flush=True)
        try:
            resp = await generate_structured_response_async(
                user_query=prompt,
                search_mode="hybrid-rerank",
            )
            print("OK")
        except Exception as e:
            print(f"Failed: {e}")
            raise e

        # Store chunk metadata cleanly
        clean_chunks = []
        for c in chunks:
            clean_chunks.append({
                "chunk_id": c.get("chunk_id"),
                "source_file": c.get("source_file"),
                "text": c.get("text"),
                "score": round(float(c.get("score", 0.0)), 4),
            })

        # Convert NavigatorResponse to dict
        resp_dict = resp.model_dump()

        raw_pairs.append({
            "question_id": qid,
            "topic": topic,
            "question": prompt,
            "answerability": q_item.get("answerability"),
            "required_evidence": q_item.get("required_evidence", []),
            "retrieved_chunks": clean_chunks,
            "raw_response": resp_dict,
        })
        # Small sleep to be polite to API
        await asyncio.sleep(0.5)

    out_path = PROJECT_ROOT / "eval" / "raw_model_responses_d45.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(raw_pairs, f, indent=2)
    print(f"\nAll 30 fresh model responses generated and saved to {out_path}!")

if __name__ == "__main__":
    asyncio.run(generate_all_raw_pairs())
