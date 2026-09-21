"""Target management, configuration, capabilities, and protocol models."""

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
    TargetConfigurationStatus,
    TargetConnectionStatus,
)
from rag_eval.models.retrieval import RetrievalResult


# ---------------------------------------------------------------------------
# Target configuration and management
# ---------------------------------------------------------------------------


class SecretRef(CanonicalModel):
    """Reference to a secret stored outside persisted target configuration.

    Canonical target configuration must never contain resolved secret values.
    """

    secret_id: str
    name: str | None = None


class TargetAdapterSelection(CanonicalModel):
    """Select the base adapter used by a target configuration.

    Examples:
        openai_compatible
        anthropic
        rag_eval_protocol
        generic_http
    """

    type: str


class TargetConnectionConfig(CanonicalModel):
    """Connection settings supplied by target.yaml.

    Fields are intentionally optional because a base adapter may provide
    defaults. Resolution into EffectiveTargetConfig determines whether the
    final configuration is complete.
    """

    base_url: str | None = None
    timeout_seconds: float | None = Field(default=None, gt=0)
    verify_tls: bool | None = None

    # Non-secret headers may be specified directly. Secret-valued headers
    # are replaced with SecretRef during target configuration ingestion.
    headers: dict[str, str | SecretRef] = Field(default_factory=dict)

    metadata: JsonDict = Field(default_factory=dict)


class TargetAuthConfig(CanonicalModel):
    """Authentication references for an evaluator-managed target.

    Secret fields contain references only. Plaintext values may exist in the
    raw uploaded YAML temporarily, but must be extracted into SecretStore
    before canonical TargetConfig validation/persistence.
    """

    type: str | None = None

    bearer_token: SecretRef | None = Field(
        default=None,
        json_schema_extra={"secret": True},
    )
    api_key: SecretRef | None = Field(
        default=None,
        json_schema_extra={"secret": True},
    )
    auth_token: SecretRef | None = Field(
        default=None,
        json_schema_extra={"secret": True},
    )

    username: str | None = None
    password: SecretRef | None = Field(
        default=None,
        json_schema_extra={"secret": True},
    )

    # Supports authentication schemes not covered by the common fields.
    # Secret-detection policy must sanitize sensitive values before this
    # model is persisted.
    parameters: JsonDict = Field(default_factory=dict)


class TargetConfig(CanonicalModel):
    """Declared target configuration derived from target.yaml.

    This represents what the user explicitly configured.

    Three supported configuration levels:

    1. Base adapter only:
         adapter:
           type: openai_compatible

    2. Base adapter plus differences:
         adapter:
           type: openai_compatible
         overrides:
           query:
             endpoint: /generate

    3. Fully declarative target:
         adapter:
           type: generic_http
         protocol:
           ...

    This model must be safe to persist, return through the API, version,
    and display in the frontend. It therefore contains SecretRef objects,
    never resolved credentials.
    """

    schema_version: str = "1.0"

    adapter: TargetAdapterSelection

    connection: TargetConnectionConfig | None = None
    auth: TargetAuthConfig | None = None

    # Adapter-specific ordinary configuration, e.g. OpenAI model name.
    parameters: JsonDict = Field(default_factory=dict)

    # Differences from the selected adapter's built-in defaults.
    overrides: JsonDict = Field(default_factory=dict)

    # Full declarative protocol specification. Primarily intended for
    # generic/config-driven adapters.
    protocol: JsonDict | None = None

    metadata: JsonDict = Field(default_factory=dict)


class EffectiveTargetConfig(CanonicalModel):
    """Fully resolved configuration consumed by a target adapter.

    Produced by combining:
        adapter defaults
        + declared target configuration
        + target-specific overrides

    Secrets remain unresolved SecretRef objects here. Credential resolution
    occurs only immediately before adapter execution.
    """

    schema_version: str = "1.0"

    adapter_type: str

    connection: TargetConnectionConfig | None = None
    auth: TargetAuthConfig | None = None

    # Fully resolved protocol behavior after applying adapter defaults and
    # target-specific overrides.
    protocol: JsonDict = Field(default_factory=dict)

    # Adapter-specific settings that are not protocol mappings.
    parameters: JsonDict = Field(default_factory=dict)

    metadata: JsonDict = Field(default_factory=dict)


class TargetConfigVersion(CanonicalModel):
    """One immutable persisted version of target.yaml and its resolution."""

    version: int = Field(ge=1)

    # Immutable artifact containing the safe/versioned target.yaml.
    source_artifact: ArtifactRef

    # What the user declared after secret extraction.
    declared: TargetConfig

    # What adapter resolution produced and what execution will use.
    effective: EffectiveTargetConfig

    config_hash: str
    created_at: datetime

    _validate_created_at = field_validator("created_at")(
        validate_aware_timestamp
    )


class TargetAdapterDescriptor(CanonicalModel):
    """Metadata published by the adapter registry for API/frontend use."""

    type: str
    version: str | None = None
    description: str | None = None

    supports_overrides: bool = True
    supports_full_protocol: bool = False

    # Optional adapter defaults suitable for display/debugging.
    defaults: JsonDict = Field(default_factory=dict)

    metadata: JsonDict = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Target identity and capabilities exposed through the canonical protocol
# ---------------------------------------------------------------------------


class TargetInfo(CanonicalModel):
    """Identity exposed by a target or normalized by its adapter.

    Evaluator-owned identity such as target_id and adapter_type belongs to
    ManagedTarget rather than this protocol-level model.
    """

    name: str
    version: str | None = None
    implementation: str | None = None
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

    usage: UsageCapabilities = Field(
        default_factory=UsageCapabilities
    )
    retrieval_metadata: RetrievalMetadataCapabilities = Field(
        default_factory=RetrievalMetadataCapabilities
    )

    limits: dict[str, int] = Field(default_factory=dict)

    idempotency_retention_seconds: int | None = Field(
        default=None,
        ge=0,
    )

    metadata: JsonDict = Field(default_factory=dict)


class HealthStatus(CanonicalModel):
    """Operational health reported or normalized through the target adapter.

    This is distinct from TargetConnectionState, which records whether the
    evaluator itself could verify connectivity.
    """

    status: HealthState
    target: TargetInfo
    details: JsonDict = Field(default_factory=dict)


class TargetConnectionState(CanonicalModel):
    """Evaluator-observed connectivity state for a configured target."""

    status: TargetConnectionStatus = TargetConnectionStatus.NOT_TESTED

    checked_at: datetime | None = None
    last_successful_at: datetime | None = None

    # Present when a health mechanism exists and returned usable information.
    health: HealthStatus | None = None

    # Human/debug-friendly normalized failure information.
    error: JsonDict | None = None

    _validate_checked_at = field_validator("checked_at")(
        validate_aware_timestamp
    )
    _validate_last_successful_at = field_validator("last_successful_at")(
        validate_aware_timestamp
    )


class ManagedTarget(CanonicalModel):
    """Evaluator-owned representation of one registered target."""

    target_id: str
    name: str

    adapter_type: str | None = None

    configuration_status: TargetConfigurationStatus = (
        TargetConfigurationStatus.EMPTY
    )

    connection: TargetConnectionState = Field(
        default_factory=TargetConnectionState
    )

    current_config_version: int | None = Field(
        default=None,
        ge=1,
    )

    # Last successfully discovered/normalized capabilities.
    capabilities: TargetCapabilities | None = None
    capabilities_checked_at: datetime | None = None

    enabled: bool = True

    created_at: datetime
    updated_at: datetime

    metadata: JsonDict = Field(default_factory=dict)

    _validate_capabilities_checked_at = field_validator(
        "capabilities_checked_at"
    )(validate_aware_timestamp)

    _validate_created_at = field_validator("created_at")(
        validate_aware_timestamp
    )
    _validate_updated_at = field_validator("updated_at")(
        validate_aware_timestamp
    )


# ---------------------------------------------------------------------------
# Canonical target query/retrieval protocol
# ---------------------------------------------------------------------------


class AnswerSpan(CanonicalModel):
    """A half-open character range within a generated answer."""

    start_char: int = Field(ge=0)
    end_char: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_span(self) -> "AnswerSpan":
        """Ensure the end boundary is not before the start boundary."""
        if self.end_char < self.start_char:
            raise ValueError(
                "end_char must be greater than or equal to start_char"
            )
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
        """Validate documented confidence bounds when supplied."""
        if self.minimum is not None and self.maximum is not None:
            if self.minimum > self.maximum:
                raise ValueError("minimum must not exceed maximum")

            if not self.minimum <= self.value <= self.maximum:
                raise ValueError(
                    "value must be within the documented confidence range"
                )

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

    duration_ms: float | None = Field(
        default=None,
        ge=0,
    )

    attributes: JsonDict = Field(default_factory=dict)

    _validate_started_at = field_validator("started_at")(
        validate_aware_timestamp
    )
    _validate_ended_at = field_validator("ended_at")(
        validate_aware_timestamp
    )


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
    def validate_call_counts(
        cls,
        value: dict[str, int],
    ) -> dict[str, int]:
        """Reject negative target-side token and call counts."""

        if any(count < 0 for count in value.values()):
            raise ValueError("usage counts must be non-negative")

        return value


class ErrorRecord(CanonicalModel):
    """Normalized error envelope retained for recovery and reliability."""

    error_id: str
    category: ErrorCategory
    code: str
    message: str

    stage: str | None = None

    retryable: bool = False
    retry_after_ms: int | None = Field(
        default=None,
        ge=0,
    )

    http_status: int | None = Field(
        default=None,
        ge=100,
        le=599,
    )

    provider: JsonDict = Field(default_factory=dict)

    exception_type: str | None = None
    timestamp: datetime | None = None

    raw_artifact: ArtifactRef | None = None

    details: JsonDict = Field(default_factory=dict)

    _validate_timestamp = field_validator("timestamp")(
        validate_aware_timestamp
    )


class OperationProgress(CanonicalModel):
    """Informational progress for an asynchronous target operation."""

    value: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )

    stage: str | None = None
    current: int | None = Field(
        default=None,
        ge=0,
    )
    total: int | None = Field(
        default=None,
        ge=0,
    )
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

    _validate_started_at = field_validator("started_at")(
        validate_aware_timestamp
    )
    _validate_finished_at = field_validator("finished_at")(
        validate_aware_timestamp
    )


class Configuration(CanonicalModel):
    """Requested versus target-reported effective runtime configuration.

    This is execution-time target information and is intentionally distinct
    from evaluator-managed TargetConfig / EffectiveTargetConfig.
    """

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

    include: RetrieveInclude = Field(
        default_factory=RetrieveInclude
    )


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

    include: QueryInclude = Field(
        default_factory=QueryInclude
    )

    stream: bool = False

    @model_validator(mode="after")
    def validate_context_policy(self) -> "QueryRequest":
        """Require evaluator contexts only for supplied-context execution."""

        if self.context_policy is ContextPolicy.SUPPLIED_CONTEXT:
            if self.supplied_contexts is None:
                raise ValueError(
                    "SUPPLIED_CONTEXT requires supplied_contexts"
                )

        elif self.supplied_contexts is not None:
            raise ValueError(
                "supplied_contexts requires SUPPLIED_CONTEXT policy"
            )

        return self


class QueryResponse(CanonicalModel):
    """Canonical non-streaming result; null retrieval means not exposed."""

    protocol_version: str = "1.0"

    request_id: str
    status: RequestStatus = RequestStatus.COMPLETED

    answer: Answer | None = None
    retrieval: RetrievalResult | None = None

    confidence: list[ConfidenceSignal] = Field(
        default_factory=list
    )

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

    _validate_timestamp = field_validator("timestamp")(
        validate_aware_timestamp
    )


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

    confidence: list[ConfidenceSignal] = Field(
        default_factory=list
    )

    trace: Trace | None = None
    usage: Usage | None = None

    warnings: list[WarningRecord] = Field(default_factory=list)
    errors: list[ErrorRecord] = Field(default_factory=list)

    configuration: Configuration = Field(
        default_factory=Configuration
    )

    raw_request_artifact: ArtifactRef | None = None
    raw_response_artifact: ArtifactRef | None = None

    normalization_version: str = "1.0"

    created_at: datetime

    metadata: JsonDict = Field(default_factory=dict)

    _validate_created_at = field_validator("created_at")(
        validate_aware_timestamp
    )