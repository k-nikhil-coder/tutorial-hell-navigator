import os
import json
import logging
import asyncio
from typing import AsyncGenerator, Optional, Any, Dict, List, Tuple
from dotenv import load_dotenv
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception
from google import genai
from google.genai import types, errors

from app.schemas import NavigatorResponse
from app.tools import AVAILABLE_TOOLS
from app.rag import (
    retrieve_relevant_chunks_async,
    format_retrieved_context,
)

load_dotenv()
logger = logging.getLogger(__name__)

PRIMARY_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-lite-latest")
FALLBACK_MODELS = list(dict.fromkeys([
    PRIMARY_MODEL,
    "gemini-flash-lite-latest",
    "gemini-3.5-flash-lite",
    "gemini-3.5-flash",
    "gemini-3.8-flash",
]))

MAX_CONCURRENT_REQUESTS = int(os.getenv("MAX_CONCURRENT_REQUESTS", "5"))
DEFAULT_CONCURRENCY_LIMIT = MAX_CONCURRENT_REQUESTS
GLOBAL_SEMAPHORE = asyncio.Semaphore(MAX_CONCURRENT_REQUESTS)

SYSTEM_PROMPT = (
    "You are Tutorial Hell Navigator, an eval-first technical mentor for computer science students. "
    "You must ground your guidance in the provided verified technical context when available. "
    "\n\nSTRICT CITATION & REFUSAL RULES:\n"
    "1. CITATIONS: In your action_plan, each ActionableStep MUST include the exact chunk_id (e.g. 'fastapi_fullstack_guide_chunk_2') in its 'citations' list for every technical claim made.\n"
    "2. OUT-OF-CORPUS REFUSAL: If the provided verified context is empty or does not contain information to answer the question, you MUST:\n"
    "   - Set is_refusal = True\n"
    "   - Set refusal_reason = 'Question is out-of-corpus and cannot be verified against the technical documentation.'\n"
    "   - State clearly in the summary that the question is outside the scope of the verified corpus.\n"
    "   - Provide 1 advisory step pointing to standard documentation resources rather than inventing commands.\n"
    "3. ACTIONABLE STEPS: When context is present, provide concrete terminal CLI commands, rationale, and verification checks.\n"
    "4. ANTI-PATTERNS: List specific pitfalls to avoid."
)


def get_genai_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("Missing GEMINI_API_KEY environment variable.")
    return genai.Client(api_key=api_key)


def is_transient_error(exc: BaseException) -> bool:
    if isinstance(exc, (errors.ServerError, httpx.RequestError)):
        return True
    if isinstance(exc, errors.ClientError) and exc.code == 429:
        return True
    msg = str(exc).lower()
    return any(term in msg for term in ["503", "unavailable", "resource_exhausted", "rate limit", "timeout"])


def clean_json_text(raw: str) -> str:
    text = raw.strip()
    if text.startswith("```json"):
        text = text.removeprefix("```json")
    elif text.startswith("```"):
        text = text.removeprefix("```")
    if text.endswith("```"):
        text = text.removesuffix("```")
    return text.strip()


async def _execute_chat_with_fallback(
    user_query: str,
    response_schema: Optional[Any] = None,
    response_mime_type: Optional[str] = None,
    temperature: float = 0.2,
) -> str:
    client = get_genai_client()
    last_err: Optional[Exception] = None

    for model_name in FALLBACK_MODELS:
        try:
            config_params: Dict[str, Any] = {
                "tools": AVAILABLE_TOOLS,
                "temperature": temperature,
                "system_instruction": SYSTEM_PROMPT,
            }
            if response_schema:
                config_params["response_schema"] = response_schema
            if response_mime_type:
                config_params["response_mime_type"] = response_mime_type

            chat = client.aio.chats.create(
                model=model_name,
                config=types.GenerateContentConfig(**config_params),
            )
            response = await chat.send_message(user_query)
            if response and response.text:
                return response.text
        except Exception as e:
            last_err = e
            logger.warning("Model %s failed: %s. Checking fallback...", model_name, e)
            if not is_transient_error(e) and "404" not in str(e):
                raise e

    if last_err:
        raise last_err
    raise RuntimeError("All candidate models failed to return a response.")


@retry(
    retry=retry_if_exception(is_transient_error),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    reraise=True,
)
async def generate_structured_response_async(
    user_query: str,
    semaphore: Optional[asyncio.Semaphore] = None,
    enable_rag: bool = True,
) -> NavigatorResponse:
    sem = semaphore or GLOBAL_SEMAPHORE
    async with sem:
        retrieved_chunks: List[Dict[str, Any]] = []

        if enable_rag:
            try:
                retrieved_chunks = await retrieve_relevant_chunks_async(user_query, top_k=3)
            except Exception as e:
                logger.warning("RAG retrieval failed (falling back to tools): %s", e)

        if retrieved_chunks:
            # Check if top score is below out-of-corpus threshold
            top_score = retrieved_chunks[0].get("score", 0.0)
            if top_score < 0.40:
                context_str = "[NO VERIFIED CORPUS FOUND FOR THIS TOPIC - OUT OF BOUNDS]"
            else:
                context_str = format_retrieved_context(retrieved_chunks)
            prompt = f"VERIFIED CONTEXT:\n{context_str}\n\nSTUDENT QUESTION:\n{user_query}"
        else:
            prompt = user_query

        raw_output = await _execute_chat_with_fallback(
            user_query=prompt,
            response_schema=NavigatorResponse,
            response_mime_type="application/json",
            temperature=0.1,
        )
        cleaned = clean_json_text(raw_output)
        resp_model = NavigatorResponse.model_validate_json(cleaned)

        # Aggregate citations across action steps
        all_citations = []
        for step in resp_model.action_plan:
            if step.citations:
                all_citations.extend(step.citations)
        resp_model.cited_chunk_ids = list(dict.fromkeys(all_citations))

        # Attach retrieved chunks for telemetry logging
        object.__setattr__(resp_model, "_retrieved_chunks", retrieved_chunks)

        return resp_model


def generate_structured_response(user_query: str) -> str:
    """Sync wrapper for legacy callers and sync benchmarks."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(
                lambda: asyncio.run(generate_structured_response_async(user_query))
            ).result()
            return result.model_dump_json()
    else:
        result = asyncio.run(generate_structured_response_async(user_query))
        return result.model_dump_json()


async def stream_response_sse(
    user_query: str,
    semaphore: Optional[asyncio.Semaphore] = None,
    enable_rag: bool = True,
) -> AsyncGenerator[str, None]:
    """Stream model output as Server-Sent Events."""
    sem = semaphore or GLOBAL_SEMAPHORE
    client = get_genai_client()

    async with sem:
        retrieved_chunks: List[Dict[str, Any]] = []
        if enable_rag:
            try:
                retrieved_chunks = await retrieve_relevant_chunks_async(user_query, top_k=3)
            except Exception as e:
                logger.warning("RAG retrieval failed during stream: %s", e)

        if retrieved_chunks and retrieved_chunks[0].get("score", 0.0) >= 0.40:
            context_str = format_retrieved_context(retrieved_chunks)
            prompt = f"VERIFIED CONTEXT:\n{context_str}\n\nSTUDENT QUESTION:\n{user_query}"
        else:
            prompt = user_query

        last_err: Optional[Exception] = None
        for model_name in FALLBACK_MODELS:
            try:
                chat = client.aio.chats.create(
                    model=model_name,
                    config=types.GenerateContentConfig(
                        tools=AVAILABLE_TOOLS,
                        temperature=0.2,
                        system_instruction=SYSTEM_PROMPT,
                    ),
                )
                stream = await chat.send_message_stream(prompt)
                async for chunk in stream:
                    if chunk.text:
                        yield f"data: {json.dumps({'text': chunk.text})}\n\n"
                yield "data: [DONE]\n\n"
                return
            except Exception as e:
                last_err = e
                logger.warning("Streaming failed on %s: %s", model_name, e)
                if not is_transient_error(e) and "404" not in str(e):
                    break

        err_msg = str(last_err) if last_err else "Failed to stream response"
        yield f"data: {json.dumps({'error': err_msg})}\n\n"
        yield "data: [DONE]\n\n"


async def generate_async_with_semaphore(semaphore: asyncio.Semaphore, query: str) -> str:
    response = await generate_structured_response_async(query, semaphore=semaphore)
    return response.model_dump_json()
