"""PostgreSQL ORM records for durable rag-eval operational state.

Canonical Pydantic models remain the executable payload schemas. ORM records
store queryable identity, ownership, and lifecycle fields plus JSONB payloads
where fully normalizing nested structures would be counterproductive.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    DateTime,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from rag_eval.db.base import Base
from rag_eval.db.benchmark_models import (
    BenchmarkCaseRecord,
    BenchmarkChunkRecord,
    BenchmarkDocumentRecord,
    BenchmarkRecord,
)
from rag_eval.db.target_models import (
    CorpusRecord,
    DocumentRecord,
    TargetCapabilityRecord,
    TargetConfigVersionRecord,
    TargetConnectionRecord,
    TargetObservationRecord,
    TargetRecord,
    TargetSecretRecord,
)


class TimestampedRecord:
    """Common database creation timestamp for durable records."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ============================================================================
# Artifacts
# ============================================================================


class ArtifactRecord(Base, TimestampedRecord):
    """Metadata and external location for immutable artifact bytes."""

    __tablename__ = "artifacts"

    artifact_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    artifact_type: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    uri: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    sha256: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
    )

    content_type: Mapped[str | None] = mapped_column(
        String(255),
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )