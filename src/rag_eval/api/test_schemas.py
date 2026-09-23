"""Pydantic schemas for test configuration and evaluation-run API contracts.

These are presentation-layer schemas for:
- editable test definitions
- test-owned metric selection
- metric YAML import/export
- test validation
- evaluation run lifecycle
- case execution and retry attempts
- metric results and aggregates
- run lifecycle events

They are intentionally separate from canonical domain models and ORM records.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ============================================================================
# Metric registry
# ============================================================================


class MetricDefinition(BaseModel):
    """Registered metric definition."""

    metric_id: str
    version: str
    scope: str
    requirements: list[str]
    description: str


# ============================================================================
# Test definitions
# ============================================================================


class TestCreate(BaseModel):
    """Create an initially editable test."""

    name: str = Field(
        ...,
        min_length=1,
        max_length=255,
    )
    description: str | None = None
    metadata: dict[str, Any] = Field(
        default_factory=dict
    )


class TestUpdate(BaseModel):
    """Update mutable test configuration.

    Fields omitted from a PATCH request remain unchanged.

    Explicit null for target_id, benchmark_id, or seed may be interpreted by
    the service layer as clearing that value.
    """

    name: str | None = Field(
        default=None,
        min_length=1,
        max_length=255,
    )
    description: str | None = None

    target_id: str | None = None
    benchmark_id: str | None = None

    execution_config: dict[str, Any] | None = None
    seed: int | None = None

    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class TestSummary(BaseModel):
    """Summary representation of one test."""

    test_definition_id: str
    name: str
    configuration_status: str

    target_id: str | None
    benchmark_id: str | None

    metric_selection_mode: str

    created_at: datetime
    updated_at: datetime


class TestDetail(BaseModel):
    """Complete editable test configuration."""

    test_definition_id: str
    name: str
    description: str | None

    configuration_status: str

    target_id: str | None
    benchmark_id: str | None

    metric_selection_mode: str

    judge_config: dict[str, Any]
    retrieval_config: dict[str, Any]
    execution_config: dict[str, Any]

    seed: int | None
    tags: list[str]
    metadata: dict[str, Any]

    definition_hash: str | None

    created_at: datetime
    updated_at: datetime


# ============================================================================
# Test metric selection
# ============================================================================


class TestMetricSelectionUpdate(BaseModel):
    """Replace metric configuration belonging to a test."""

    mode: str = Field(
        default="EXPLICIT",
        pattern="^(EXPLICIT|ALL_AVAILABLE)$",
    )

    selected_metrics: list[str] = Field(
        default_factory=list
    )

    metric_parameters: dict[str, dict[str, Any]] = Field(
        default_factory=dict
    )

    judge_config: dict[str, Any] = Field(
        default_factory=dict
    )

    retrieval_config: dict[str, Any] = Field(
        default_factory=dict
    )


class TestMetricInfo(BaseModel):
    """One registered metric as seen from a particular test."""

    metric_id: str
    version: str
    scope: str
    description: str

    requirements: list[str]

    applicable: bool
    selected: bool

    unavailable_reason: str | None = None

    parameters: dict[str, Any] = Field(
        default_factory=dict
    )


class TestMetricsInfo(BaseModel):
    """Metric availability and selection for one test."""

    test_definition_id: str

    mode: str

    metrics: list[TestMetricInfo]

    selected_metric_ids: list[str]
    applicable_metric_ids: list[str]

    judge_config: dict[str, Any]
    retrieval_config: dict[str, Any]

    warnings: list[str] = Field(
        default_factory=list
    )


class MetricImportResult(BaseModel):
    """Result of importing portable YAML into a test configuration."""

    applied: bool

    mode: str

    selected_metrics: list[str]
    ignored_metrics: list[str]
    unavailable_metrics: list[str]

    detected_target_id: str | None = None
    detected_benchmark_id: str | None = None

    target_conflict: bool = False
    benchmark_conflict: bool = False

    warnings: list[str] = Field(
        default_factory=list
    )


# ============================================================================
# Test validation
# ============================================================================


class TestValidationResult(BaseModel):
    """Result of checking whether a test can start a run."""

    valid: bool
    configuration_status: str

    target_valid: bool
    benchmark_valid: bool
    metrics_valid: bool

    resolved_metric_ids: list[str] = Field(
        default_factory=list
    )

    errors: list[str] = Field(
        default_factory=list
    )

    warnings: list[str] = Field(
        default_factory=list
    )


# ============================================================================
# Evaluation runs
# ============================================================================


class RunSummary(BaseModel):
    """Run summary for listings."""

    run_id: str
    name: str

    status: str
    status_reason: str | None

    config_hash: str

    target_id: str | None
    benchmark_id: str | None
    test_definition_id: str | None

    started_at: datetime | None
    finished_at: datetime | None
    paused_at: datetime | None
    interrupted_at: datetime | None

    created_at: datetime
    updated_at: datetime


class RunDetail(BaseModel):
    """Detailed evaluation run information."""

    run_id: str
    name: str

    status: str
    status_reason: str | None

    config_hash: str

    target_id: str | None
    benchmark_id: str | None
    test_definition_id: str | None

    started_at: datetime | None
    finished_at: datetime | None
    paused_at: datetime | None
    interrupted_at: datetime | None

    seed: int | None
    rag_eval_version: str | None

    tags: list[str]
    metadata: dict[str, Any]

    created_at: datetime
    updated_at: datetime

    total_cases: int | None = None
    complete_cases: int | None = None
    failed_cases: int | None = None
    pending_cases: int | None = None
    running_cases: int | None = None


class RunStatus(BaseModel):
    """Lightweight run progress information."""

    run_id: str
    status: str
    status_reason: str | None = None

    total_cases: int
    complete_cases: int
    failed_cases: int
    pending_cases: int
    running_cases: int

    progress_percent: float

    started_at: datetime | None
    finished_at: datetime | None
    paused_at: datetime | None = None
    interrupted_at: datetime | None = None

    elapsed_seconds: float | None


class RunEventInfo(BaseModel):
    """One append-only run lifecycle event."""

    run_event_id: str
    run_id: str

    event_type: str
    payload: dict[str, Any]

    created_at: datetime


# ============================================================================
# Case execution / attempts
# ============================================================================


class CaseExecutionSummary(BaseModel):
    """Case execution summary for listings."""

    case_execution_id: str
    case_id: str
    status: str

    started_at: datetime | None
    finished_at: datetime | None

    attempt_count: int | None


class CaseExecutionDetail(BaseModel):
    """Detailed case execution information."""

    case_execution_id: str
    run_id: str
    case_id: str
    status: str

    started_at: datetime | None
    finished_at: datetime | None

    metadata: dict[str, Any]

    query: str | None = None
    reference_answer: str | None = None
    answerability: str | None = None

    tags: list[str] = Field(
        default_factory=list
    )


class AttemptSummary(BaseModel):
    """Attempt summary for listings."""

    attempt_id: str
    attempt_number: int
    status: str
    request_id: str

    started_at: datetime | None
    finished_at: datetime | None

    retryable: bool | None
    error_summary: str | None


class AttemptDetail(BaseModel):
    """Detailed attempt information."""

    attempt_id: str
    case_execution_id: str

    attempt_number: int
    request_id: str

    idempotency_key: str | None
    canonical_request_hash: str | None

    status: str

    started_at: datetime | None
    finished_at: datetime | None

    retryable: bool | None
    error_summary: str | None

    metadata: dict[str, Any]


# ============================================================================
# Target observations
# ============================================================================


class TargetObservationSummary(BaseModel):
    """Target observation summary."""

    observation_id: str
    request_id: str

    has_answer: bool
    answer_length: int | None

    retrieval_stage_count: int
    citation_count: int

    has_trace: bool
    has_usage: bool

    error_count: int

    created_at: datetime


class TargetObservationDetail(BaseModel):
    """Detailed target observation."""

    observation_id: str
    request_id: str

    case_execution_id: str
    attempt_id: str

    answer: dict[str, Any] | None
    retrieval: dict[str, Any] | None

    citations: list[dict[str, Any]]
    confidence: list[dict[str, Any]]

    trace: dict[str, Any] | None
    usage: dict[str, Any] | None

    errors: list[dict[str, Any]]
    warnings: list[dict[str, Any]]

    normalization_version: str

    created_at: datetime


# ============================================================================
# Metric results
# ============================================================================


class MetricResultSummary(BaseModel):
    """Metric result summary."""

    metric_id: str
    metric_version: str
    status: str

    has_value: bool
    value_summary: str | None


class MetricResultDetail(BaseModel):
    """Detailed individual metric result."""

    metric_result_id: str

    run_id: str
    case_execution_id: str | None
    case_id: str | None

    metric_id: str
    metric_version: str

    value: Any | None

    status: str
    reason: str | None

    details: dict[str, Any]
    payload: dict[str, Any]

    created_at: datetime


class AggregateResultSummary(BaseModel):
    """Aggregate metric result summary."""

    metric_id: str
    metric_version: str
    aggregation: str

    status: str

    value_summary: str | None


class AggregateResultDetail(BaseModel):
    """Detailed run-level aggregate metric result."""

    aggregate_metric_result_id: str

    run_id: str

    metric_id: str
    metric_version: str
    aggregation: str

    value: Any | None

    status: str
    reason: str | None

    details: dict[str, Any]

    created_at: datetime


class RunResultsResponse(BaseModel):
    """Individual and aggregate results belonging to one run."""

    run_id: str

    metrics: list[MetricResultDetail]
    aggregates: list[AggregateResultDetail]


# ============================================================================
# Reports / comparison / export
# ============================================================================


class RunReport(BaseModel):
    """Run report."""

    run_id: str
    run_name: str
    status: str

    target_id: str | None
    config_hash: str

    total_cases: int
    complete_cases: int
    failed_cases: int
    pending_cases: int

    answer_metrics: dict[str, Any]
    retrieval_metrics: dict[str, Any]
    citation_metrics: dict[str, Any]
    performance_metrics: dict[str, Any]
    usage_metrics: dict[str, Any]
    cost_metrics: dict[str, Any]
    reliability_metrics: dict[str, Any]

    started_at: datetime | None
    finished_at: datetime | None

    duration_seconds: float | None


class ComparisonResult(BaseModel):
    """Run comparison result."""

    run_a_id: str
    run_b_id: str

    compatibility_warnings: list[str]
    metric_comparisons: list[dict[str, Any]]
    summary: dict[str, Any]

    compared_at: datetime = Field(
        default_factory=datetime.utcnow
    )


class ExportRequest(BaseModel):
    """Request to export run results."""

    formats: list[str] = Field(
        default_factory=lambda: ["parquet", "json"]
    )

    include_raw_artifacts: bool = False


class ExportResult(BaseModel):
    """Export result."""

    run_id: str
    export_id: str
    status: str

    files: list[dict[str, Any]]

    download_url: str | None

    created_at: datetime


# ============================================================================
# Test/run-scoped errors
# ============================================================================


class ErrorDetail(BaseModel):
    """Structured evaluation error detail."""

    error_id: str

    category: str
    code: str
    message: str

    stage: str | None

    retryable: bool
    retry_after_ms: int | None
    http_status: int | None

    created_at: datetime
