"""PostgreSQL ORM records for evaluator-owned benchmark state."""

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from rag_eval.db.base import Base


class _BenchmarkTimestampedRecord:
    """Common database creation timestamp for benchmark records."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


class BenchmarkRecord(Base, _BenchmarkTimestampedRecord):
    """Persisted identity and metadata for one canonical benchmark."""

    __tablename__ = "benchmarks"

    benchmark_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    schema_version: Mapped[str] = mapped_column(
        String(64),
        default="1.0",
        nullable=False,
    )

    corpus_mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        index=True,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )

    corpus_id: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
    )

    source: Mapped[str | None] = mapped_column(
        Text,
    )

    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


class BenchmarkCaseRecord(Base, _BenchmarkTimestampedRecord):
    """Evaluator-owned ground-truth case belonging to a benchmark."""

    __tablename__ = "benchmark_cases"

    case_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    benchmark_id: Mapped[str] = mapped_column(
        ForeignKey(
            "benchmarks.benchmark_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    query: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    history: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    reference_answer: Mapped[str | None] = mapped_column(
        Text,
    )

    gold_evidence: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    answerability: Mapped[str | None] = mapped_column(
        String(32),
    )

    tags: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


class BenchmarkDocumentRecord(Base, _BenchmarkTimestampedRecord):
    """Evaluator-owned source document belonging to a benchmark."""

    __tablename__ = "benchmark_documents"

    document_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    benchmark_id: Mapped[str] = mapped_column(
        ForeignKey(
            "benchmarks.benchmark_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    filename: Mapped[str | None] = mapped_column(
        String(1024),
    )

    mime_type: Mapped[str | None] = mapped_column(
        String(255),
    )

    sha256: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )

    size_bytes: Mapped[int | None] = mapped_column(
        Integer,
    )

    artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "artifacts.artifact_id",
            ondelete="SET NULL",
        ),
        index=True,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


class BenchmarkChunkRecord(Base, _BenchmarkTimestampedRecord):
    """Evaluator-owned canonical chunk belonging to a benchmark."""

    __tablename__ = "benchmark_chunks"

    chunk_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    benchmark_id: Mapped[str] = mapped_column(
        ForeignKey(
            "benchmarks.benchmark_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    document_id: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    text: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    location: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )
