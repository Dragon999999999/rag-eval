"""Async persistence repository for the evaluated-target domain.

This repository owns durable evaluator-side target state:

- registered target identity and lifecycle
- immutable target configuration versions
- encrypted target secret records
- latest connectivity state
- latest discovered capabilities
- prepared target corpora and documents
- normalized target observations

It deliberately does not perform:

- YAML parsing
- adapter-default resolution
- secret encryption/decryption
- target I/O
- connection testing
- capability discovery
- artifact byte storage

Those responsibilities belong to the configuration, secret, adapter, service,
and artifact layers respectively.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.target_models import (
    CorpusRecord,
    DocumentRecord,
    TargetCapabilityRecord,
    TargetConfigVersionRecord,
    TargetConnectionRecord,
    TargetObservationRecord,
    TargetRecord,
    TargetSecretRecord,
)
from rag_eval.models import (
    Document,
    EffectiveTargetConfig,
    TargetCapabilities,
    TargetConfig,
    TargetConnectionState,
    TargetObservation,
    target,
)
from rag_eval.models.enums import TargetConfigurationStatus


def _payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash canonical JSON payload content deterministically."""

    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )

    return hashlib.sha256(
        encoded.encode("utf-8")
    ).hexdigest()


def _target_config_hash(
    declared: TargetConfig,
    effective: EffectiveTargetConfig,
) -> str:
    """Hash the complete safe configuration identity.

    Both forms are included:

    - declared: what the user explicitly configured
    - effective: what adapter execution actually uses

    Secret values cannot appear here because canonical target configuration
    contains SecretRef values rather than resolved credentials.
    """

    payload = {
        "declared": declared.model_dump(
            mode="json",
            exclude_none=True,
        ),
        "effective": effective.model_dump(
            mode="json",
            exclude_none=True,
        ),
    }

    return _payload_hash(payload)


class TargetRepository:
    """Explicit target-domain persistence with caller-managed transactions."""

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        """Bind this repository to one caller-managed async session."""

        self._session = session

    # -------------------------------------------------------------------------
    # Registered targets
    # -------------------------------------------------------------------------

    async def create_target(
        self,
        target_id: str,
        name: str,
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> TargetRecord:
        """Create an empty evaluator-managed target.

        Newly created targets intentionally have no adapter/configuration yet.
        """

        existing = await self._session.get(
            TargetRecord,
            target_id,
        )

        if existing is not None:
            raise ValueError(
                f"target already exists: {target_id}"
            )

        record = TargetRecord(
            target_id=target_id,
            name=name,
            adapter_type=None,
            configuration_status=(
                TargetConfigurationStatus.EMPTY.value
            ),
            current_config_version=None,
            enabled=True,
            metadata_json=dict(metadata or {}),
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def get_target(
        self,
        target_id: str,
    ) -> TargetRecord | None:
        """Return one registered target."""

        return await self._session.get(
            TargetRecord,
            target_id,
        )

    async def list_targets(
        self,
    ) -> list[TargetRecord]:
        """Return registered targets in deterministic identity order."""

        result = await self._session.scalars(
            select(TargetRecord).order_by(
                TargetRecord.target_id
            )
        )

        return list(result.all())

    async def update_target_identity(
        self,
        target_id: str,
        *,
        name: str | None = None,
        adapter_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TargetRecord:
        """Update evaluator-owned target identity metadata."""

        target = await self._require_target(
            target_id
        )

        if name is not None:
            target.name = name

        if adapter_type is not None:
            target.adapter_type = adapter_type

        if metadata is not None:
            target.metadata_json = dict(metadata)

        await self._session.flush()

        return target

    async def set_target_enabled(
        self,
        target_id: str,
        enabled: bool,
    ) -> TargetRecord:
        """Enable or disable a registered target."""

        record = await self._require_target(
            target_id
        )

        record.enabled = enabled

        await self._session.flush()

        return record

    async def set_configuration_status(
        self,
        target_id: str,
        status: TargetConfigurationStatus,
    ) -> TargetRecord:
        """Update target configuration lifecycle state."""

        record = await self._require_target(
            target_id
        )

        record.configuration_status = status.value

        await self._session.flush()

        return record


    async def delete_target(
        self,
        target_id: str,
    ) -> None:
        """Delete a target and its target-owned persisted state."""

        target = await self._require_target(
            target_id
        )

        await self._session.delete(
            target
        )

        await self._session.flush()

    # -------------------------------------------------------------------------
    # Configuration versions
    # -------------------------------------------------------------------------

    async def persist_config_version(
        self,
        *,
        config_version_id: str,
        target_id: str,
        version: int,
        source_artifact_id: str,
        declared: TargetConfig,
        effective: EffectiveTargetConfig,
    ) -> TargetConfigVersionRecord:
        """Persist one immutable target configuration version.

        The caller must already have:

        1. parsed target.yaml,
        2. extracted plaintext secrets,
        3. replaced them with SecretRef values,
        4. persisted the sanitized YAML artifact,
        5. resolved adapter defaults and overrides.

        On success this method also updates the target's pointer to the
        current configuration version.
        """

        if version < 1:
            raise ValueError(
                "target configuration version must be >= 1"
            )

        target = await self._require_target(
            target_id
        )

        existing = await self._session.scalar(
            select(TargetConfigVersionRecord).where(
                TargetConfigVersionRecord.target_id
                == target_id,
                TargetConfigVersionRecord.version
                == version,
            )
        )

        if existing is not None:
            raise ValueError(
                f"target configuration version already exists: "
                f"{target_id} v{version}"
            )

        declared_payload = declared.model_dump(
            mode="json",
            exclude_none=True,
        )

        effective_payload = effective.model_dump(
            mode="json",
            exclude_none=True,
        )

        record = TargetConfigVersionRecord(
            config_version_id=config_version_id,
            target_id=target_id,
            version=version,
            source_artifact_id=source_artifact_id,
            schema_version=declared.schema_version,
            declared_config=declared_payload,
            effective_config=effective_payload,
            config_hash=_target_config_hash(
                declared,
                effective,
            ),
        )

        self._session.add(record)

        target.adapter_type = effective.adapter_type
        target.configuration_status = (
            TargetConfigurationStatus.CONFIGURED.value
        )
        target.current_config_version = version

        await self._session.flush()

        return record

    async def get_config_version(
        self,
        target_id: str,
        version: int,
    ) -> TargetConfigVersionRecord | None:
        """Return one immutable target configuration version."""

        return await self._session.scalar(
            select(TargetConfigVersionRecord).where(
                TargetConfigVersionRecord.target_id
                == target_id,
                TargetConfigVersionRecord.version
                == version,
            )
        )

    async def get_current_config_version(
        self,
        target_id: str,
    ) -> TargetConfigVersionRecord | None:
        """Return the target's currently selected configuration version."""

        target = await self._session.get(
            TargetRecord,
            target_id,
        )

        if (
            target is None
            or target.current_config_version is None
        ):
            return None

        return await self.get_config_version(
            target_id,
            target.current_config_version,
        )

    async def list_config_versions(
        self,
        target_id: str,
    ) -> list[TargetConfigVersionRecord]:
        """List target configuration history in version order."""

        result = await self._session.scalars(
            select(TargetConfigVersionRecord)
            .where(
                TargetConfigVersionRecord.target_id
                == target_id
            )
            .order_by(
                TargetConfigVersionRecord.version
            )
        )

        return list(result.all())

    async def load_current_declared_config(
        self,
        target_id: str,
    ) -> TargetConfig | None:
        """Reload the current declared configuration canonically."""

        record = await self.get_current_config_version(
            target_id
        )

        if record is None:
            return None

        return TargetConfig.model_validate(
            record.declared_config
        )

    async def load_current_effective_config(
        self,
        target_id: str,
    ) -> EffectiveTargetConfig | None:
        """Reload the current effective configuration canonically."""

        record = await self.get_current_config_version(
            target_id
        )

        if record is None:
            return None

        return EffectiveTargetConfig.model_validate(
            record.effective_config
        )

    # -------------------------------------------------------------------------
    # Secrets
    # -------------------------------------------------------------------------

    async def persist_secret(
        self,
        *,
        secret_id: str,
        target_id: str,
        name: str,
        encrypted_value: bytes,
        key_version: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TargetSecretRecord:
        """Persist or replace encrypted target secret material.

        Encryption happens outside this repository.

        ``secret_id`` remains stable when an existing secret is replaced so
        target configuration can continue referring to the same SecretRef.
        """

        await self._require_target(
            target_id
        )

        existing = await self._session.scalar(
            select(TargetSecretRecord).where(
                TargetSecretRecord.target_id
                == target_id,
                TargetSecretRecord.name
                == name,
            )
        )

        if existing is None:
            record = TargetSecretRecord(
                secret_id=secret_id,
                target_id=target_id,
                name=name,
                encrypted_value=encrypted_value,
                key_version=key_version,
                metadata_json=dict(metadata or {}),
            )

            self._session.add(record)

        else:
            if existing.secret_id != secret_id:
                raise ValueError(
                    f"secret name '{name}' already exists for target "
                    f"'{target_id}' with a different secret_id"
                )

            existing.encrypted_value = encrypted_value
            existing.key_version = key_version

            if metadata is not None:
                existing.metadata_json = dict(metadata)

            record = existing

        await self._session.flush()

        return record

    async def get_secret(
        self,
        secret_id: str,
    ) -> TargetSecretRecord | None:
        """Return encrypted secret material by stable secret identity."""

        return await self._session.get(
            TargetSecretRecord,
            secret_id,
        )

    async def get_secret_by_name(
        self,
        target_id: str,
        name: str,
    ) -> TargetSecretRecord | None:
        """Return encrypted secret material by target-local name."""

        return await self._session.scalar(
            select(TargetSecretRecord).where(
                TargetSecretRecord.target_id
                == target_id,
                TargetSecretRecord.name
                == name,
            )
        )

    async def list_secrets(
        self,
        target_id: str,
    ) -> Sequence[TargetSecretRecord]:
        """List secret metadata for one target.

        Callers must never expose ``encrypted_value`` through public APIs.
        """

        result = await self._session.scalars(
            select(TargetSecretRecord)
            .where(
                TargetSecretRecord.target_id
                == target_id
            )
            .order_by(
                TargetSecretRecord.name
            )
        )

        return result.all()

    async def delete_secret(
        self,
        secret_id: str,
    ) -> bool:
        """Delete one target secret.

        Configuration/service code is responsible for preventing deletion of
        a secret that is still required by the active target configuration.
        """

        record = await self._session.get(
            TargetSecretRecord,
            secret_id,
        )

        if record is None:
            return False

        await self._session.delete(record)
        await self._session.flush()

        return True

    # -------------------------------------------------------------------------
    # Connectivity
    # -------------------------------------------------------------------------

    async def persist_connection_state(
        self,
        target_id: str,
        state: TargetConnectionState,
    ) -> TargetConnectionRecord:
        """Persist the latest evaluator-observed target connectivity state."""

        await self._require_target(
            target_id
        )

        record = await self._session.get(
            TargetConnectionRecord,
            target_id,
        )

        health_payload = (
            state.health.model_dump(
                mode="json",
                exclude_none=True,
            )
            if state.health is not None
            else None
        )

        error_payload = (
            dict(state.error)
            if state.error is not None
            else None
        )

        if record is None:
            record = TargetConnectionRecord(
                target_id=target_id,
                status=state.status.value,
                checked_at=state.checked_at,
                last_successful_at=state.last_successful_at,
                health_payload=health_payload,
                error_json=error_payload,
            )

            self._session.add(record)

        else:
            record.status = state.status.value
            record.checked_at = state.checked_at
            record.last_successful_at = (
                state.last_successful_at
            )
            record.health_payload = health_payload
            record.error_json = error_payload

        await self._session.flush()

        return record

    async def get_connection_state(
        self,
        target_id: str,
    ) -> TargetConnectionState | None:
        """Reload latest evaluator-observed connectivity canonically."""

        record = await self._session.get(
            TargetConnectionRecord,
            target_id,
        )

        if record is None:
            return None

        return TargetConnectionState.model_validate(
            {
                "status": record.status,
                "checked_at": record.checked_at,
                "last_successful_at": (
                    record.last_successful_at
                ),
                "health": record.health_payload,
                "error": record.error_json,
            }
        )

    # -------------------------------------------------------------------------
    # Capabilities
    # -------------------------------------------------------------------------

    async def persist_capabilities(
        self,
        target_id: str,
        capabilities: TargetCapabilities,
    ) -> TargetCapabilityRecord:
        """Persist the latest canonical target capabilities."""

        await self._require_target(
            target_id
        )

        record = await self._session.get(
            TargetCapabilityRecord,
            target_id,
        )

        payload = capabilities.model_dump(
            mode="json",
            exclude_none=True,
        )

        if record is None:
            record = TargetCapabilityRecord(
                target_id=target_id,
                payload=payload,
            )

            self._session.add(record)

        else:
            record.payload = payload

        await self._session.flush()

        return record

    async def get_capabilities(
        self,
        target_id: str,
    ) -> TargetCapabilities | None:
        """Reload latest discovered capabilities canonically."""

        record = await self._session.get(
            TargetCapabilityRecord,
            target_id,
        )

        if record is None:
            return None

        return TargetCapabilities.model_validate(
            record.payload
        )

    # -------------------------------------------------------------------------
    # Prepared target corpora
    # -------------------------------------------------------------------------

    async def persist_corpus(
        self,
        record: CorpusRecord,
    ) -> CorpusRecord:
        """Persist target corpus identity and current preparation state."""

        if record.target_id is not None:
            await self._require_target(
                record.target_id
            )

        existing = await self._session.get(
            CorpusRecord,
            record.corpus_id,
        )

        if existing is None:
            self._session.add(record)

        else:
            existing.target_id = record.target_id
            existing.mode = record.mode
            existing.status = record.status
            existing.content_hash = record.content_hash
            existing.metadata_json = (
                record.metadata_json
            )

            record = existing

        await self._session.flush()

        return record

    async def persist_document(
        self,
        corpus_id: str,
        document: Document,
    ) -> DocumentRecord:
        """Persist a document uploaded into a target corpus."""

        corpus = await self._session.get(
            CorpusRecord,
            corpus_id,
        )

        if corpus is None:
            raise KeyError(
                f"target corpus not found: {corpus_id}"
            )

        record = await self._session.get(
            DocumentRecord,
            document.document_id,
        )

        values = {
            "corpus_id": corpus_id,
            "filename": document.filename,
            "mime_type": document.mime_type,
            "sha256": document.sha256,
            "size_bytes": document.size_bytes,
            "artifact_id": (
                document.artifact.artifact_id
                if document.artifact is not None
                else None
            ),
            "metadata_json": document.metadata,
        }

        if record is None:
            record = DocumentRecord(
                document_id=document.document_id,
                **values,
            )

            self._session.add(record)

        else:
            for name, value in values.items():
                setattr(
                    record,
                    name,
                    value,
                )

        await self._session.flush()

        return record

    # -------------------------------------------------------------------------
    # Target observations
    # -------------------------------------------------------------------------

    async def persist_observation(
        self,
        observation: TargetObservation,
        case_execution_id: str,
        attempt_id: str,
    ) -> TargetObservationRecord:
        """Persist one immutable normalized target observation."""

        payload = observation.model_dump(
            mode="json"
        )

        record = TargetObservationRecord(
            observation_id=(
                observation.observation_id
            ),
            request_id=observation.request_id,
            case_execution_id=case_execution_id,
            attempt_id=attempt_id,
            normalization_version=(
                observation.normalization_version
            ),
            payload=payload,
            payload_hash=_payload_hash(payload),
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def get_observation(
        self,
        observation_id: str,
    ) -> TargetObservation | None:
        """Reload one normalized target observation canonically."""

        record = await self._session.get(
            TargetObservationRecord,
            observation_id,
        )

        if record is None:
            return None

        return TargetObservation.model_validate(
            record.payload
        )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _require_target(
        self,
        target_id: str,
    ) -> TargetRecord:
        """Return an existing target or raise a domain-friendly lookup error."""

        record = await self._session.get(
            TargetRecord,
            target_id,
        )

        if record is None:
            raise KeyError(
                f"target not found: {target_id}"
            )

        return record