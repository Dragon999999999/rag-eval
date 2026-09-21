"""Validated static configuration models for future rag-eval experiments."""

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl, model_validator

from rag_eval.models import CorpusMode, ErrorCategory

JsonDict = dict[str, Any]


class ExperimentModel(BaseModel):
    """Strict base model for static experiment configuration."""

    model_config = ConfigDict(extra="forbid")


class RunConfig(ExperimentModel):
    """User-selected identity and reproducibility options for a run."""

    name: str
    seed: int | None = None
    resume: bool = False
    tags: list[str] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)


class DatasetConfig(ExperimentModel):
    """Reference to benchmark input without performing dataset retrieval."""

    manifest: str | None = None
    dataset_id: str | None = None
    version: str | None = None

    @model_validator(mode="after")
    def validate_identifier(self) -> "DatasetConfig":
        """Require a manifest path or stable dataset identifier."""
        if self.manifest is None and self.dataset_id is None:
            raise ValueError("dataset requires manifest or dataset_id")
        return self


class CorpusConfig(ExperimentModel):
    """Target corpus settings shared by document, chunk, and external modes."""

    mode: CorpusMode
    corpus_id: str | None = None
    parameters: JsonDict = Field(default_factory=dict)


class ExperimentTargetConfig(ExperimentModel):
    """Transport-independent target selection and target-specific parameters."""

    adapter: Literal["http", "python"]
    base_url: HttpUrl | None = None
    python_target: str | None = None
    authentication_env: str | None = None
    corpus: CorpusConfig
    parameters: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_adapter_target(self) -> "ExperimentTargetConfig":
        """Require exactly the location mechanism appropriate to the adapter."""
        if self.adapter == "http":
            if self.base_url is None or self.python_target is not None:
                raise ValueError("http target requires base_url and no python_target")
        elif self.python_target is None or self.base_url is not None:
            raise ValueError("python target requires python_target and no base_url")
        return self


class RetryConfig(ExperimentModel):
    """Validated retry policy inputs; no retry behavior is executed here."""

    max_attempts: int = Field(default=3, ge=1)
    strategy: str = "exponential_jitter"
    initial_delay: float = Field(default=1.0, ge=0)
    maximum_delay: float = Field(default=30.0, ge=0)
    retryable_http_statuses: list[int] = Field(
        default_factory=lambda: [408, 429, 500, 502, 503, 504]
    )
    retryable_categories: list[ErrorCategory] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_delay_range(self) -> "RetryConfig":
        """Ensure the maximum backoff cannot precede its initial delay."""
        if self.maximum_delay < self.initial_delay:
            raise ValueError(
                "maximum_delay must be greater than or equal to initial_delay"
            )
        return self


class ExecutionConfig(ExperimentModel):
    """Future execution limits validated without beginning execution."""

    concurrency: int = Field(default=1, ge=1)
    connect_timeout: float = Field(default=10.0, gt=0)
    request_timeout: float = Field(default=60.0, gt=0)
    total_timeout: float = Field(default=120.0, gt=0)
    retry: RetryConfig = Field(default_factory=RetryConfig)


class JudgeConfig(ExperimentModel):
    """Future judge identity and parameters without any invocation behavior."""

    provider: str | None = None
    model: str | None = None
    parameters: JsonDict = Field(default_factory=dict)
    authentication_env: str | None = None


class MetricsConfig(ExperimentModel):
    """Metric-selection intent retained independently from metric execution."""

    mode: Literal["all_available", "explicit"] = "all_available"
    selected: list[str] = Field(default_factory=list)
    judge: JudgeConfig | None = None

    @model_validator(mode="after")
    def validate_selection(self) -> "MetricsConfig":
        """Require explicit metric IDs only when explicit mode is selected."""
        if self.mode == "explicit" and not self.selected:
            raise ValueError(
                "metrics.selected is required when metrics.mode is explicit"
            )
        return self


class DatabaseStorageConfig(ExperimentModel):
    """Database URL reference retained without resolving or exposing a secret."""

    url_env: str = "RAG_EVAL_DATABASE_URL"


class ArtifactStorageConfig(ExperimentModel):
    """S3-compatible artifact location and environment-variable references."""

    endpoint_env: str = "RAG_EVAL_S3_ENDPOINT_URL"
    bucket: str = "rag-eval-artifacts"
    access_key_env: str = "RAG_EVAL_S3_ACCESS_KEY"
    secret_key_env: str = "RAG_EVAL_S3_SECRET_KEY"
    region_env: str = "RAG_EVAL_S3_REGION"


class StorageConfig(ExperimentModel):
    """References for future PostgreSQL and object-storage integrations."""

    database: DatabaseStorageConfig = Field(default_factory=DatabaseStorageConfig)
    artifacts: ArtifactStorageConfig = Field(default_factory=ArtifactStorageConfig)


class PersistenceConfig(ExperimentModel):
    """Static persistence preferences that do not open persistence connections."""

    enabled: bool = True
    metadata: JsonDict = Field(default_factory=dict)


class OutputConfig(ExperimentModel):
    """Future output options that influence run artifacts, not execution state."""

    directory: str | None = None
    formats: list[str] = Field(default_factory=list)


class ExperimentConfig(ExperimentModel):
    """Complete static experiment definition accepted by validate and plan."""

    version: str
    run: RunConfig
    dataset: DatasetConfig
    target: ExperimentTargetConfig
    execution: ExecutionConfig = Field(default_factory=ExecutionConfig)
    metrics: MetricsConfig = Field(default_factory=MetricsConfig)
    storage: StorageConfig = Field(default_factory=StorageConfig)
    persistence: PersistenceConfig = Field(default_factory=PersistenceConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    matrix: dict[str, list[Any]] | None = None

    @model_validator(mode="after")
    def validate_matrix_values(self) -> "ExperimentConfig":
        """Reject empty matrix dimensions before planning combinations."""
        if self.matrix is not None:
            for path, values in self.matrix.items():
                if not path:
                    raise ValueError("matrix paths must not be empty")
                if not values:
                    raise ValueError(f"matrix.{path} must contain at least one value")
        return self
