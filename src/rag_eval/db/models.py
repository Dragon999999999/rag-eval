"""PostgreSQL ORM records for durable rag-eval operational state.

Canonical Pydantic models remain the executable payload schemas. ORM records
store queryable identity, ownership, and lifecycle fields plus JSONB payloads
where fully normalizing nested structures would be counterproductive.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from rag_eval.db.base import Base


class TimestampedRecord:
    """Common database creation timestamp for durable records."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ============================================================================
# Benchmarks
# ============================================================================


class BenchmarkRecord(Base, TimestampedRecord):
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


class BenchmarkCaseRecord(Base, TimestampedRecord):
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


class BenchmarkDocumentRecord(Base, TimestampedRecord):
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


class BenchmarkChunkRecord(Base, TimestampedRecord):
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


# ============================================================================
# Targets and capabilities
# ============================================================================


class TargetRecord(Base, TimestampedRecord):
    """Stable identity for an evaluated target."""

    __tablename__ = "targets"

    target_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    version: Mapped[str | None] = mapped_column(
        String(255),
    )

    implementation: Mapped[str | None] = mapped_column(
        String(255),
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


class TargetCapabilityRecord(Base, TimestampedRecord):
    """Latest discovered canonical capability payload for one target."""

    __tablename__ = "target_capabilities"

    target_id: Mapped[str] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
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


# ============================================================================
# Target corpora
# ============================================================================


class CorpusRecord(Base, TimestampedRecord):
    """Target-side corpus identity and preparation lifecycle state."""

    __tablename__ = "corpora"

    corpus_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    target_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="SET NULL",
        ),
        index=True,
    )

    mode: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    content_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


class DocumentRecord(Base, TimestampedRecord):
    """Document metadata for material uploaded into a target corpus.

    This is intentionally separate from BenchmarkDocumentRecord. A benchmark
    document is evaluator-owned source material; this record represents its
    target-side corpus ingestion.
    """

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    corpus_id: Mapped[str] = mapped_column(
        ForeignKey(
            "corpora.corpus_id",
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
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


# ============================================================================
# Reusable evaluation configuration
# ============================================================================


class MetricConfigRecord(Base, TimestampedRecord):
    """Reusable named metric configuration."""

    __tablename__ = "metric_configs"

    metric_config_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    mode: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    selected_metrics: Mapped[list[str]] = mapped_column(
        JSONB,
        default=list,
        nullable=False,
    )

    metric_parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    judge_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    retrieval_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    config_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )


class TestDefinitionRecord(Base, TimestampedRecord):
    """Reusable evaluation definition.

    References the target, benchmark, and metric configuration while keeping
    execution state separate.
    """

    __tablename__ = "test_definitions"

    test_definition_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    description: Mapped[str | None] = mapped_column(
        Text,
    )

    target_id: Mapped[str] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    benchmark_id: Mapped[str] = mapped_column(
        ForeignKey(
            "benchmarks.benchmark_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    metric_config_id: Mapped[str] = mapped_column(
        ForeignKey(
            "metric_configs.metric_config_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    execution_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    seed: Mapped[int | None] = mapped_column(
        Integer,
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

    definition_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )


# ============================================================================
# Runs
# ============================================================================


class RunConfigRecord(Base, TimestampedRecord):
    """Immutable secret-free canonical configuration deduplicated by hash."""

    __tablename__ = "run_configs"

    config_hash: Mapped[str] = mapped_column(
        String(64),
        primary_key=True,
    )

    canonical_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )


class RunRecord(Base, TimestampedRecord):
    """Durable lifecycle state for one evaluation run."""

    __tablename__ = "runs"

    run_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    config_hash: Mapped[str] = mapped_column(
        ForeignKey(
            "run_configs.config_hash",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    target_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="SET NULL",
        ),
        index=True,
    )

    test_definition_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "test_definitions.test_definition_id",
            ondelete="SET NULL",
        ),
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    seed: Mapped[int | None] = mapped_column(
        Integer,
    )

    rag_eval_version: Mapped[str | None] = mapped_column(
        String(64),
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


# ============================================================================
# Execution
# ============================================================================


class CaseExecutionRecord(Base, TimestampedRecord):
    """One logical benchmark case execution within a run."""

    __tablename__ = "case_executions"

    __table_args__ = (
        UniqueConstraint(
            "run_id",
            "case_id",
            name="uq_case_execution_run_case",
        ),
    )

    case_execution_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "runs.run_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    case_id: Mapped[str] = mapped_column(
        ForeignKey(
            "benchmark_cases.case_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


class AttemptRecord(Base, TimestampedRecord):
    """Append-only target attempt; retries never overwrite historical rows."""

    __tablename__ = "attempts"

    __table_args__ = (
        UniqueConstraint(
            "case_execution_id",
            "attempt_number",
            name="uq_attempt_case_number",
        ),
    )

    attempt_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    case_execution_id: Mapped[str] = mapped_column(
        ForeignKey(
            "case_executions.case_execution_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    attempt_number: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    request_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
    )

    idempotency_key: Mapped[str | None] = mapped_column(
        String(255),
        index=True,
    )

    canonical_request_hash: Mapped[str | None] = mapped_column(
        String(64),
        index=True,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    raw_request_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "artifacts.artifact_id",
            ondelete="SET NULL",
        ),
    )

    raw_response_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "artifacts.artifact_id",
            ondelete="SET NULL",
        ),
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


class StageExecutionRecord(Base, TimestampedRecord):
    """Optional timing and lifecycle record for a target operation stage."""

    __tablename__ = "stage_executions"

    stage_execution_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    attempt_id: Mapped[str] = mapped_column(
        ForeignKey(
            "attempts.attempt_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    stage_name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


# ============================================================================
# Target observations
# ============================================================================


class TargetObservationRecord(Base, TimestampedRecord):
    """Validated normalized target result reusable by future scoring passes."""

    __tablename__ = "target_observations"

    observation_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    request_id: Mapped[str] = mapped_column(
        String(128),
        unique=True,
        nullable=False,
    )

    case_execution_id: Mapped[str] = mapped_column(
        ForeignKey(
            "case_executions.case_execution_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    attempt_id: Mapped[str] = mapped_column(
        ForeignKey(
            "attempts.attempt_id",
            ondelete="CASCADE",
        ),
        unique=True,
        nullable=False,
    )

    normalization_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    payload_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )


# ============================================================================
# Metrics
# ============================================================================


class MetricResultRecord(Base, TimestampedRecord):
    """Case- or run-level raw metric result."""

    __tablename__ = "metric_results"

    metric_result_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "runs.run_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    case_execution_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "case_executions.case_execution_id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    case_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "benchmark_cases.case_id",
            ondelete="SET NULL",
        ),
        index=True,
    )

    metric_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    metric_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    value: Mapped[Any | None] = mapped_column(
        JSONB,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )


class AggregateMetricResultRecord(Base, TimestampedRecord):
    """Run-level aggregate metric separate from individual case results."""

    __tablename__ = "aggregate_metric_results"

    aggregate_metric_result_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    run_id: Mapped[str] = mapped_column(
        ForeignKey(
            "runs.run_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    metric_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    metric_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    aggregation: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    value: Mapped[Any | None] = mapped_column(
        JSONB,
    )

    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    reason: Mapped[str | None] = mapped_column(
        Text,
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


# ============================================================================
# Errors
# ============================================================================


class ErrorRecordDB(Base, TimestampedRecord):
    """Structured normalized error without large provider payload storage."""

    __tablename__ = "errors"

    error_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    run_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "runs.run_id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    case_execution_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "case_executions.case_execution_id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    attempt_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "attempts.attempt_id",
            ondelete="CASCADE",
        ),
        index=True,
    )

    category: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    code: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    message: Mapped[str] = mapped_column(
        Text,
        nullable=False,
    )

    stage: Mapped[str | None] = mapped_column(
        String(255),
    )

    retryable: Mapped[bool] = mapped_column(
        Boolean,
        default=False,
        nullable=False,
    )

    retry_after_ms: Mapped[int | None] = mapped_column(
        Integer,
    )

    http_status: Mapped[int | None] = mapped_column(
        Integer,
    )

    provider: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    raw_artifact_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "artifacts.artifact_id",
            ondelete="SET NULL",
        ),
    )

    details: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )