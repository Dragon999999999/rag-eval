"""PostgreSQL ORM records owned by the evaluated-target domain.

Canonical Pydantic models remain the executable configuration and protocol
schemas. These ORM records persist evaluator-owned target identity, target
configuration versions, connectivity state, discovered capabilities,
target-scoped secrets, corpora, documents, and normalized observations.

Important invariants:

- TargetRecord represents evaluator-owned target identity.
- Remote target-reported identity lives in TargetCapabilities/TargetInfo.
- Target configuration is versioned and immutable once persisted.
- Stored target configuration contains SecretRef values, never plaintext
  credentials.
- Plaintext credentials are encrypted before reaching TargetSecretRecord.
- Raw target.yaml artifacts must already be sanitized before persistence.
"""

from datetime import datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from rag_eval.db.base import Base


class TargetTimestampedRecord:
    """Creation timestamp shared by target-domain records."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ============================================================================
# Registered targets
# ============================================================================


class TargetRecord(Base, TargetTimestampedRecord):
    """Evaluator-owned identity and lifecycle state for one target.

    This record deliberately does not persist remote target-reported
    ``version`` or ``implementation`` fields. Those belong to canonical
    TargetInfo discovered through capabilities.
    """

    __tablename__ = "targets"

    target_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        index=True,
    )

    # Denormalized from the current effective configuration for efficient
    # target listing/filtering. None is valid before configuration.
    adapter_type: Mapped[str | None] = mapped_column(
        String(128),
        index=True,
    )

    configuration_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="empty",
        index=True,
    )

    # Version number within TargetConfigVersionRecord, not a target software
    # version.
    current_config_version: Mapped[int | None] = mapped_column(
        Integer,
    )

    enabled: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        nullable=False,
        index=True,
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


# ============================================================================
# Target configuration
# ============================================================================


class TargetConfigVersionRecord(Base, TargetTimestampedRecord):
    """One immutable version of a target's sanitized configuration.

    ``declared_config`` corresponds to canonical TargetConfig:
        what target.yaml explicitly declares after secret extraction.

    ``effective_config`` corresponds to EffectiveTargetConfig:
        adapter defaults + declared configuration + overrides.

    ``source_artifact_id`` points to the sanitized/versioned target.yaml.
    Plaintext secret values must never be written into that artifact.
    """

    __tablename__ = "target_config_versions"

    __table_args__ = (
        UniqueConstraint(
            "target_id",
            "version",
            name="uq_target_config_version",
        ),
    )

    config_version_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    target_id: Mapped[str] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    version: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
    )

    source_artifact_id: Mapped[str] = mapped_column(
        ForeignKey(
            "artifacts.artifact_id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    schema_version: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        default="1.0",
    )

    declared_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    effective_config: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        nullable=False,
    )

    config_hash: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        index=True,
    )


# ============================================================================
# Target secrets
# ============================================================================


class TargetSecretRecord(Base, TargetTimestampedRecord):
    """Encrypted target-scoped secret stored by the default SecretStore.

    ``encrypted_value`` contains ciphertext only. Encryption/decryption belongs
    to SecretStore and must use a key supplied outside PostgreSQL.

    The canonical target configuration references this record through
    SecretRef.secret_id.
    """

    __tablename__ = "target_secrets"

    __table_args__ = (
        UniqueConstraint(
            "target_id",
            "name",
            name="uq_target_secret_name",
        ),
    )

    secret_id: Mapped[str] = mapped_column(
        String(128),
        primary_key=True,
    )

    target_id: Mapped[str] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    name: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
    )

    encrypted_value: Mapped[bytes] = mapped_column(
        LargeBinary,
        nullable=False,
    )

    # Lets encryption keys/algorithms be rotated without changing SecretRef.
    key_version: Mapped[str | None] = mapped_column(
        String(64),
    )

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    metadata_json: Mapped[dict[str, Any]] = mapped_column(
        JSONB,
        default=dict,
        nullable=False,
    )


# ============================================================================
# Connectivity
# ============================================================================


class TargetConnectionRecord(Base, TargetTimestampedRecord):
    """Latest evaluator-observed connectivity state for one target.

    This is distinct from canonical HealthStatus:

    - HealthStatus is information reported/normalized by the target adapter.
    - This row records what happened when rag-eval attempted verification.

    Typical states:
        not_tested
        connected
        unverified
        disconnected
    """

    __tablename__ = "target_connections"

    target_id: Mapped[str] = mapped_column(
        ForeignKey(
            "targets.target_id",
            ondelete="CASCADE",
        ),
        primary_key=True,
    )

    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="not_tested",
        index=True,
    )

    checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    last_successful_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
    )

    # Canonical HealthStatus.model_dump(...) when health was available.
    health_payload: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
    )

    # Sanitized normalized connectivity/protocol error information.
    error_json: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB,
    )


# ============================================================================
# Capabilities
# ============================================================================


class TargetCapabilityRecord(Base, TargetTimestampedRecord):
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

    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )


# ============================================================================
# Target corpora
# ============================================================================


class CorpusRecord(Base, TargetTimestampedRecord):
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


class DocumentRecord(Base, TargetTimestampedRecord):
    """Document metadata for material uploaded into a target corpus.

    This remains separate from BenchmarkDocumentRecord. A benchmark document
    is evaluator-owned source material; this record represents target-side
    corpus ingestion.
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
# Target observations
# ============================================================================


class TargetObservationRecord(Base, TargetTimestampedRecord):
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