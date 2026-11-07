"""
eval/schema.py

Replacement Gold Set Schema (v2) and Validator for Tutorial Hell Navigator.
Enforces strict provenance, verbatim evidence spans, and test set hygiene.

Rules enforced:
1. not_answerable questions have empty evidence.
2. answerable questions have at least one required span (in v2).
3. A VERIFIED span must appear verbatim in the named corpus file in corpus/raw/.
4. A test question must not be BURNED (e.g. marked BURNED or LABELED_AFTER_RESULTS).
5. Every row has origin, labeled_by, and labeled_on.
"""

import os
from pathlib import Path
from typing import List, Dict, Any, Optional, Literal
from pydantic import BaseModel, Field, model_validator

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS_RAW_DIR = PROJECT_ROOT / "corpus" / "raw"

# Cache for raw corpus text to avoid redundant disk/pdf parsing
_raw_corpus_cache: Dict[str, str] = {}


def read_raw_corpus_text(source_file: str, corpus_raw_dir: Optional[Path] = None) -> str:
    """Read full text of a raw corpus file (Markdown or PDF) from corpus/raw/."""
    raw_dir = corpus_raw_dir or DEFAULT_CORPUS_RAW_DIR
    target_path = raw_dir / source_file

    # Also handle if source_file has relative path or subfolder
    if not target_path.exists():
        # Try matching basename in raw_dir
        target_path = raw_dir / Path(source_file).name

    if not target_path.exists():
        raise FileNotFoundError(f"Corpus raw file '{source_file}' not found in {raw_dir}")

    cache_key = str(target_path.resolve())
    if cache_key in _raw_corpus_cache:
        return _raw_corpus_cache[cache_key]

    ext = target_path.suffix.lower()
    if ext == ".pdf":
        try:
            import pymupdf
            doc = pymupdf.open(target_path)
        except ImportError:
            import fitz
            doc = fitz.open(target_path)
        pages_text = [page.get_text() for page in doc]
        doc.close()
        text = "\n".join(pages_text)
    else:
        with open(target_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

    _raw_corpus_cache[cache_key] = text
    return text


class EvidenceItem(BaseModel):
    """Verbatim evidence span pointing to a raw technical corpus file."""
    source_file: str = Field(..., description="Filename in corpus/raw/ e.g. fastapi_cors.md")
    span: str = Field(..., description="Verbatim answer text extracted directly from the file")


class Origin(BaseModel):
    """Data provenance and source tracking."""
    kind: Literal["stackoverflow", "reddit", "student", "owner", "UNSET"]
    url: Optional[str] = ""
    collected_on: str = Field(..., description="ISO date YYYY-MM-DD")
    license: Optional[str] = ""


class GoldStandardQuestionV2(BaseModel):
    """
    Gold Standard Evaluation Benchmark Question (v2 Schema).
    Decouples factual evidence from volatile chunk boundaries.
    """
    id: str
    topic: str = Field(..., description="Topic identifier or 'UNSET'")
    type: Literal["conceptual", "exact_syntax", "multi_hop", "debugging", "UNSET"]
    origin: Origin
    question: str
    answerability: Literal["answerable", "partial", "not_answerable"]
    answer_spans: List[EvidenceItem] = Field(default_factory=list, description="List of verbatim answer spans")
    required_evidence: List[EvidenceItem] = Field(default_factory=list, description="Alias for answer_spans for backwards compatibility")
    acceptable_alternatives: List[EvidenceItem] = Field(default_factory=list, description="List of acceptable alternative spans")
    must_include: List[str] = Field(default_factory=list)
    must_not_include: List[str] = Field(default_factory=list)
    judge_criteria: List[str] = Field(default_factory=list)
    span_status: Literal["UNVERIFIED", "VERIFIED"] = "UNVERIFIED"
    labeled_by: str
    labeled_on: str
    corpus_version: str = "v2"
    split: Literal["dev", "test", "UNSET"] = "UNSET"
    source_kind: Optional[Literal["official", "owner_authored", "out_of_scope"]] = None
    labeling_status: Literal["CLEAN", "LABELED_AFTER_RESULTS", "BURNED"] = "CLEAN"
    legacy_expected_chunk_ids: Optional[List[str]] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def sync_answer_spans(cls, data: Any) -> Any:
        if isinstance(data, dict):
            data = dict(data)
            # Synchronize answer_spans and required_evidence
            if "answer_spans" in data and "required_evidence" not in data:
                data["required_evidence"] = data["answer_spans"]
            elif "required_evidence" in data and "answer_spans" not in data:
                data["answer_spans"] = data["required_evidence"]
            elif "required_evidence" in data and "answer_spans" in data:
                if not data["answer_spans"] and data["required_evidence"]:
                    data["answer_spans"] = data["required_evidence"]
                elif not data["required_evidence"] and data["answer_spans"]:
                    data["required_evidence"] = data["answer_spans"]
        return data

    @model_validator(mode="after")
    def validate_rules(self) -> "GoldStandardQuestionV2":
        # Keep both in sync if one was set post-init
        if self.answer_spans and not self.required_evidence:
            self.required_evidence = self.answer_spans
        elif self.required_evidence and not self.answer_spans:
            self.answer_spans = self.required_evidence

        # Rule 5: Every row has origin, labeled_by, and labeled_on
        if not self.origin or not getattr(self.origin, "kind", None):
            raise ValueError(f"[{self.id}] Rule 5 Violation: Every row must have origin.kind.")
        if not self.labeled_by or not self.labeled_by.strip():
            raise ValueError(f"[{self.id}] Rule 5 Violation: Every row must have non-empty labeled_by.")
        if not self.labeled_on or not self.labeled_on.strip():
            raise ValueError(f"[{self.id}] Rule 5 Violation: Every row must have non-empty labeled_on.")

        # Rule 1: not_answerable questions have empty evidence
        active_evidence_len = max(len(self.answer_spans), len(self.required_evidence))
        if self.answerability == "not_answerable":
            if active_evidence_len > 0 or len(self.acceptable_alternatives) > 0:
                raise ValueError(
                    f"[{self.id}] Rule 1 Violation: not_answerable questions must have empty evidence "
                    f"(found {active_evidence_len} answer spans, {len(self.acceptable_alternatives)} alternatives)."
                )

        # Rule 2: answerable questions have at least one required span (enforced on v2)
        if self.answerability == "answerable" and self.corpus_version == "v2":
            if active_evidence_len == 0:
                raise ValueError(
                    f"[{self.id}] Rule 2 Violation: answerable questions in corpus_version 'v2' must have at least one required span."
                )

        # Rule 4: A test question must not be BURNED
        if self.split == "test":
            if self.labeling_status in ("BURNED", "LABELED_AFTER_RESULTS"):
                raise ValueError(
                    f"[{self.id}] Rule 4 Violation: A test question must not be BURNED "
                    f"(found labeling_status='{self.labeling_status}')."
                )

        return self


def validate_verbatim_spans(
    question: GoldStandardQuestionV2,
    corpus_raw_dir: Optional[Path] = None,
) -> None:
    """
    Enforces Rule 3: A VERIFIED span must appear verbatim in the named corpus file in corpus/raw/.
    """
    if question.span_status != "VERIFIED":
        return

    raw_dir = corpus_raw_dir or DEFAULT_CORPUS_RAW_DIR

    evidence_items = question.answer_spans or question.required_evidence
    all_evidence = [("answer_span", item) for item in evidence_items] + [
        ("alternative", item) for item in question.acceptable_alternatives
    ]

    for ev_type, item in all_evidence:
        if not item.span or not item.span.strip():
            raise ValueError(
                f"[{question.id}] Rule 3 Violation: {ev_type} evidence has an empty span."
            )
        try:
            raw_text = read_raw_corpus_text(item.source_file, corpus_raw_dir=raw_dir)
        except FileNotFoundError as e:
            raise ValueError(f"[{question.id}] Rule 3 Violation: {e}")

        # Check verbatim substring match
        if item.span not in raw_text:
            # Also check normalized whitespace variant in case of Windows CRLF vs LF differences
            norm_span = " ".join(item.span.split())
            norm_raw = " ".join(raw_text.split())
            if norm_span not in norm_raw:
                snippet = item.span[:60] + ("..." if len(item.span) > 60 else "")
                raise ValueError(
                    f"[{question.id}] Rule 3 Violation: VERIFIED span does not appear verbatim in {item.source_file}: '{snippet}'"
                )


def validate_question(
    question_data: Dict[str, Any] | GoldStandardQuestionV2,
    corpus_raw_dir: Optional[Path] = None,
) -> GoldStandardQuestionV2:
    """Validate a single question dictionary or model instance against all 5 rules."""
    if isinstance(question_data, dict):
        model = GoldStandardQuestionV2.model_validate(question_data)
    else:
        model = question_data

    validate_verbatim_spans(model, corpus_raw_dir=corpus_raw_dir)
    return model


def validate_dataset(
    dataset: List[Dict[str, Any]],
    corpus_raw_dir: Optional[Path] = None,
) -> List[GoldStandardQuestionV2]:
    """Validate an entire dataset against all 5 schema rules."""
    validated: List[GoldStandardQuestionV2] = []
    errors: List[str] = []

    for item in dataset:
        try:
            q = validate_question(item, corpus_raw_dir=corpus_raw_dir)
            validated.append(q)
        except Exception as e:
            errors.append(str(e))

    if errors:
        msg = f"Dataset validation failed with {len(errors)} error(s):\n" + "\n".join(errors[:10])
        if len(errors) > 10:
            msg += f"\n...and {len(errors) - 10} more errors."
        raise ValueError(msg)

    return validated
