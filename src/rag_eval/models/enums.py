"""String-backed enums used by the canonical protocol."""

from enum import StrEnum


class CorpusMode(StrEnum):
    """How a target obtains a corpus."""

    DOCUMENTS = "DOCUMENTS"
    CHUNKS = "CHUNKS"
    EXTERNAL = "EXTERNAL"


class ContextPolicy(StrEnum):
    """How context reaches generation for a query."""

    TARGET_RETRIEVAL = "TARGET_RETRIEVAL"
    SUPPLIED_CONTEXT = "SUPPLIED_CONTEXT"
    NO_CONTEXT = "NO_CONTEXT"


class RetrievalStageType(StrEnum):
    """Canonical retrieval pipeline stage types."""

    CANDIDATE_RETRIEVAL = "CANDIDATE_RETRIEVAL"
    FUSION = "FUSION"
    RERANK = "RERANK"
    FILTER = "FILTER"
    COMPRESSION = "COMPRESSION"
    FINAL_CONTEXT = "FINAL_CONTEXT"
    CUSTOM = "CUSTOM"


class FinishReason(StrEnum):
    """Why answer generation stopped."""

    STOP = "STOP"
    LENGTH = "LENGTH"
    REFUSAL = "REFUSAL"
    CONTENT_FILTER = "CONTENT_FILTER"
    ERROR = "ERROR"
    CANCELLED = "CANCELLED"
    UNKNOWN = "UNKNOWN"


class ErrorCategory(StrEnum):
    """Normalized target and evaluator error categories."""

    VALIDATION = "VALIDATION"
    UNSUPPORTED_CAPABILITY = "UNSUPPORTED_CAPABILITY"
    AUTHENTICATION = "AUTHENTICATION"
    AUTHORIZATION = "AUTHORIZATION"
    NOT_FOUND = "NOT_FOUND"
    CONFLICT = "CONFLICT"
    NETWORK = "NETWORK"
    CONNECTION = "CONNECTION"
    TIMEOUT = "TIMEOUT"
    RATE_LIMIT = "RATE_LIMIT"
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    INGESTION = "INGESTION"
    RETRIEVAL = "RETRIEVAL"
    GENERATION = "GENERATION"
    INVALID_RESPONSE = "INVALID_RESPONSE"
    INTERNAL = "INTERNAL"
    UNKNOWN = "UNKNOWN"


class MetricStatus(StrEnum):
    """Outcome of one metric calculation."""

    COMPUTED = "COMPUTED"
    UNAVAILABLE_MISSING_INPUT = "UNAVAILABLE_MISSING_INPUT"
    NOT_APPLICABLE = "NOT_APPLICABLE"
    FAILED = "FAILED"
    SKIPPED = "SKIPPED"


class OperationStatus(StrEnum):
    """State of a target-side asynchronous operation."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RequestStatus(StrEnum):
    """Recoverable state of a logical target request."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    NOT_FOUND = "NOT_FOUND"


class Answerability(StrEnum):
    """Benchmark assessment of whether a case can be answered."""

    ANSWERABLE = "ANSWERABLE"
    UNANSWERABLE = "UNANSWERABLE"
    AMBIGUOUS = "AMBIGUOUS"
    UNKNOWN = "UNKNOWN"


class HealthState(StrEnum):
    """Operational readiness of an evaluated target."""

    READY = "READY"
    DEGRADED = "DEGRADED"
    NOT_READY = "NOT_READY"


class ClaimClassification(StrEnum):
    """Assessment of a claim against evidence."""

    SUPPORTED = "SUPPORTED"
    CONTRADICTED = "CONTRADICTED"
    UNSUPPORTED = "UNSUPPORTED"
    UNKNOWN = "UNKNOWN"


class EvidenceRelationship(StrEnum):
    """Relationship between a claim and one evidence item."""

    ENTAILS = "ENTAILS"
    CONTRADICTS = "CONTRADICTS"
    NEUTRAL = "NEUTRAL"
    UNKNOWN = "UNKNOWN"


class ArtifactType(StrEnum):
    """Purpose of externally stored immutable artifact bytes."""

    SOURCE_DOCUMENT = "SOURCE_DOCUMENT"
    TARGET_CONFIG = "TARGET_CONFIG"
    TARGET_ADAPTER_SOURCE = "TARGET_ADAPTER_SOURCE"
    RAW_TARGET_REQUEST = "RAW_TARGET_REQUEST"
    RAW_TARGET_RESPONSE = "RAW_TARGET_RESPONSE"
    STREAM_EVENTS = "STREAM_EVENTS"
    RAW_JUDGE_REQUEST = "RAW_JUDGE_REQUEST"
    RAW_JUDGE_RESPONSE = "RAW_JUDGE_RESPONSE"
    LOG = "LOG"
    PARQUET_EXPORT = "PARQUET_EXPORT"
    REPORT = "REPORT"
    OTHER = "OTHER"


class RunStatus(StrEnum):
    """Lifecycle state of a benchmark run."""

    PENDING = "PENDING"
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class CaseExecutionStatus(StrEnum):
    """Lifecycle state of one case execution within a run."""

    PENDING = "PENDING"
    RUNNING = "RUNNING"
    TARGET_COMPLETE = "TARGET_COMPLETE"
    SCORING = "SCORING"
    COMPLETE = "COMPLETE"
    FAILED = "FAILED"
    RETRY_PENDING = "RETRY_PENDING"
    UNKNOWN = "UNKNOWN"


class AttemptStatus(StrEnum):
    """State of one target attempt within a case execution."""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    RESPONSE_RECEIVED = "RESPONSE_RECEIVED"
    NORMALIZED = "NORMALIZED"
    SUCCEEDED = "SUCCEEDED"
    RETRYABLE_FAILURE = "RETRYABLE_FAILURE"
    PERMANENT_FAILURE = "PERMANENT_FAILURE"
    UNKNOWN_OUTCOME = "UNKNOWN_OUTCOME"


class QueryExecutionMode(StrEnum):
    """Execution mode for benchmark cases."""

    QUERY = "QUERY"
    RETRIEVAL = "RETRIEVAL"


class TargetConfigurationStatus(StrEnum):
    """State of evaluator-managed target configuration."""

    EMPTY = "empty"
    CONFIGURED = "configured"
    INVALID = "invalid"


class TargetConnectionStatus(StrEnum):
    """Evaluator-observed connectivity state for a configured target."""

    NOT_TESTED = "not_tested"
    CONNECTED = "connected"
    UNVERIFIED = "unverified"
    DISCONNECTED = "disconnected"