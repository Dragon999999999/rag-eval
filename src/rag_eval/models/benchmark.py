"""Canonical corpus and benchmark truth models."""

from datetime import datetime

from pydantic import Field, field_validator

from rag_eval.models.common import (
    ArtifactRef,
    CanonicalModel,
    JsonDict,
    Message,
    SourceLocation,
    validate_aware_timestamp,
)
from rag_eval.models.enums import Answerability, CorpusMode


class Document(CanonicalModel):
    """A stable evaluator-owned source document."""

    document_id: str
    filename: str | None = None
    mime_type: str | None = None
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    artifact: ArtifactRef | None = None
    metadata: JsonDict = Field(default_factory=dict)


class Chunk(CanonicalModel):
    """An evaluator-defined chunk used in controlled chunk corpus mode."""

    chunk_id: str
    document_id: str
    text: str
    location: SourceLocation | None = None
    metadata: JsonDict = Field(default_factory=dict)


class EvidenceSpan(CanonicalModel):
    """Gold evidence identified independently of target-specific chunk IDs."""

    evidence_id: str
    document_id: str
    page: int | None = Field(default=None, ge=1)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    text: str | None = None
    relevance: float | None = None
    metadata: JsonDict = Field(default_factory=dict)

    @field_validator("end_char")
    @classmethod
    def validate_end_char(cls, value: int | None, info: object) -> int | None:
        """Ensure a complete gold-evidence span is half-open and ordered."""
        start_char = getattr(info, "data", {}).get("start_char")
        if value is not None and start_char is not None and value < start_char:
            raise ValueError("end_char must be greater than or equal to start_char")
        return value


class SuppliedContext(CanonicalModel):
    """Evaluator-controlled context supplied directly to a target."""

    context_id: str
    text: str
    source: SourceLocation | None = None
    metadata: JsonDict = Field(default_factory=dict)


class BenchmarkManifest(CanonicalModel):
    """Versioned metadata needed to identify and reproduce a benchmark."""

    benchmark_id: str
    name: str
    version: str
    schema_version: str = "1.0"
    content_hash: str | None = None
    case_count: int | None = Field(default=None, ge=0)
    corpus_id: str | None = None
    created_at: datetime | None = None
    source: str | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)

    _validate_created_at = field_validator("created_at")(validate_aware_timestamp)


class BenchmarkCase(CanonicalModel):
    """One benchmark-owned prompt and optional reference truth."""

    case_id: str
    query: str
    history: list[Message] = Field(default_factory=list)
    reference_answer: str | None = None
    gold_evidence: list[EvidenceSpan] = Field(default_factory=list)
    answerability: Answerability | None = None
    tags: list[str] = Field(default_factory=list)
    difficulty: str | None = None
    language: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


__all__ = [
    "BenchmarkCase",
    "BenchmarkManifest",
    "Chunk",
    "CorpusMode",
    "Document",
    "EvidenceSpan",
    "SuppliedContext",
]
