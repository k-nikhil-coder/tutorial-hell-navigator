from typing import List, Optional
from pydantic import BaseModel, Field


class ActionableStep(BaseModel):
    step_number: int = Field(..., ge=1, description="Step index (1-based)")
    title: str = Field(..., description="Short title for this action")
    command: Optional[str] = Field(None, description="Terminal command or code snippet")
    explanation: str = Field(..., description="Why this step is necessary")
    verification: Optional[str] = Field(None, description="How to verify the step succeeded")
    citations: List[str] = Field(default_factory=list, description="Exact chunk_id references supporting this step")


class NavigatorResponse(BaseModel):
    summary: str = Field(..., description="Overview of the diagnosis and solution")
    action_plan: List[ActionableStep] = Field(..., min_length=1, description="Ordered list of steps to resolve the issue")
    anti_patterns_to_avoid: List[str] = Field(..., min_length=1, description="Pitfalls and bad habits to avoid")
    architecture_contract: Optional[str] = Field(None, description="File tree or component architecture if relevant")
    key_takeaway: Optional[str] = Field(None, description="Core concept to take away")
    is_refusal: bool = Field(False, description="True if query is out-of-corpus and cannot be verified")
    refusal_reason: Optional[str] = Field(None, description="Explanation if refusal path was triggered")
    cited_chunk_ids: List[str] = Field(default_factory=list, description="All chunk_ids cited across the response")


class QueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="User roadblock, question, or error message")
    topic: Optional[str] = None


class HealthStatus(BaseModel):
    status: str = "healthy"
    model: str
    concurrency_limit: int
    available_tools: List[str]
    indexed_chunks: int = 0
    vector_store: str = "Qdrant"


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
