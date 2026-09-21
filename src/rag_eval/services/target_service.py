"""Application service for evaluator-managed target lifecycle.

TargetService orchestrates:

- target registration
- target.yaml ingestion and versioning
- secret extraction
- adapter-default/override resolution
- runtime adapter construction
- connectivity testing
- capability discovery

It deliberately does not:

- implement target transports
- encrypt/decrypt secrets directly
- persist ORM objects directly
- prepare benchmark corpora
- execute benchmark cases
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol
from uuid import uuid4

import yaml
from pydantic import ValidationError

from rag_eval.adapters import (
    ResolvedTargetCredentials,
    TargetAdapter,
    TargetAdapterError,
    create_target_adapter,
)
from rag_eval.adapters.uploaded_python import (
    load_uploaded_python_adapter,
    validate_uploaded_python_source,
)
from rag_eval.artifacts import ArtifactService
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.target_models import (
    TargetConfigVersionRecord,
    TargetRecord,
)
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import (
    EffectiveTargetConfig,
    TargetAdapterSelection,
    TargetCapabilities,
    TargetConfig,
    TargetConnectionState,
)
from rag_eval.models.enums import (
    ArtifactType,
    TargetConfigurationStatus,
    TargetConnectionStatus,
)


class TargetConfigResolver(Protocol):
    """Resolve declared target configuration into executable configuration."""

    def resolve(
        self,
        config: TargetConfig,
    ) -> EffectiveTargetConfig:
        """Apply adapter defaults and target-specific overrides."""
        ...


class TargetSecretService(Protocol):
    """Secret operations required by TargetService."""

    async def extract_and_store(
        self,
        target_id: str,
        config: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Extract plaintext secrets and return secret-safe configuration.

        Returned data must contain SecretRef representations rather than
        plaintext credential values.
        """
        ...

    async def resolve_credentials(
        self,
        target_id: str,
        config: EffectiveTargetConfig,
    ) -> ResolvedTargetCredentials:
        """Resolve SecretRef values into transient runtime credentials."""
        ...


@dataclass(frozen=True)
class UploadedPythonAdapterSourceInfo:
    """Metadata describing the active uploaded Python adapter source."""

    filename: str
    artifact_id: str
    content_hash: str | None
    created_at: datetime | None


class TargetService:
    """Coordinate evaluator-managed target setup and runtime access."""

    def __init__(
        self,
        repository: TargetRepository,
        persistence_repository: PersistenceRepository,
        artifact_service: ArtifactService,
        secret_service: TargetSecretService,
        config_resolver: TargetConfigResolver,
    ) -> None:
        """Bind target persistence and configuration infrastructure."""

        self._repository = repository
        self._persistence_repository = persistence_repository
        self._artifact_service = artifact_service
        self._secret_service = secret_service
        self._config_resolver = config_resolver

    # ---------------------------------------------------------------------
    # Target registration
    # ---------------------------------------------------------------------

    async def create_target(
        self,
        name: str,
        *,
        target_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> TargetRecord:
        """Create an empty target that can later receive target.yaml."""

        resolved_target_id = target_id or f"tgt-{uuid4()}"

        target = await self._repository.create_target(
            target_id=resolved_target_id,
            name=name,
            metadata=metadata,
        )

        # Persist an explicit initial connection state so callers do not need
        # to infer it from absence of a row.
        await self._repository.persist_connection_state(
            resolved_target_id,
            TargetConnectionState(
                status=TargetConnectionStatus.NOT_TESTED,
            ),
        )

        return target

    async def get_target(
        self,
        target_id: str,
    ) -> TargetRecord | None:
        """Return one registered target."""

        return await self._repository.get_target(target_id)

    # ---------------------------------------------------------------------
    # Configuration
    # ---------------------------------------------------------------------

    async def save_configuration(
        self,
        target_id: str,
        yaml_content: str,
    ) -> TargetConfigVersionRecord:
        """Validate and persist a new immutable target configuration version.

        Processing order:

            raw target.yaml
                ↓
            parse YAML
                ↓
            extract/store plaintext secrets
                ↓
            safe config containing SecretRef values
                ↓
            TargetConfig validation
                ↓
            adapter defaults + overrides
                ↓
            EffectiveTargetConfig
                ↓
            sanitized target.yaml artifact
                ↓
            TargetConfigVersionRecord

        Plaintext secrets must never reach artifact storage or canonical
        configuration persistence.
        """

        target = await self._require_target(target_id)

        try:
            raw_mapping = self._parse_yaml(yaml_content)
        except ValueError:
            if target.current_config_version is None:
                await self._repository.set_configuration_status(
                    target_id,
                    TargetConfigurationStatus.INVALID,
                )
            raise

        # Must happen before TargetConfig validation because user-provided YAML
        # may contain plaintext values where canonical config requires
        # SecretRef objects.
        sanitized_mapping = await self._secret_service.extract_and_store(
            target_id,
            raw_mapping,
        )

        try:
            declared = TargetConfig.model_validate(sanitized_mapping)
            effective = self._config_resolver.resolve(declared)
        except (ValidationError, ValueError):
            if target.current_config_version is None:
                await self._repository.set_configuration_status(
                    target_id,
                    TargetConfigurationStatus.INVALID,
                )
            raise

        sanitized_yaml = yaml.safe_dump(
            declared.model_dump(
                mode="json",
                exclude_none=True,
            ),
            sort_keys=False,
            allow_unicode=True,
        )

        artifact = await self._artifact_service.put(
            sanitized_yaml.encode("utf-8"),
            ArtifactType.TARGET_CONFIG,
            content_type="application/yaml",
            metadata={
                "target_id": target_id,
                "filename": "target.yaml",
            },
        )

        next_version = (target.current_config_version or 0) + 1

        record = await self._repository.persist_config_version(
            config_version_id=f"tcfg-{uuid4()}",
            target_id=target_id,
            version=next_version,
            source_artifact_id=artifact.artifact_id,
            declared=declared,
            effective=effective,
        )

        # Configuration changed, therefore previous connectivity information
        # is no longer authoritative.
        await self._repository.persist_connection_state(
            target_id,
            TargetConnectionState(
                status=TargetConnectionStatus.NOT_TESTED,
            ),
        )

        return record

    async def get_declared_config(
        self,
        target_id: str,
    ) -> TargetConfig | None:
        """Return the current user-declared target configuration."""

        return await self._repository.load_current_declared_config(target_id)

    async def get_effective_config(
        self,
        target_id: str,
    ) -> EffectiveTargetConfig | None:
        """Return the current fully resolved target configuration."""

        return await self._repository.load_current_effective_config(target_id)

    async def get_configuration_yaml(
        self,
        target_id: str,
    ) -> str | None:
        """Return editable sanitized target.yaml for the current version."""

        version = await self._repository.get_current_config_version(target_id)

        if version is None:
            return None

        artifact = await self._persistence_repository.get_artifact(
            version.source_artifact_id
        )

        if artifact is None:
            raise KeyError(
                f"target configuration artifact not found: {version.source_artifact_id}"
            )

        content = await self._artifact_service.get(artifact)

        return content.decode("utf-8")

    async def get_config_version(
        self,
        target_id: str,
        version: int,
    ) -> TargetConfigVersionRecord:
        """Return one immutable target configuration version."""

        await self._require_target(target_id)

        record = await self._repository.get_config_version(
            target_id,
            version,
        )

        if record is None:
            raise KeyError(
                f"target configuration version not found: "
                f"{target_id} v{version}"
            )

        return record

    async def get_configuration_version_yaml(
        self,
        target_id: str,
        version: int,
    ) -> str:
        """Return sanitized target.yaml for one immutable config version."""

        record = await self.get_config_version(
            target_id,
            version,
        )

        artifact = await self._persistence_repository.get_artifact(
            record.source_artifact_id
        )

        if artifact is None:
            raise KeyError(
                "target configuration artifact not found: "
                f"{record.source_artifact_id}"
            )

        content = await self._artifact_service.get(
            artifact
        )

        return content.decode("utf-8")

    async def restore_configuration_version(
        self,
        target_id: str,
        version: int,
    ) -> TargetConfigVersionRecord:
        """Restore a historical configuration as a new immutable version.

        The historical declared/effective configuration and sanitized source
        artifact are reused exactly. This preserves SecretRef identities and
        avoids re-extracting or duplicating secrets.
        """

        target = await self._require_target(
            target_id
        )

        historical = await self.get_config_version(
            target_id,
            version,
        )

        declared = TargetConfig.model_validate(
            historical.declared_config
        )

        effective = EffectiveTargetConfig.model_validate(
            historical.effective_config
        )

        next_version = (
            (target.current_config_version or 0) + 1
        )

        record = await self._repository.persist_config_version(
            config_version_id=f"tcfg-{uuid4()}",
            target_id=target_id,
            version=next_version,
            source_artifact_id=historical.source_artifact_id,
            declared=declared,
            effective=effective,
        )

        # Restoring configuration changes the active runtime configuration,
        # therefore previous connectivity information is no longer authoritative.
        await self._repository.persist_connection_state(
            target_id,
            TargetConnectionState(
                status=TargetConnectionStatus.NOT_TESTED,
            ),
        )

        return record

    async def upload_python_adapter(
        self,
        target_id: str,
        content: bytes,
        *,
        filename: str = "target_adapter.py",
    ) -> UploadedPythonAdapterSourceInfo:
        """Configure a target directly from an uploaded Python adapter.

        The Python source and synthesized target configuration are persisted as
        separate artifacts:

        - TARGET_ADAPTER_SOURCE contains the executable Python source.
        - TARGET_CONFIG contains the synthesized sanitized configuration.

        The config version points to TARGET_CONFIG while its parameters contain
        the Python source artifact reference.
        """

        target = await self._require_target(
            target_id
        )

        if not filename.lower().endswith(".py"):
            raise ValueError(
                "Uploaded target adapter must be a .py file."
            )

        # Syntax validation only. Do not execute arbitrary code merely because
        # it has been uploaded.
        validate_uploaded_python_source(
            content,
            filename=filename,
        )

        source_artifact = await self._artifact_service.put(
            content,
            ArtifactType.TARGET_ADAPTER_SOURCE,
            content_type="text/x-python",
            metadata={
                "target_id": target_id,
                "filename": filename,
            },
        )

        declared = TargetConfig(
            adapter=TargetAdapterSelection(
                type="uploaded_python",
            ),
            parameters={
                "source_artifact_id": source_artifact.artifact_id,
                "filename": filename,
                "entrypoint": "create_adapter",
            },
        )

        effective = EffectiveTargetConfig(
            schema_version=declared.schema_version,
            adapter_type="uploaded_python",
            protocol={},
            parameters=dict(declared.parameters),
            metadata={},
        )

        # Config versions must always reference a configuration artifact.
        # The actual Python source remains referenced from declared/effective
        # parameters.source_artifact_id.
        sanitized_yaml = yaml.safe_dump(
            declared.model_dump(
                mode="json",
                exclude_none=True,
            ),
            sort_keys=False,
            allow_unicode=True,
        )

        config_artifact = await self._artifact_service.put(
            sanitized_yaml.encode("utf-8"),
            ArtifactType.TARGET_CONFIG,
            content_type="application/yaml",
            metadata={
                "target_id": target_id,
                "filename": "target.yaml",
                "adapter_source_artifact_id": source_artifact.artifact_id,
            },
        )

        next_version = (
            (target.current_config_version or 0) + 1
        )

        await self._repository.persist_config_version(
            config_version_id=f"tcfg-{uuid4()}",
            target_id=target_id,
            version=next_version,
            source_artifact_id=config_artifact.artifact_id,
            declared=declared,
            effective=effective,
        )

        await self._repository.persist_connection_state(
            target_id,
            TargetConnectionState(
                status=TargetConnectionStatus.NOT_TESTED,
            ),
        )

        return UploadedPythonAdapterSourceInfo(
            filename=filename,
            artifact_id=source_artifact.artifact_id,
            content_hash=source_artifact.sha256,
            created_at=source_artifact.created_at,
        )


    async def get_python_adapter_source(
        self,
        target_id: str,
    ) -> UploadedPythonAdapterSourceInfo | None:
        """Return metadata for the active uploaded Python adapter source."""

        await self._require_target(
            target_id
        )

        effective = await self._repository.load_current_effective_config(
            target_id
        )

        if (
            effective is None
            or effective.adapter_type != "uploaded_python"
        ):
            return None

        artifact_id = effective.parameters.get(
            "source_artifact_id"
        )

        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError(
                "uploaded_python configuration requires "
                "parameters.source_artifact_id."
            )

        artifact = await self._persistence_repository.get_artifact(
            artifact_id
        )

        if artifact is None:
            raise KeyError(
                f"uploaded Python adapter artifact not found: {artifact_id}"
            )

        filename_value = effective.parameters.get(
            "filename"
        )

        if isinstance(filename_value, str) and filename_value:
            filename = filename_value
        else:
            metadata_filename = artifact.metadata.get(
                "filename"
            )

            filename = (
                metadata_filename
                if isinstance(metadata_filename, str)
                else "target_adapter.py"
            )

        return UploadedPythonAdapterSourceInfo(
            filename=filename,
            artifact_id=artifact.artifact_id,
            content_hash=artifact.sha256,
            created_at=artifact.created_at,
        )


    # ---------------------------------------------------------------------
    # Runtime adapter construction
    # ---------------------------------------------------------------------

    async def get_adapter(
        self,
        target_id: str,
    ) -> TargetAdapter:
        """Construct a runtime adapter for the current target configuration."""

        target = await self._require_target(target_id)

        if not target.enabled:
            raise ValueError(f"target is disabled: {target_id}")

        effective = await self._repository.load_current_effective_config(target_id)

        if effective is None:
            raise ValueError(f"target has no active configuration: {target_id}")

        if effective.adapter_type == "uploaded_python":
            return await self._load_uploaded_python_adapter(effective)

        credentials = await self._secret_service.resolve_credentials(
            target_id,
            effective,
        )

        return create_target_adapter(
            effective,
            credentials,
        )

    # ---------------------------------------------------------------------
    # Connectivity
    # ---------------------------------------------------------------------

    async def test_connection(
        self,
        target_id: str,
    ) -> TargetConnectionState:
        """Test configured target connectivity and persist the result.

        Semantics:

        - no health mechanism -> UNVERIFIED
        - valid health response -> CONNECTED
        - timeout/network/protocol failure -> DISCONNECTED

        Capability discovery is attempted after successful adapter creation
        and persisted when available.
        """

        adapter: TargetAdapter | None = None

        try:
            adapter = await self.get_adapter(target_id)

            health = await adapter.health()

            now = datetime.now(UTC)

            if health is None:
                state = TargetConnectionState(
                    status=TargetConnectionStatus.UNVERIFIED,
                    checked_at=now,
                )
            else:
                state = TargetConnectionState(
                    status=TargetConnectionStatus.CONNECTED,
                    checked_at=now,
                    last_successful_at=now,
                    health=health,
                )

            await self._repository.persist_connection_state(
                target_id,
                state,
            )

            # Capability discovery is separate from health verification.
            # A target without health can therefore remain UNVERIFIED while
            # still exposing usable capabilities.
            try:
                capabilities = await adapter.capabilities()
            except TargetAdapterError:
                capabilities = None

            if capabilities is not None:
                await self._repository.persist_capabilities(
                    target_id,
                    capabilities,
                )

            return state

        except TargetAdapterError as exc:
            state = TargetConnectionState(
                status=TargetConnectionStatus.DISCONNECTED,
                checked_at=datetime.now(UTC),
                error=exc.to_error_record().model_dump(
                    mode="json",
                    exclude_none=True,
                ),
            )

            await self._repository.persist_connection_state(
                target_id,
                state,
            )

            return state

        except Exception as exc:
            # Configuration/adapter construction failures are persisted as
            # disconnected state without leaking credentials.
            state = TargetConnectionState(
                status=TargetConnectionStatus.DISCONNECTED,
                checked_at=datetime.now(UTC),
                error={
                    "code": "TARGET_CONNECTION_FAILED",
                    "message": str(exc),
                    "exception_type": type(exc).__name__,
                },
            )

            await self._repository.persist_connection_state(
                target_id,
                state,
            )

            return state

        finally:
            if adapter is not None:
                await self._close_adapter(adapter)

    async def get_connection_state(
        self,
        target_id: str,
    ) -> TargetConnectionState | None:
        """Return the most recently persisted connectivity state."""

        return await self._repository.get_connection_state(target_id)

    # ---------------------------------------------------------------------
    # Capabilities
    # ---------------------------------------------------------------------

    async def discover_capabilities(
        self,
        target_id: str,
    ) -> TargetCapabilities:
        """Discover and persist current normalized target capabilities."""

        adapter = await self.get_adapter(target_id)

        try:
            capabilities = await adapter.capabilities()

            await self._repository.persist_capabilities(
                target_id,
                capabilities,
            )

            return capabilities

        finally:
            await self._close_adapter(adapter)

    async def get_capabilities(
        self,
        target_id: str,
    ) -> TargetCapabilities | None:
        """Return the latest persisted target capabilities."""

        return await self._repository.get_capabilities(target_id)

    # ---------------------------------------------------------------------
    # Target lifecycle
    # ---------------------------------------------------------------------

    async def set_enabled(
        self,
        target_id: str,
        enabled: bool,
    ) -> TargetRecord:
        """Enable or disable a target."""

        return await self._repository.set_target_enabled(
            target_id,
            enabled,
        )

    # ---------------------------------------------------------------------
    # Basic CRUD
    # ---------------------------------------------------------------------

    async def list_targets(
        self,
    ) -> list[TargetRecord]:
        """Return all registered targets."""

        return await self._repository.list_targets()

    async def list_config_versions(
        self,
        target_id: str,
    ) -> list[TargetConfigVersionRecord]:
        """Return immutable configuration history."""

        await self._require_target(target_id)

        return await self._repository.list_config_versions(target_id)

    async def update_target(
        self,
        target_id: str,
        *,
        name: str | None = None,
        metadata: Mapping[str, Any] | None = None,
        enabled: bool | None = None,
    ) -> TargetRecord:
        """Update evaluator-owned mutable target properties."""

        target = await self._repository.update_target_identity(
            target_id,
            name=name,
            metadata=metadata,
        )

        if enabled is not None:
            target = await self._repository.set_target_enabled(
                target_id,
                enabled,
            )

        return target

    async def delete_target(
        self,
        target_id: str,
    ) -> None:
        """Delete a target and target-owned database state."""

        await self._require_target(target_id)

        await self._repository.delete_target(target_id)

    # ---------------------------------------------------------------------
    # Internal helpers
    # ---------------------------------------------------------------------

    async def _require_target(
        self,
        target_id: str,
    ) -> TargetRecord:
        """Return an existing target or raise a useful lookup error."""

        target = await self._repository.get_target(target_id)

        if target is None:
            raise KeyError(f"target not found: {target_id}")

        return target

    async def _load_uploaded_python_adapter(
        self,
        config: EffectiveTargetConfig,
    ) -> TargetAdapter:
        """Load a trusted Python adapter from its persisted source artifact."""

        artifact_id = config.parameters.get("source_artifact_id")

        if not isinstance(artifact_id, str) or not artifact_id:
            raise ValueError(
                "uploaded_python configuration requires parameters.source_artifact_id."
            )

        artifact = await self._persistence_repository.get_artifact(artifact_id)

        if artifact is None:
            raise KeyError(f"uploaded Python adapter artifact not found: {artifact_id}")

        source = await self._artifact_service.get(artifact)

        filename_value = config.parameters.get("filename")

        filename = (
            filename_value if isinstance(filename_value, str) else "target_adapter.py"
        )

        return load_uploaded_python_adapter(
            source,
            filename=filename,
        )

    @staticmethod
    def _parse_yaml(
        content: str,
    ) -> dict[str, Any]:
        """Parse one target.yaml document into a mapping."""

        try:
            parsed = yaml.safe_load(content)
        except yaml.YAMLError as exc:
            raise ValueError("target.yaml contains invalid YAML.") from exc

        if parsed is None:
            raise ValueError("target.yaml must not be empty.")

        if not isinstance(parsed, dict):
            raise ValueError("target.yaml root must be a mapping/object.")

        return parsed

    @staticmethod
    async def _close_adapter(
        adapter: TargetAdapter,
    ) -> None:
        """Close adapter-owned resources."""

        await adapter.aclose()
