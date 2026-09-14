"""Target identity, advertised capabilities, health, and protocol request/response models."""

from datetime import datetime
from typing import Any

from pydantic import ConfigDict, Field, field_validator, model_validator

from rag_eval.models.benchmark import SuppliedContext
from rag_eval.models.common import (
    ArtifactRef,
    CanonicalModel,
    JsonDict,
    Message,
    SourceLocation,
    WarningRecord,
    validate_aware_timestamp,
)
from rag_eval.models.enums import (
    ContextPolicy,
    CorpusMode,
    ErrorCategory,
    FinishReason,
    HealthState,
    OperationStatus,
    RequestStatus,
)
from rag_eval.models.retrieval import RetrievalResult


class TargetInfo(CanonicalModel):
    """Identifying information for an evaluated target."""

    name: str
    version: str | None = None
    implementation: str | None = None
    target_id: str | None = None
    adapter_type: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class UsageCapabilities(CanonicalModel):
    """Usage information a target can expose."""

    tokens: bool = False
    cost: bool = False
    cpu: bool = False
    ram: bool = False
    gpu: bool = False
    vram: bool = False


class RetrievalMetadataCapabilities(CanonicalModel):
    """Retrieval metadata fields a target can expose per retrieved item."""

    rank: bool = False
    score: bool = False
    document_id: bool = False
    chunk_id: bool = False
    page: bool = False
    character_span: bool = False


class TargetCapabilities(CanonicalModel):
    """Optional operations and observations supported by a target."""

    model_config = ConfigDict(extra="ignore")

    protocol_version: str = "1.0"
    target: TargetInfo
    query: bool = False
    streaming: bool = False
    conversation_history: bool = False
    retrieval: bool = False
    retrieval_stages: bool = False
    document_ingestion: bool = False
    chunk_ingestion: bool = False
    context_injection: bool = False
    citations: bool = False
    confidence: bool = False
    target_trace: bool = False
    effective_configuration: bool = False
    idempotency: bool = False
    request_recovery: bool = False
    usage: UsageCapabilities = Field(default_factory=UsageCapabilities)
    retrieval_metadata: RetrievalMetadataCapabilities = Field(
        default_factory=RetrievalMetadataCapabilities
    )
    limits: dict[str, int] = Field(default_factory=dict)
    idempotency_retention_seconds: int | None = Field(default=None, ge=0)
    metadata: JsonDict = Field(default_factory=dict)


class HealthStatus(CanonicalModel):
    """Operational target health, separate from evaluation correctness."""

    status: HealthState
    target: TargetInfo
    details: JsonDict = Field(default_factory=dict)


class AnswerSpan(CanonicalModel):
    """A half-open character range within a generated answer."""

    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_span(self) -> "AnswerSpan":
        """Ensure the end boundary is not before the start boundary."""
        if self.end_char < self.start_char:
            raise ValueError("end_char must be greater than or equal to start_char")
        return self


class Citation(CanonicalModel):
    """Mapping from an answer span to source evidence."""

    citation_id: str
    answer_span: AnswerSpan | None = None
    source: SourceLocation | None = None
    retrieval_id: str | None = None
    display: str | None = None
    metadata: JsonDict = Field(default_factory=dict)


class ConfidenceSignal(CanonicalModel):
    """One target-provided confidence value with explicit scale semantics."""

    name: str
    value: float
    minimum: float | None = None
    maximum: float | None = None
    semantics: str | None = None
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_range(self) -> "ConfidenceSignal":
        """Validate documented confidence bounds when both limits are supplied."""
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("minimum must not exceed maximum")
            if not self.minimum <= self.value <= self.maximum:
                raise ValueError("value must be within the documented confidence range")
        return self


class Answer(CanonicalModel):
    """Generated answer retained even when partial or refused."""

    text: str
    finish_reason: FinishReason = FinishReason.UNKNOWN
    citations: list[Citation] = Field(default_factory=list)
    structured_output: Any | None = None
    metadata: JsonDict = Field(default_factory=dict)


class TraceSpan(CanonicalModel):
    """One target-reported span in a hierarchical execution trace."""

    span_id: str
    parent_span_id: str | None = None
    name: str
    started_at: datetime
    ended_at: datetime | None = None
    duration_ms: float | None = Field(default=None, ge=0)
    attributes: JsonDict = Field(default_factory=dict)

    _validate_started_at = field_validator("started_at")(validate_aware_timestamp)
    _validate_ended_at = field_validator("ended_at")(validate_aware_timestamp)


class Trace(CanonicalModel):
    """Hierarchical target trace retained separately from client timing."""

    trace_id: str | None = None
    spans: list[TraceSpan] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)


class Usage(CanonicalModel):
    """Optional target-reported token, cost, resource, and network usage."""

    tokens: dict[str, int] = Field(default_factory=dict)
    calls: dict[str, int] = Field(default_factory=dict)
    cost: JsonDict = Field(default_factory=dict)
    resources: JsonDict = Field(default_factory=dict)
    network: JsonDict = Field(default_factory=dict)
    metadata: JsonDict = Field(default_factory=dict)

    @field_validator("tokens", "calls")
    @classmethod
    def validate_call_counts(cls, value: dict[str, int]) -> dict[str, int]:
        """Reject negative target-side token and call counts."""
        if any(count < 0 for count in value.values()):
            raise ValueError("usage counts must be non-negative")
        return value


class ErrorRecord(CanonicalModel):
    """Normalized error envelope retained for recovery and reliability metrics."""

    error_id: str
    category: ErrorCategory
    code: str
    message: str
    stage: str | None = None
    retryable: bool = False
    retry_after_ms: int | None = Field(default=None, ge=0)
    http_status: int | None = Field(default=None, ge=100, le=599)
    provider: JsonDict = Field(default_factory=dict)
    exception_type: str | None = None
    timestamp: datetime | None = None
    raw_artifact: ArtifactRef | None = None
    details: JsonDict = Field(default_factory=dict)

    _validate_timestamp = field_validator("timestamp")(validate_aware_timestamp)


class OperationProgress(CanonicalModel):
    """Informational progress for an asynchronous target operation."""

    value: float | None = Field(default=None, ge=0, le=1)
    stage: str | None = None
    current: int | None = Field(default=None, ge=0)
    total: int | None = Field(default=None, ge=0)
    message: str | None = None


class Operation(CanonicalModel):
    """Target-side asynchronous work such as corpus ingestion or indexing."""

    operation_id: str
    kind: str
    status: OperationStatus
    progress: OperationProgress | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    result: JsonDict | None = None
    error: ErrorRecord | None = None

    _validate_started_at = field_validator("started_at")(validate_aware_timestamp)
    _validate_finished_at = field_validator("finished_at")(validate_aware_timestamp)


class Configuration(CanonicalModel):
    """Requested versus target-reported effective configuration."""

    requested: JsonDict = Field(default_factory=dict)
    effective: JsonDict = Field(default_factory=dict)


class CreateCorpusRequest(CanonicalModel):
    """Request for a target-owned evaluation corpus."""

    request_id: str
    name: str
    mode: CorpusMode
    parameters: JsonDict = Field(default_factory=dict)
    metadata: JsonDict = Field(default_factory=dict)


class CreateCorpusResponse(CanonicalModel):
    """Result of requesting target corpus creation."""

    corpus_id: str
    status: str
    configuration: Configuration | None = None


class RetrieveInclude(CanonicalModel):
    """Optional retrieval observations requested from a target."""

    stages: bool = True
    trace: bool = False
    usage: bool = False
    effective_configuration: bool = False


class RetrieveRequest(CanonicalModel):
    """Independent retrieval request that does not require generation."""

    request_id: str
    corpus_id: str | None = None
    query: str
    history: list[Message] = Field(default_factory=list)
    parameters: JsonDict = Field(default_factory=dict)
    filters: JsonDict = Field(default_factory=dict)
    include: RetrieveInclude = Field(default_factory=RetrieveInclude)


class RetrieveResponse(CanonicalModel):
    """Response from an independent retrieval request."""

    protocol_version: str = "1.0"
    request_id: str
    retrieval: RetrievalResult
    trace: Trace | None = None
    usage: Usage | None = None
    configuration: Configuration | None = None
    warnings: list[WarningRecord] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)


class QueryInclude(CanonicalModel):
    """Optional observations requested with a generation query."""

    retrieval: bool = True
    citations: bool = True
    confidence: bool = True
    trace: bool = True
    usage: bool = True
    effective_configuration: bool = True
    raw_prompt: bool = False


class QueryRequest(CanonicalModel):
    """Canonical generation request for a target."""

    request_id: str
    corpus_id: str | None = None
    query: str
    history: list[Message] = Field(default_factory=list)
    context_policy: ContextPolicy = ContextPolicy.TARGET_RETRIEVAL
    supplied_contexts: list[SuppliedContext] | None = None
    parameters: JsonDict = Field(default_factory=dict)
    include: QueryInclude = Field(default_factory=QueryInclude)
    stream: bool = False

    @model_validator(mode="after")
    def validate_context_policy(self) -> "QueryRequest":
        """Require evaluator contexts only for supplied-context execution."""
        if self.context_policy is ContextPolicy.SUPPLIED_CONTEXT:
            if self.supplied_contexts is None:
                raise ValueError("SUPPLIED_CONTEXT requires supplied_contexts")
        elif self.supplied_contexts is not None:
            raise ValueError("supplied_contexts requires SUPPLIED_CONTEXT policy")
        return self


class QueryResponse(CanonicalModel):
    """Canonical non-streaming result; null retrieval means not exposed."""

    protocol_version: str = "1.0"
    request_id: str
    status: RequestStatus = RequestStatus.COMPLETED
    answer: Answer | None = None
    retrieval: RetrievalResult | None = None
    confidence: list[ConfidenceSignal] = Field(default_factory=list)
    trace: Trace | None = None
    usage: Usage | None = None
    configuration: Configuration | None = None
    warnings: list[WarningRecord] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)


class QueryEvent(CanonicalModel):
    """One timestamped event in a streaming query response."""

    event_id: str
    request_id: str
    sequence: int = Field(ge=0)
    type: str
    timestamp: datetime
    data: JsonDict = Field(default_factory=dict)

    _validate_timestamp = field_validator("timestamp")(validate_aware_timestamp)


class RequestRecoveryResult(CanonicalModel):
    """A target's recovery lookup for a previously issued request."""

    request_id: str
    status: RequestStatus
    response: QueryResponse | None = None
    error: ErrorRecord | None = None


class TargetObservation(CanonicalModel):
    """Immutable normalized record of what an evaluated target did."""

    observation_id: str
    case_id: str
    request_id: str
    answer: Answer | None = None
    retrieval: RetrievalResult | None = None
    confidence: list[ConfidenceSignal] = Field(default_factory=list)
    trace: Trace | None = None
    usage: Usage | None = None
    warnings: list[WarningRecord] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)
    configuration: Configuration = Field(default_factory=Configuration)
    raw_request_artifact: ArtifactRef | None = None
    raw_response_artifact: ArtifactRef | None = None
    normalization_version: str = "1.0"
    created_at: datetime
    metadata: JsonDict = Field(default_factory=dict)

    _validate_created_at = field_validator("created_at")(validate_aware_timestamp)
