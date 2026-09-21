"""Environment-driven application configuration."""

from functools import lru_cache
from urllib.parse import quote_plus

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from rag_eval.config.hashing import canonicalize_config, configuration_hash
from rag_eval.config.loader import (
    ConfigurationError,
    load_experiment_config,
    resolve_environment_reference,
)
from rag_eval.config.matrix import PlannedExperiment, expand_matrix
from rag_eval.config.models import ExecutionConfig, ExperimentConfig, RetryConfig, ExperimentTargetConfig
from rag_eval.config.target_resolver import TargetConfigResolver


class Settings(BaseSettings):
    """Configuration for local and deployed rag-eval infrastructure.

    Values are loaded from environment variables prefixed with ``RAG_EVAL_``.
    The local defaults match the Compose services and are safe only for local
    development.
    """

    model_config = SettingsConfigDict(
        env_prefix="RAG_EVAL_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    environment: str = "development"
    debug: bool = False
    postgres_host: str = "localhost"
    postgres_port: int = 5433
    postgres_database: str = "rag_eval"
    postgres_user: str = "rag_eval"
    postgres_password: str = "rag_eval"
    database_url: str | None = None

    s3_endpoint_url: str = "http://localhost:9002"
    s3_access_key: str = "minioadmin"
    s3_secret_key: str = "minioadmin"
    s3_bucket: str = "rag-eval-artifacts"
    s3_region: str = "us-east-1"

    # API configuration
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000,http://localhost:5173,http://127.0.0.1:5173"
    api_key: str | None = None
    api_key_required: bool = False

    # Encryption key for target secrets stored in PostgreSQL.
    # Must be a Fernet-compatible key supplied through RAG_EVAL_SECRET_KEY.
    secret_key: str = ""

    @property
    def async_database_url(self) -> str:
        """Return the async PostgreSQL URL, honoring an explicit override."""
        if self.database_url is not None:
            return self.database_url

        username = quote_plus(self.postgres_user)
        password = quote_plus(self.postgres_password)
        database = quote_plus(self.postgres_database)
        return (
            "postgresql+asyncpg://"
            f"{username}:{password}@{self.postgres_host}:"
            f"{self.postgres_port}/{database}"
        )


@lru_cache
def get_settings() -> Settings:
    """Return the process-wide settings instance."""
    return Settings()


@model_validator(mode="after")
def validate_secret_key(self) -> "Settings":
    """Require the target-secret encryption key at application startup."""
    if not self.secret_key:
        raise ValueError(
            "RAG_EVAL_SECRET_KEY must be configured."
        )
    return self


__all__ = [
    "ConfigurationError",
    "ExecutionConfig",
    "ExperimentConfig",
    "PlannedExperiment",
    "RetryConfig",
    "Settings",
    "ExperimentTargetConfig",
    "TargetConfigResolver",
    "canonicalize_config",
    "configuration_hash",
    "expand_matrix",
    "get_settings",
    "load_experiment_config",
    "resolve_environment_reference",
]
