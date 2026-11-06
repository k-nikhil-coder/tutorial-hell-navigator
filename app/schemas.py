from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, model_validator


class ActionableStep(BaseModel):
    step_number: int = Field(..., ge=1, description="Step index (1-based)")
    title: str = Field(..., description="Short title for this action")
    command: Optional[str] = Field(None, description="Terminal command or code snippet")
    explanation: str = Field(..., description="Why this step is necessary")
    verification: Optional[str] = Field(None, description="How to verify the step succeeded")
    citations: List[str] = Field(default_factory=list, description="Exact chunk_id references supporting this step")


class NavigatorResponse(BaseModel):
    summary: str = Field(..., description="Overview of the diagnosis and solution")
    action_plan: List[ActionableStep] = Field(default_factory=list, description="Ordered list of steps to resolve the issue")
    anti_patterns_to_avoid: List[str] = Field(default_factory=list, description="Pitfalls and bad habits to avoid")
    architecture_contract: Optional[str] = Field(None, description="File tree or component architecture if relevant")
    key_takeaway: Optional[str] = Field(None, description="Core concept to take away")
    is_refusal: bool = Field(False, description="True if query is out-of-corpus and cannot be verified")
    refusal_reason: Optional[str] = Field(None, description="Explanation if refusal path was triggered")
    cited_chunk_ids: List[str] = Field(default_factory=list, description="All chunk_ids cited across the response")

    @model_validator(mode="after")
    def validate_plan_requirements(self) -> "NavigatorResponse":
        if not self.is_refusal:
            if len(self.action_plan) < 1:
                raise ValueError("In-corpus responses must provide at least 1 actionable step.")
            if len(self.anti_patterns_to_avoid) < 1:
                raise ValueError("In-corpus responses must provide at least 1 anti-pattern.")
        return self


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User roadblock, question, or error message")
    topic: Optional[str] = None
    category: Optional[str] = None
    backend: Optional[str] = Field("qdrant", description="Vector store backend: 'qdrant' or 'pgvector'")


class HealthStatus(BaseModel):
    status: str = "healthy"
    model: str
    concurrency_limit: int
    available_tools: List[str]
    indexed_chunks: int = 0
    vector_store: str = "Qdrant"
    pgvector_indexed_chunks: Optional[int] = None
    pgvector_is_live: Optional[bool] = None


class RetrievedChunk(BaseModel):
    chunk_id: str
    source_file: str
    score: float
    text_preview: str


class QueryTrajectory(BaseModel):
    timestamp: str
    query: str
    retrieved_chunks: List[RetrievedChunk]
    is_refusal: bool
    cited_chunk_ids: List[str]
    latency_ms: float
    response_summary: str


class FeedbackRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Original user query")
    rating: Optional[str] = Field(None, description="User rating: 'positive' or 'negative'")
    unstuck: Optional[bool] = Field(None, description="Phase 0 metric: did this answer unstick the student?")
    comment: Optional[str] = Field(None, max_length=1000, description="Optional qualitative feedback")
    cited_chunk_ids: List[str] = Field(default_factory=list, description="Chunks cited in the response")
    session_id: Optional[str] = Field(None, description="Anonymous session identifier")


class FeedbackResponse(BaseModel):
    status: str = "ok"
    message: str = "Feedback recorded"


class ReviewResult(BaseModel):
    is_valid: bool = Field(..., description="Overall pass/fail verdict from reviewer")
    verdict: str = Field(..., description="'PASS', 'FAIL', or 'WARN'")
    faithfulness_score: float = Field(..., ge=0.0, le=1.0, description="Score indicating whether claims are supported by context")
    groundedness_score: float = Field(..., ge=0.0, le=1.0, description="Score indicating whether steps have verified chunk citations")
    code_correctness_score: float = Field(..., ge=0.0, le=1.0, description="Score indicating absence of hallucinated code/commands")
    adherence_score: float = Field(..., ge=0.0, le=1.0, description="Score for meeting rubric constraints and avoiding anti-patterns")
    overall_score: float = Field(..., ge=0.0, le=1.0, description="Aggregate correctness score")
    flagged_claims: List[str] = Field(default_factory=list, description="Unsupported or hallucinated claims detected")
    hallucinated_code: List[str] = Field(default_factory=list, description="Hallucinated commands, flags, or invalid code detected")
    ungrounded_steps: List[int] = Field(default_factory=list, description="Step numbers lacking verified chunk citations")
    feedback: str = Field(..., description="Detailed reviewer explanation and critique")


class ReviewRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User query or question")
    response: NavigatorResponse = Field(..., description="Navigator response to audit")
    retrieved_chunks: Optional[List[Dict[str, Any]]] = Field(default_factory=list, description="Retrieved chunks used as context")

