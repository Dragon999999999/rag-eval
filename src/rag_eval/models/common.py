"""Shared canonical types and validation helpers for rag-eval models."""

from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

JsonDict = dict[str, Any]


class CanonicalModel(BaseModel):
    """Base for strict canonical models with JSON-compatible extension fields."""

    model_config = ConfigDict(extra="forbid")


class MessageRole(StrEnum):
    """Roles supported by canonical conversation history."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


def validate_aware_timestamp(value: datetime | None) -> datetime | None:
    """Reject timestamps without a UTC offset or timezone information."""
    if value is None:
        return value
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    return value


class ArtifactRef(CanonicalModel):
    """Reference to immutable bytes stored outside transactional persistence."""

    artifact_id: str
    uri: str
    sha256: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    content_type: str | None = None
    created_at: datetime | None = None
    metadata: JsonDict = Field(default_factory=dict)

    _validate_created_at = field_validator("created_at")(validate_aware_timestamp)


class SourceLocation(CanonicalModel):
    """Stable source coordinates shared by evidence, retrieval, and citations."""

    document_id: str | None = None
    chunk_id: str | None = None
    page: int | None = Field(default=None, ge=1)
    start_char: int | None = Field(default=None, ge=0)
    end_char: int | None = Field(default=None, ge=0)
    section: str | None = None
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_character_span(self) -> "SourceLocation":
        """Ensure complete source spans have valid half-open boundaries."""
        if (self.start_char is None) != (self.end_char is None):
            raise ValueError("start_char and end_char must be provided together")
        if self.start_char is not None and self.end_char is not None:
            if self.end_char < self.start_char:
                raise ValueError("end_char must be greater than or equal to start_char")
        return self


class Message(CanonicalModel):
    """One ordered, benchmark-controlled conversation message."""

    role: MessageRole
    content: str
    name: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class WarningRecord(CanonicalModel):
    """A non-fatal observation reported by a target or evaluator."""

    code: str
    message: str
    stage: str | None = None
    metadata: JsonDict = Field(default_factory=dict)
