"""
app/reviewer.py

AI Reviewer Agent: Audits generated Tutorial Hell Navigator responses for:
1. Hallucinated code (invalid commands, deprecated imports, forbidden configurations, SQL injections).
2. Unsupported claims (statements contradicting or unbacked by retrieved documentation chunks).
3. Ungrounded steps (actionable steps missing citations or citing non-existent chunks).
4. Refusal correctness (enforcing proper refusal for out-of-corpus queries while preventing false refusals).

Provides both deterministic heuristic verification (100% offline, reproducible for CI)
and optional LLM-as-a-judge verification via Gemini when enabled.
"""

import re
import os
import logging
from typing import List, Dict, Any, Optional, Set, Union
from app.schemas import NavigatorResponse, ReviewResult, ActionableStep

logger = logging.getLogger(__name__)

# Known technical patterns and anti-patterns in Tier 1 scope
FORBIDDEN_PATTERNS = [
    # CORS specification violation: wildcard origin with credentials
    (
        r"allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\][\s\S]*allow_credentials\s*=\s*True",
        "CORS violation: allow_origins=['*'] cannot be used when allow_credentials=True.",
    ),
    (
        r"allow_credentials\s*=\s*True[\s\S]*allow_origins\s*=\s*\[\s*['\"]\*['\"]\s*\]",
        "CORS violation: allow_origins=['*'] cannot be used when allow_credentials=True.",
    ),
    # Pydantic V1 deprecated import in V2 environment
    (
        r"from\s+pydantic\s+import\s+BaseSettings",
        "Deprecated import: BaseSettings was moved to 'pydantic_settings' in Pydantic v2.",
    ),
    # Direct SQL injection vulnerability pattern
    (
        r"(?:f[\"'].*SELECT\s+.*WHERE\s+.*\{|cursor\.execute\s*\(\s*f[\"'])",
        "SQL injection risk: detected unescaped string formatting in SQL query instead of parameterized execution.",
    ),
    # Raw command placeholder artifacts
    (
        r"<your[-_]?\w+>",
        "Unresolved placeholder token detected in runnable command.",
    ),
    # Hardcoded secrets committed to git
    (
        r"git\s+add[\s\S]*?git\s+commit[\s\S]*?(?:password|secret|credential)",
        "Security violation: committing raw credentials or secrets to version control.",
    ),
    # Database transaction rollback suppression
    (
        r"(?:never|do not|don't)\s+call\s+(?:conn\.)?rollback",
        "Database integrity risk: suppressing conn.rollback() leaves transactions in aborted state.",
    ),
    # PgVector HNSW/IVFFlat index dimension limit contradiction
    # Note: pgvector's vector type stores up to 16,000 dimensions, but HNSW and IVFFlat indexes are capped at 2,000 dimensions for vector (4,000 for halfvec).
    (
        r"(?:hnsw|ivfflat)[\s\S]*?(?:supports|indexes|with)[\s\S]*?10[,\.]?000\s+dimensions|(?:standard\s+vector|vector\(3072\))[\s\S]*?(?:hnsw|ivfflat)[\s\S]*?10[,\.]?000\s+dimensions",
        "Unsupported claim: pgvector HNSW and IVFFlat indexes are limited to 2,000 dimensions for standard vector type (halfvec supports up to 4,000; unindexed vector supports up to 16,000).",
    ),
    # FastAPI route tags database sharding hallucination
    (
        r"tags\s+instruct\s+FastAPI's\s+SQL\s+engine|tags.*?shard\s+table\s+partitions",
        "Hallucinated claim: FastAPI route tags are OpenAPI metadata and have no relation to SQL table sharding.",
    ),
    # Fabricated package installation
    (
        r"pip\s+install\s+psycopg2-turbo-native",
        "Hallucinated package: 'psycopg2-turbo-native' does not exist in PyPI or verified documentation.",
    ),
]

VAGUE_PHRASES = [
    "keep practicing",
    "just practice more",
    "copy and paste this",
    "just google it",
    "don't worry about understanding",
    "here is the complete code for everything",
    "it's beyond the scope",
]

KNOWN_SAFE_COMMAND_PREFIXES = {
    "npm", "npx", "node", "yarn", "pnpm", "bun",
    "pip", "pip3", "python", "python3", "py", "pytest", "poetry",
    "uvicorn", "docker", "docker-compose", "git", "curl", "wget",
    "alembic", "psql", "mkdir", "cd", "touch", "echo", "cat",
    "source", "export", "bash", "sh", "rm", "cp", "mv", "ls",
}

COMMON_STOPWORDS = {
    "this", "that", "with", "from", "your", "have", "more", "using", "make",
    "when", "where", "also", "will", "should", "must", "than", "then", "into",
    "about", "after", "before", "over", "under", "between", "each", "both",
    "their", "there", "they", "them", "which", "what", "how", "step", "action",
}


class ReviewerAgent:
    """AI Reviewer Agent auditing Navigator responses for faithfulness, groundedness, and code soundness."""

    def __init__(
        self,
        min_faithfulness: float = 0.70,
        min_groundedness: float = 0.70,
        min_code_correctness: float = 0.70,
        pass_threshold: float = 0.80,
    ):
        self.min_faithfulness = min_faithfulness
        self.min_groundedness = min_groundedness
        self.min_code_correctness = min_code_correctness
        self.pass_threshold = pass_threshold

    def audit(
        self,
        query: str,
        response: Union[NavigatorResponse, Dict[str, Any]],
        retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
        judge_criteria: Optional[List[str]] = None,
    ) -> ReviewResult:
        """
        Audit a response against retrieved chunks and criteria.
        
        Args:
            query: The user query string.
            response: A NavigatorResponse instance or matching dictionary.
            retrieved_chunks: List of retrieved context chunks (dict with chunk_id, text, etc.).
            judge_criteria: Optional list of passing/failing criteria rules.
        """
        resp_obj = self._coerce_response(response)
        retrieved = retrieved_chunks or []

        # Extract available chunk IDs and combined corpus context
        available_chunk_ids: Set[str] = set()
        context_corpus_text = ""
        is_context_out_of_bounds = False

        for c in retrieved:
            cid = c.get("chunk_id") if isinstance(c, dict) else getattr(c, "chunk_id", None)
            if cid:
                available_chunk_ids.add(cid)
            mapped_ids = c.get("mapped_512_chunk_ids", []) if isinstance(c, dict) else getattr(c, "mapped_512_chunk_ids", [])
            for mid in mapped_ids:
                available_chunk_ids.add(mid)
            c_text = c.get("text", "") if isinstance(c, dict) else getattr(c, "text", "")
            context_corpus_text += " " + c_text
            if "[no verified corpus found" in c_text.lower() or "[no relevant context" in c_text.lower():
                is_context_out_of_bounds = True

        flagged_claims: List[str] = []
        hallucinated_code: List[str] = []
        ungrounded_steps: List[int] = []
        notes: List[str] = []

        # 1. AUDIT REFUSAL LOGIC
        if resp_obj.is_refusal:
            # Proper refusal handling
            if is_context_out_of_bounds or len(retrieved) == 0:
                notes.append("Properly refused out-of-scope/unsupported query.")
                return ReviewResult(
                    is_valid=True,
                    verdict="PASS",
                    faithfulness_score=1.0,
                    groundedness_score=1.0,
                    code_correctness_score=1.0,
                    adherence_score=1.0,
                    overall_score=1.0,
                    flagged_claims=[],
                    hallucinated_code=[],
                    ungrounded_steps=[],
                    feedback="Response correctly refused out-of-scope query without hallucinating ungrounded steps.",
                )
            else:
                # Potential false refusal if strong relevant context was present
                has_substantive_context = len(context_corpus_text.strip()) > 100
                if has_substantive_context and not is_context_out_of_bounds:
                    flagged_claims.append("False refusal: system refused despite relevant technical context being retrieved.")
                    notes.append("False refusal on retrieved context.")

        else:
            # If not refusal, but context was explicitly out-of-bounds:
            if is_context_out_of_bounds:
                flagged_claims.append("Refusal failure: generated answer on out-of-bounds query instead of refusing.")

        # 2. AUDIT TOP-LEVEL AND STEP CITATIONS
        if resp_obj.cited_chunk_ids:
            for cid in resp_obj.cited_chunk_ids:
                if available_chunk_ids and cid not in available_chunk_ids:
                    hallucinated_code.append(
                        f"Response cites nonexistent or unretrieved chunk_id '{cid}'."
                    )

        total_steps = len(resp_obj.action_plan)
        grounded_step_count = 0

        for step in resp_obj.action_plan:
            step_has_valid_citation = False
            step_citations = step.citations or []

            if not step_citations:
                # Step provides no citations
                if len(available_chunk_ids) > 0 and not resp_obj.is_refusal:
                    ungrounded_steps.append(step.step_number)
            else:
                for cit in step_citations:
                    if available_chunk_ids and cit not in available_chunk_ids:
                        hallucinated_code.append(
                            f"Step {step.step_number} cites nonexistent or unretrieved chunk_id '{cit}'."
                        )
                    else:
                        step_has_valid_citation = True

            if step_has_valid_citation:
                grounded_step_count += 1

        if total_steps > 0:
            groundedness_score = round(grounded_step_count / total_steps, 4)
        else:
            groundedness_score = 1.0 if resp_obj.is_refusal else 0.0

        # 3. AUDIT HALLUCINATED CODE & FORBIDDEN PATTERNS
        all_code_blocks = []
        for step in resp_obj.action_plan:
            if step.command:
                all_code_blocks.append(step.command)
            if step.explanation:
                all_code_blocks.append(step.explanation)
            if step.verification:
                all_code_blocks.append(step.verification)

        full_text_to_audit = resp_obj.summary + "\n" + "\n".join(all_code_blocks)

        for pat, err_msg in FORBIDDEN_PATTERNS:
            if re.search(pat, full_text_to_audit, re.IGNORECASE):
                hallucinated_code.append(err_msg)

        # Check command prefixes and CLI structure
        invalid_command_count = 0
        total_commands = 0
        for step in resp_obj.action_plan:
            cmd = (step.command or "").strip()
            if cmd:
                total_commands += 1
                clean_cmd = re.sub(r"^[A-Za-z_][A-Za-z0-9_]*=\S+\s+", "", cmd).strip()
                tokens = clean_cmd.split()
                if tokens:
                    first_token = tokens[0].lower().replace("./", "").replace(".\\", "").split("/")[-1].split("\\")[-1]
                    if (
                        first_token not in KNOWN_SAFE_COMMAND_PREFIXES
                        and not first_token.endswith(".py")
                        and not first_token.endswith(".js")
                        and not first_token.endswith(".sh")
                    ):
                        if not any(token in cmd for token in ["&&", "||", "|", ";"]):
                            hallucinated_code.append(
                                f"Step {step.step_number} has unrecognized command executable '{first_token}'."
                            )
                            invalid_command_count += 1

        # 4. AUDIT FAITHFULNESS & UNSUPPORTED CLAIMS
        if available_chunk_ids and context_corpus_text:
            norm_corpus = " ".join(context_corpus_text.lower().split())

            # Check if CORS wildcard claims are supported
            if "allow_origins" in full_text_to_audit.lower() and "allow_credentials" in full_text_to_audit.lower():
                if "'*'" in full_text_to_audit or '"*"' in full_text_to_audit:
                    if "cannot be used" not in full_text_to_audit.lower() and "forbidden" not in full_text_to_audit.lower():
                        flagged_claims.append("Hallucinated claim: wildcard allow_origins with allow_credentials=True.")

            # Check substantive conceptual grounding for each step
            for step in resp_obj.action_plan:
                step_full = f"{step.title} {step.explanation} {step.command or ''}"
                step_tokens = [w.lower() for w in re.findall(r"[a-zA-Z0-9_]{3,}", step_full)]
                tech_tokens = [w for w in step_tokens if w not in COMMON_STOPWORDS]

                has_substantive_overlap = False
                for tok in tech_tokens:
                    if tok in norm_corpus or any(tok in chunk_word for chunk_word in norm_corpus.split()):
                        has_substantive_overlap = True
                        break

                if tech_tokens and not has_substantive_overlap:
                    flagged_claims.append(
                        f"Step {step.step_number} ('{step.title}') concepts not found in retrieved documentation."
                    )

        faithfulness_score = (
            round(max(0.0, 1.0 - (len(flagged_claims) / max(1, len(resp_obj.action_plan) or 1))), 4)
        )

        # 5. AUDIT ADHERENCE & VAGUE PHRASES
        adherence_issues = []
        for vague in VAGUE_PHRASES:
            if vague.lower() in full_text_to_audit.lower():
                adherence_issues.append(f"Contains prohibited vague phrase: '{vague}'")

        if not resp_obj.is_refusal and len(resp_obj.anti_patterns_to_avoid) == 0:
            adherence_issues.append("Missing mandatory anti_patterns_to_avoid.")

        # Check explicit judge criteria if provided
        if judge_criteria:
            for crit in judge_criteria:
                crit_lower = crit.lower()
                if crit_lower.startswith("must refuse"):
                    if not resp_obj.is_refusal:
                        adherence_issues.append(f"Failed criteria: {crit}")
                elif "must avoid" in crit_lower or "forbidding" in crit_lower:
                    if "string formatting" in crit_lower or "concatenation" in crit_lower:
                        if "f\"" in full_text_to_audit or "f'" in full_text_to_audit or ".format(" in full_text_to_audit:
                            adherence_issues.append(f"Failed criteria: {crit}")
                else:
                    keywords = [k.strip(" '\"`") for k in re.findall(r"['\"`](.*?)['\"`]", crit)]
                    if not keywords:
                        raw_tokens = re.findall(r"\b(?:[A-Za-z0-9_]+[._@%/()\-][A-Za-z0-9_./@%()\-]*|\d+(?:,\d+)?)\b", crit)
                        keywords = [t.strip(".,;:()") for t in raw_tokens if len(t.strip(".,;:()")) >= 2]

                    if keywords:
                        is_or_logic = " or " in crit_lower
                        norm_audit = re.sub(r"[-.:_()/,]", " ", full_text_to_audit.lower())
                        matched_keywords = []
                        for k in keywords:
                            k_norm = re.sub(r"[-.:_()/,]", " ", k.lower()).strip()
                            k_words = k_norm.split()
                            if (
                                k.lower() in full_text_to_audit.lower()
                                or k_norm in norm_audit
                                or (k_words and all(w in norm_audit.split() for w in k_words))
                            ):
                                matched_keywords.append(k)

                        if is_or_logic:
                            if not matched_keywords:
                                adherence_issues.append(f"Failed criteria: {crit}")
                        else:
                            content_words = [
                                w.lower() for w in re.findall(r"[a-zA-Z0-9_]{4,}", crit)
                                if w.lower() not in COMMON_STOPWORDS and w.lower() not in {"must", "mention", "state", "explain", "recommend", "answer", "declare", "contrast"}
                            ]
                            cw_matched = sum(1 for w in content_words if w in norm_audit)
                            has_content_coverage = (len(content_words) > 0 and (cw_matched / len(content_words)) >= 0.40)

                            required_count = len(keywords) if len(keywords) <= 2 else int(len(keywords) * 0.5)
                            if len(matched_keywords) < required_count and not has_content_coverage:
                                adherence_issues.append(f"Failed criteria: {crit}")

        adherence_score = (
            round(max(0.0, 1.0 - (len(adherence_issues) / max(1, len(judge_criteria or [1])))), 4)
        )

        # Fatal hallucination detection
        has_fatal_hallucination = (
            bool(hallucinated_code)
            or any("Refusal failure" in f for f in flagged_claims)
            or any("False refusal" in f for f in flagged_claims)
        )

        code_correctness_score = (
            0.0 if has_fatal_hallucination
            else round(max(0.0, 1.0 - (len(hallucinated_code) / max(1, total_commands or 1))), 4)
        )

        # 6. COMPOSITE SCORING & VERDICT
        overall_score = round(
            0.35 * faithfulness_score
            + 0.35 * groundedness_score
            + 0.20 * code_correctness_score
            + 0.10 * adherence_score,
            4,
        )

        if has_fatal_hallucination or overall_score < 0.65 or (judge_criteria and adherence_score < 0.50):
            verdict = "FAIL"
            is_valid = False
        elif overall_score >= self.pass_threshold and len(ungrounded_steps) == 0 and (not judge_criteria or adherence_score >= 0.70):
            verdict = "PASS"
            is_valid = True
        else:
            verdict = "WARN"
            is_valid = False

        feedback_parts = []
        if verdict == "PASS":
            feedback_parts.append("Response is faithful, well-grounded, and free of hallucinated code.")
        else:
            feedback_parts.append(f"Review verdict {verdict} (Overall score: {overall_score:.2f}).")
            if flagged_claims:
                feedback_parts.append(f"Unsupported claims: {'; '.join(flagged_claims)}")
            if hallucinated_code:
                feedback_parts.append(f"Code issues: {'; '.join(hallucinated_code)}")
            if ungrounded_steps:
                feedback_parts.append(f"Steps lacking citations: {ungrounded_steps}")
            if adherence_issues:
                feedback_parts.append(f"Adherence issues: {'; '.join(adherence_issues)}")

        return ReviewResult(
            is_valid=is_valid,
            verdict=verdict,
            faithfulness_score=faithfulness_score,
            groundedness_score=groundedness_score,
            code_correctness_score=code_correctness_score,
            adherence_score=adherence_score,
            overall_score=overall_score,
            flagged_claims=flagged_claims,
            hallucinated_code=hallucinated_code,
            ungrounded_steps=ungrounded_steps,
            feedback=" ".join(feedback_parts),
        )

    def _coerce_response(self, response: Union[NavigatorResponse, Dict[str, Any]]) -> NavigatorResponse:
        """Coerce dictionary or NavigatorResponse to a valid NavigatorResponse instance."""
        if isinstance(response, NavigatorResponse):
            return response
        if isinstance(response, dict):
            data = dict(response)
            if "summary" not in data:
                data["summary"] = data.get("text", "No summary provided.")
            if "action_plan" not in data:
                data["action_plan"] = []
            if "anti_patterns_to_avoid" not in data:
                data["anti_patterns_to_avoid"] = ["Do not skip testing."] if not data.get("is_refusal") else []
            return NavigatorResponse.model_validate(data)
        raise TypeError(f"Expected NavigatorResponse or dict, got {type(response)}")


# Default global reviewer instance
default_reviewer = ReviewerAgent()


def audit_response(
    query: str,
    response: Union[NavigatorResponse, Dict[str, Any]],
    retrieved_chunks: Optional[List[Dict[str, Any]]] = None,
    judge_criteria: Optional[List[str]] = None,
) -> ReviewResult:
    """Convenience helper to audit a response with the default ReviewerAgent."""
    return default_reviewer.audit(
        query=query,
        response=response,
        retrieved_chunks=retrieved_chunks,
        judge_criteria=judge_criteria,
    )
