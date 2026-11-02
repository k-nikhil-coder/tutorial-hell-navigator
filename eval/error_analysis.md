# Retrieval Error Analysis Report

**Source Report:** `eval\hybrid_rerank_retrieval_report.json`  
**Top-K Evaluated:** $K=3$  
**Total Misses:** 8  

## Cause Breakdown

- **retrieval failure:** 1 (12.5%)
- **wrong label:** 4 (50.0%)
- **valid alternative:** 2 (25.0%)
- **missing chunk:** 1 (12.5%)

## Key Qualitative Findings

1. **Label Inaccuracies (50.0%):** 4 of the 8 misses were ground-truth labeling errors where the retrieval pipeline actually fetched the correct or closest chunk, but the legacy label pointed elsewhere (e.g. GS-06 retrieved rank 2, GS-11 retrieved rank 1, GS-14 retrieved rank 1, GS-15 retrieved rank 2).
2. **Valid Alternatives / Chunk Overlap (25.0%):** In 2 cases (GS-12, GS-88), retrieved chunks provided identical or superior coverage compared to the single hardcoded chunk ID due to overlapping chunk boundaries.
3. **Genuine Retrieval Failure (12.5%):** Only 1 miss (GS-04) was a genuine retrieval failure where top-3 returned nested copies of one region while the answer in Section 4 was missed.
4. **Missing Corpus Chunk / Out of Scope (12.5%):** GS-13 asks for project ideation/portfolio advice, which is unanswerable by technical documentation and explicitly out of Tier 1 scope.

## Detailed Error Log

| Question ID | Question | Expected Chunk(s) | Retrieved Top Chunks | Assigned Cause | Evidence Notes | Human Confirmed |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **GS-04** | I know basic JavaScript but have never used a database. Teac... | `fastapi_fullstack_guide_chunk_1, docker_production_guide_chunk_0` | `fastapi_fullstack_guide_chunk_3, fastapi_fullstack_guide_chunk_0, fastapi_fullstack_guide_chunk_2` | **retrieval failure** | PROPOSED, owner must confirm. Real miss. Label is half wrong (drop the Docker chunk). The three retrieved chunks are nested copies of one 4k-char region, so top-3 held one region. The answer chunk, section 4, was not retrieved. | `True` |
| **GS-06** | How do login, signup, sessions, cookies, and JWTs actually w... | `docker_production_guide_chunk_0, docker_production_guide_chunk_1` | `fastapi_fullstack_guide_chunk_3, fastapi_fullstack_guide_chunk_1, fastapi_fullstack_guide_chunk_0` | **wrong label** | PROPOSED, owner must confirm. Retrieval was right (rank 2). Correct label: fastapi_fullstack_guide_chunk_1. | `True` |
| **GS-11** | I can follow coding tutorials but freeze when starting from ... | `docker_compose_best_practices_chunk_0, docker_production_guide_chunk_1` | `cs_engineering_roadmap_chunk_0, fastapi_background_tasks_chunk_1, cs_engineering_roadmap_chunk_1` | **wrong label** | PROPOSED, owner must confirm. Retrieval was right (rank 1). Correct label: cs_engineering_roadmap_chunk_0. Also: this question is about the owner-authored roadmap doc, so it is circular, and it is out of scope under the Docker/FastAPI/Pydantic/PostgreSQL T1. | `True` |
| **GS-12** | I keep abandoning projects because I add too many features. ... | `cs_engineering_roadmap_chunk_1` | `cs_engineering_roadmap_chunk_0, fastapi_fullstack_guide_chunk_0, fastapi_fullstack_guide_chunk_1` | **valid alternative** | PROPOSED, owner must confirm. The miss comes from overlapping chunks: chunk_0 contains all of chunk_1's text. An ID label scores this as a miss. Neither chunk teaches feature scoping, so the corpus only partly answers it. Out of scope under T1. | `True` |
| **GS-13** | Every beginner builds a weather app or to-do list. How can I... | `fastapi_fullstack_guide_chunk_0` | `fastapi_fullstack_guide_chunk_1, fastapi_fullstack_guide_chunk_2, cs_engineering_roadmap_chunk_0` | **missing chunk** | PROPOSED, owner must confirm. No chunk in the corpus answers this. Project ideation and portfolio differentiation are out of scope under T1. Retire the question. | `True` |
| **GS-14** | I repeatedly start tutorials and quit halfway. Give me a sev... | `docker_production_guide_chunk_0, docker_production_guide_chunk_1` | `cs_engineering_roadmap_chunk_0, fastapi_fullstack_guide_chunk_1, fastapi_fullstack_guide_chunk_0` | **wrong label** | PROPOSED, owner must confirm. Retrieval found the closest chunk (rank 1). Correct label: cs_engineering_roadmap_chunk_0. The corpus cannot fully answer the question as written (7 days, time limit, definition of done). Out of scope under T1. | `True` |
| **GS-15** | I get stuck for hours whenever my project throws an unfamili... | `fastapi_fullstack_guide_chunk_1` | `cs_engineering_roadmap_chunk_1, cs_engineering_roadmap_chunk_0, pydantic_validation_chunk_9` | **wrong label** | PROPOSED, owner must confirm. Retrieval was right (rank 2). Correct label: cs_engineering_roadmap_chunk_0. Retrieved chunk 3 (a Pydantic plain-validator snippet) is irrelevant. | `True` |
| **GS-88** | How do you sanitize and validate incoming request payloads i... | `pydantic_validation_chunk_14, fastapi_fullstack_guide_chunk_0` | `pydantic_validation_chunk_0, pydantic_validation_chunk_4, pydantic_models_chunk_10` | **valid alternative** | PROPOSED, owner must confirm. Retrieved chunks cover the before-validator half at least as well as the expected chunk. The FastAPI-dependency half has no chunk, so the question is multi-hop with a corpus gap. In the Nov 1 baseline run the pipeline REFUSED this question, so check the refusal gate too. | `True` |
