"""Pydantic schemas for API request/response models.

These are API presentation contracts, separate from canonical domain models.
They provide stable frontend-facing interfaces even as internal models evolve.
"""

from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

DataT = TypeVar("DataT")


class APIResponse(BaseModel, Generic[DataT]):
    """Standard API response wrapper."""

    success: bool = True
    data: DataT | None = None
    error: str | None = None
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class PaginationParams(BaseModel):
    """Common pagination parameters."""

    limit: int = Field(default=100, ge=1, le=1000)
    offset: int = Field(default=0, ge=0)


class PaginatedResponse(BaseModel, Generic[DataT]):
    """Paginated list response."""

    items: list[DataT]
    total: int
    limit: int
    offset: int
    has_more: bool


# ============================================================================
# Target Schemas
# ============================================================================


class TargetCreate(BaseModel):
    """Request to create a target."""

    name: str = Field(..., min_length=1, max_length=255)
    version: str | None = None
    implementation: str | None = None
    adapter: str = Field(..., pattern="^(http|python)$")
    base_url: str | None = None
    python_target: str | None = None
    authentication_env: str | None = None
    corpus_mode: str = Field(..., pattern="^(DOCUMENTS|CHUNKS|EXTERNAL)$")
    parameters: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TargetUpdate(BaseModel):
    """Request to update a target."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    version: str | None = None
    implementation: str | None = None
    parameters: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class TargetInfo(BaseModel):
    """Target identity information."""

    target_id: str
    name: str
    version: str | None
    implementation: str | None
    adapter: str
    base_url: str | None
    python_target: str | None
    authentication_env: str | None
    corpus_mode: str
    parameters: dict[str, Any]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime


class TargetCapabilities(BaseModel):
    """Target capability information."""

    target_id: str
    capabilities: dict[str, Any]
    discovered_at: datetime


# ============================================================================
# Benchmark Schemas
# ============================================================================


class BenchmarkCreate(BaseModel):
    """Create an empty benchmark."""

    name: str = Field(..., min_length=1, max_length=255)
    version: str = Field(default="1", min_length=1, max_length=64)
    corpus_mode: str = Field(
        default="DOCUMENTS",
        pattern="^(DOCUMENTS|CHUNKS|EXTERNAL)$",
    )


class BenchmarkInfo(BaseModel):
    """Canonical benchmark information."""

    benchmark_id: str
    name: str
    version: str
    schema_version: str
    corpus_mode: str
    content_hash: str | None
    corpus_id: str | None
    source: str | None
    tags: list[str]
    metadata: dict[str, Any]

    case_count: int
    document_count: int
    chunk_count: int

    is_complete: bool
    available_corpus_modes: list[str]

    created_at: datetime | None


class BenchmarkCaseSummary(BaseModel):
    """Benchmark case summary."""

    case_id: str
    query: str
    answerability: str | None
    tags: list[str]
    metadata: dict[str, Any]

    
# ============================================================================
# MetricConfig Schemas
# ============================================================================


class MetricConfigCreate(BaseModel):
    """Request to create a metric configuration."""

    name: str = Field(..., min_length=1, max_length=255)
    mode: str = Field(..., pattern="^(all_available|explicit)$")
    selected_metrics: list[str] = Field(default_factory=list)
    metric_parameters: dict[str, Any] = Field(default_factory=dict)
    judge_config: dict[str, Any] = Field(default_factory=dict)
    retrieval_config: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class MetricConfigUpdate(BaseModel):
    """Request to update a metric configuration."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    mode: str | None = None
    selected_metrics: list[str] | None = None
    metric_parameters: dict[str, Any] | None = None
    judge_config: dict[str, Any] | None = None
    retrieval_config: dict[str, Any] | None = None
    metadata: dict[str, Any] | None = None


class MetricConfigInfo(BaseModel):
    """Metric configuration information."""

    metric_config_id: str
    name: str
    mode: str
    selected_metrics: list[str]
    metric_parameters: dict[str, Any]
    judge_config: dict[str, Any]
    retrieval_config: dict[str, Any]
    metadata: dict[str, Any]
    config_hash: str
    created_at: datetime
    updated_at: datetime


class MetricDefinition(BaseModel):
    """Registered metric definition."""

    metric_id: str
    version: str
    scope: str
    requirements: list[dict[str, Any]]
    description: str


# ============================================================================
# TestDefinition Schemas
# ============================================================================


class TestDefinitionCreate(BaseModel):
    """Request to create a test definition."""

    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = None
    target_id: str
    benchmark_id: str
    metric_config_id: str
    execution_config: dict[str, Any] = Field(default_factory=dict)
    seed: int | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TestDefinitionUpdate(BaseModel):
    """Request to update a test definition."""

    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    target_id: str | None = None
    benchmark_id: str | None = None
    metric_config_id: str | None = None
    execution_config: dict[str, Any] | None = None
    seed: int | None = None
    tags: list[str] | None = None
    metadata: dict[str, Any] | None = None


class TestDefinitionInfo(BaseModel):
    """Test definition information."""

    test_definition_id: str
    name: str
    description: str | None
    target_id: str
    benchmark_id: str
    metric_config_id: str
    execution_config: dict[str, Any]
    seed: int | None
    tags: list[str]
    metadata: dict[str, Any]
    definition_hash: str
    created_at: datetime
    updated_at: datetime


class TestDefinitionPlan(BaseModel):
    """Test definition execution plan."""

    test_definition_id: str
    name: str
    description: str | None
    target: dict[str, Any]
    benchmark: dict[str, Any]
    metric_config: dict[str, Any]
    execution_config: dict[str, Any]
    seed: int | None
    config_hash: str
    tags: list[str]
    experiment_config: dict[str, Any]


class ValidationResult(BaseModel):
    """Validation result."""

    valid: bool
    structural_valid: bool
    capabilities_valid: bool | None
    errors: list[str]
    warnings: list[str]


# ============================================================================
# EvaluationRun Schemas
# ============================================================================


class CreateRunRequest(BaseModel):
    """Request to create/start an evaluation run."""

    test_definition_id: str | None = None
    name: str | None = None
    seed: int | None = None
    tags: list[str] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunSummary(BaseModel):
    """Run summary for listing."""

    run_id: str
    name: str
    status: str
    config_hash: str
    target_id: str | None
    test_definition_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    created_at: datetime


class RunDetail(BaseModel):
    """Detailed run information."""

    run_id: str
    name: str
    status: str
    config_hash: str
    target_id: str | None
    test_definition_id: str | None
    started_at: datetime | None
    finished_at: datetime | None
    seed: int | None
    rag_eval_version: str | None
    tags: list[str]
    metadata: dict[str, Any]
    created_at: datetime
    updated_at: datetime
    # Computed fields
    total_cases: int | None = None
    complete_cases: int | None = None
    failed_cases: int | None = None
    pending_cases: int | None = None


class RunStatus(BaseModel):
    """Run status information."""

    run_id: str
    status: str
    total_cases: int
    complete_cases: int
    failed_cases: int
    pending_cases: int
    running_cases: int
    progress_percent: float
    started_at: datetime | None
    finished_at: datetime | None
    elapsed_seconds: float | None


# ============================================================================
# CaseExecution Schemas
# ============================================================================


class CaseExecutionSummary(BaseModel):
    """Case execution summary for listing."""

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
    # Related data
    query: str | None = None
    reference_answer: str | None = None
    answerability: str | None = None
    tags: list[str] = Field(default_factory=list)


class AttemptSummary(BaseModel):
    """Attempt summary for listing."""

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
    metadata: dict[str, Any]


# ============================================================================
# Observation & Metrics Schemas
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


class MetricResultSummary(BaseModel):
    """Metric result summary."""

    metric_id: str
    metric_version: str
    status: str
    has_value: bool
    value_summary: str | None


class MetricResultDetail(BaseModel):
    """Detailed metric result."""

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
    """Detailed aggregate metric result."""

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


# ============================================================================
# Report & Comparison Schemas
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
    compared_at: datetime = Field(default_factory=datetime.utcnow)


class ExportRequest(BaseModel):
    """Request to export run results."""

    formats: list[str] = Field(default=["parquet", "json"])
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
# Error Schemas
# ============================================================================


class ErrorDetail(BaseModel):
    """Structured error detail."""

    error_id: str
    category: str
    code: str
    message: str
    stage: str | None
    retryable: bool
    retry_after_ms: int | None
    http_status: int | None
    created_at: datetime


class APIError(BaseModel):
    """API error response."""

    error: str
    detail: str | None = None
    code: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)
