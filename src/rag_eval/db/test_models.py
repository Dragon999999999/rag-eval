"""ORM records for test definitions, evaluation runs, execution, and metrics.

This module owns the durable structures that belong to the evaluation/test
lifecycle:

- editable test definitions
- test-owned metric selections
- immutable run configuration snapshots
- run lifecycle and recovery state
- case executions and retry attempts
- optional stage execution timing
- per-case metric results and run-level aggregates
- run lifecycle events
- run/case/attempt-scoped normalized errors

Metric definitions themselves remain registry-backed.  A test stores only the
selection/configuration of those registered metrics.

Artifacts, targets, benchmarks, and other cross-cutting records remain in their
respective general/domain modules.
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
from rag_eval.db.models import TimestampedRecord


# ============================================================================
# Test definitions
# ============================================================================


class TestDefinitionRecord(Base, TimestampedRecord):
    """Editable evaluation definition.

    A test may be created with only a name and remain INCOMPLETE until a target,
    benchmark, and usable metric selection are configured.

    Metric configuration belongs to the test rather than to a separate reusable
    MetricConfig object.  Reusable metric presets can be introduced later
    without making them part of the core test lifecycle.
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

    target_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    benchmark_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "benchmarks.benchmark_id",
            ondelete="SET NULL",
        ),
        nullable=True,
        index=True,
    )

    # INCOMPLETE / READY.  The service layer decides readiness after validating
    # target, benchmark, metric applicability, judge settings, etc.
    configuration_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="INCOMPLETE",
        index=True,
    )

    # EXPLICIT / ALL_AVAILABLE.
    metric_selection_mode: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="EXPLICIT",
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

    # May be NULL while the test is incomplete.  The service layer recomputes it
    # whenever the runnable configuration changes.
    definition_hash: Mapped[str | None] = mapped_column(
        String(64),
        nullable=True,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class TestMetricSelectionRecord(Base, TimestampedRecord):
    """One metric explicitly selected/configured for a test.

    Rows are authoritative only when the test uses EXPLICIT mode.  In
    ALL_AVAILABLE mode the service resolves all currently applicable registered
    metrics when a run starts and snapshots that resolved list into RunConfig.
    """

    __tablename__ = "test_metric_selections"

    __table_args__ = (
        UniqueConstraint(
            "test_definition_id",
            "metric_id",
            name="uq_test_metric_selection_test_metric",
        ),
    )

    test_metric_selection_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    test_definition_id: Mapped[str] = mapped_column(
        ForeignKey(
            "test_definitions.test_definition_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    metric_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # NULL means "resolve the currently registered version when the run starts".
    # The resolved concrete version belongs in the immutable run snapshot.
    metric_version: Mapped[str | None] = mapped_column(
        String(64),
    )

    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


# ============================================================================
# Runs and immutable configuration snapshots
# ============================================================================


class RunConfigRecord(Base, TimestampedRecord):
    """Immutable secret-free run configuration deduplicated by hash.

    The canonical snapshot should contain all information required to reproduce
    or resume the run independently of later edits to the source TestDefinition,
    including resolved target/benchmark versions and concrete metric versions.
    """

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

    # Typical values:
    # CREATED, PENDING, RUNNING, PAUSING, PAUSED, INTERRUPTED,
    # COMPLETED, FAILED, CANCELLED.
    status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )

    status_reason: Mapped[str | None] = mapped_column(
        Text,
    )

    config_hash: Mapped[str] = mapped_column(
        ForeignKey(
            "run_configs.config_hash",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    # Queryable convenience references.  The immutable authoritative identity is
    # still the RunConfig snapshot.
    target_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="SET NULL",
        ),
        index=True,
    )

    benchmark_id: Mapped[str | None] = mapped_column(
        ForeignKey(
            "benchmarks.benchmark_id",
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

    paused_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    interrupted_at: Mapped[datetime | None] = mapped_column(
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class RunEventRecord(Base, TimestampedRecord):
    """Append-only lifecycle/audit event for a run."""

    __tablename__ = "run_events"

    run_event_id: Mapped[str] = mapped_column(
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

    event_type: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        index=True,
    )

    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


# ============================================================================
# Case execution / attempts
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

    # PENDING / RUNNING / COMPLETED / FAILED / CANCELLED / INTERRUPTED.
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
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

    retryable: Mapped[bool | None] = mapped_column(
        Boolean,
    )

    error_summary: Mapped[str | None] = mapped_column(
        Text,
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

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class StageExecutionRecord(Base, TimestampedRecord):
    """Optional timing and lifecycle record for one target operation stage."""

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
# Metric results
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
        index=True,
    )

    metric_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
    )

    value: Mapped[Any | None] = mapped_column(
        JSONB,
    )

    # AVAILABLE / UNAVAILABLE / FAILED / SKIPPED, or existing canonical values.
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

    # Preserve the full canonical metric payload for forward compatibility.
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
        index=True,
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
# Run-scoped normalized errors
# ============================================================================


class ErrorRecordDB(Base, TimestampedRecord):
    """Structured normalized error associated with run execution."""

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