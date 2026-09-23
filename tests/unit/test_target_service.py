"""Unit tests for evaluator-owned target lifecycle and configuration state."""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any

import pytest

from rag_eval.adapters import ResolvedTargetCredentials
from rag_eval.adapters.errors import TargetAdapterError
from rag_eval.config.target_resolver import TargetConfigResolver
from rag_eval.db.target_models import TargetConfigVersionRecord, TargetRecord
from rag_eval.models import (
    ArtifactRef,
    EffectiveTargetConfig,
    TargetCapabilities,
    TargetConfig,
    TargetConnectionState,
    TargetInfo,
)
from rag_eval.models.enums import (
    ArtifactType,
    TargetConfigurationStatus,
    TargetConnectionStatus,
)
from rag_eval.services.target_service import TargetService


class MemoryTargetRepository:
    """Typed in-memory target repository for service-level tests."""

    def __init__(self) -> None:
        self.targets: dict[str, TargetRecord] = {}
        self.versions: dict[str, list[TargetConfigVersionRecord]] = {}
        self.declared: dict[str, TargetConfig] = {}
        self.effective: dict[str, EffectiveTargetConfig] = {}
        self.connection: dict[str, TargetConnectionState] = {}
        self.capabilities: dict[str, TargetCapabilities] = {}
        self.deleted: set[str] = set()

    async def create_target(
        self,
        target_id: str,
        name: str,
        *,
        metadata: dict[str, Any] | None = None,
    ) -> TargetRecord:
        now = datetime.now(UTC)
        target = TargetRecord(
            target_id=target_id,
            name=name,
            configuration_status=TargetConfigurationStatus.EMPTY.value,
            enabled=True,
            metadata_json=dict(metadata or {}),
            created_at=now,
            updated_at=now,
        )
        self.targets[target_id] = target
        return target

    async def get_target(self, target_id: str) -> TargetRecord | None:
        return self.targets.get(target_id)

    async def list_targets(self) -> list[TargetRecord]:
        return list(self.targets.values())

    async def persist_connection_state(
        self,
        target_id: str,
        state: TargetConnectionState,
    ) -> None:
        self.connection[target_id] = state

    async def set_configuration_status(
        self,
        target_id: str,
        status: TargetConfigurationStatus,
    ) -> TargetRecord:
        target = self.targets[target_id]
        target.configuration_status = status.value
        return target

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
        payload = declared.model_dump(mode="json", exclude_none=True)
        resolved_payload = effective.model_dump(mode="json", exclude_none=True)
        record = TargetConfigVersionRecord(
            config_version_id=config_version_id,
            target_id=target_id,
            version=version,
            source_artifact_id=source_artifact_id,
            schema_version=declared.schema_version,
            declared_config=payload,
            effective_config=resolved_payload,
            config_hash=hashlib.sha256(
                repr((payload, resolved_payload)).encode()
            ).hexdigest(),
            created_at=datetime.now(UTC),
        )
        self.versions.setdefault(target_id, []).append(record)
        self.declared[target_id] = declared
        self.effective[target_id] = effective
        target = self.targets[target_id]
        target.adapter_type = effective.adapter_type
        target.configuration_status = TargetConfigurationStatus.CONFIGURED.value
        target.current_config_version = version
        return record

    async def load_current_declared_config(self, target_id: str) -> TargetConfig | None:
        return self.declared.get(target_id)

    async def load_current_effective_config(
        self,
        target_id: str,
    ) -> EffectiveTargetConfig | None:
        return self.effective.get(target_id)

    async def get_current_config_version(
        self,
        target_id: str,
    ) -> TargetConfigVersionRecord | None:
        versions = self.versions.get(target_id, [])
        return versions[-1] if versions else None

    async def list_config_versions(
        self,
        target_id: str,
    ) -> list[TargetConfigVersionRecord]:
        return list(self.versions.get(target_id, []))

    async def update_target_identity(
        self,
        target_id: str,
        *,
        name: str | None = None,
        adapter_type: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TargetRecord:
        target = self.targets[target_id]
        if name is not None:
            target.name = name
        if adapter_type is not None:
            target.adapter_type = adapter_type
        if metadata is not None:
            target.metadata_json = dict(metadata)
        return target

    async def set_target_enabled(self, target_id: str, enabled: bool) -> TargetRecord:
        target = self.targets[target_id]
        target.enabled = enabled
        return target

    async def delete_target(self, target_id: str) -> None:
        self.deleted.add(target_id)
        self.targets.pop(target_id, None)

    async def get_connection_state(
        self, target_id: str
    ) -> TargetConnectionState | None:
        return self.connection.get(target_id)

    async def persist_capabilities(
        self,
        target_id: str,
        capabilities: TargetCapabilities,
    ) -> None:
        self.capabilities[target_id] = capabilities

    async def get_capabilities(self, target_id: str) -> TargetCapabilities | None:
        return self.capabilities.get(target_id)


class MemoryPersistenceRepository:
    """Typed artifact metadata repository used by target service tests."""

    def __init__(self) -> None:
        self.artifacts: dict[str, ArtifactRef] = {}

    async def get_artifact(self, artifact_id: str) -> ArtifactRef | None:
        return self.artifacts.get(artifact_id)


class MemoryArtifactService:
    """Typed byte store that records sanitized configuration artifacts."""

    def __init__(self, persistence: MemoryPersistenceRepository) -> None:
        self.persistence = persistence
        self.content: dict[str, bytes] = {}
        self._counter = 0

    async def put(
        self,
        content: bytes,
        artifact_type: ArtifactType,
        **_: object,
    ) -> ArtifactRef:
        self._counter += 1
        artifact_id = f"artifact-{self._counter}"
        reference = ArtifactRef(
            artifact_id=artifact_id,
            uri=f"memory://{artifact_id}",
            content_type="application/yaml",
        )
        self.content[artifact_id] = content
        self.persistence.artifacts[artifact_id] = reference
        return reference

    async def get(self, artifact: ArtifactRef) -> bytes:
        return self.content[artifact.artifact_id]


class MemorySecretService:
    """Secret boundary that makes test credentials safe references."""

    async def extract_and_store(
        self,
        target_id: str,
        config: dict[str, Any],
    ) -> dict[str, Any]:
        _ = target_id
        return config

    async def resolve_credentials(
        self,
        target_id: str,
        config: EffectiveTargetConfig,
    ) -> ResolvedTargetCredentials:
        _ = target_id, config
        return ResolvedTargetCredentials()


class HealthAdapter:
    """Adapter double with configurable health behavior."""

    def __init__(self, mode: str) -> None:
        self.mode = mode

    async def health(self):
        if self.mode == "error":
            raise TargetAdapterError("connection refused")
        if self.mode == "unverified":
            return None
        from rag_eval.models import HealthStatus
        from rag_eval.models.enums import HealthState

        return HealthStatus(
            status=HealthState.READY,
            target=TargetInfo(name="fake-target"),
        )

    async def capabilities(self) -> TargetCapabilities:
        return TargetCapabilities(target=TargetInfo(name="fake-target"), query=True)

    async def aclose(self) -> None:
        return None


def _service() -> tuple[TargetService, MemoryTargetRepository, MemoryArtifactService]:
    persistence = MemoryPersistenceRepository()
    artifacts = MemoryArtifactService(persistence)
    repository = MemoryTargetRepository()
    service = TargetService(
        repository,
        persistence,  # type: ignore[arg-type]
        artifacts,  # type: ignore[arg-type]
        MemorySecretService(),  # type: ignore[arg-type]
        TargetConfigResolver(),
    )
    return service, repository, artifacts


@pytest.mark.anyio
async def test_target_lifecycle_and_configuration_versions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Create, configure, update, disable, and delete a target canonically."""
    service, repository, artifacts = _service()
    target = await service.create_target("Demo", target_id="target-1")
    assert target.configuration_status == TargetConfigurationStatus.EMPTY.value
    assert repository.connection["target-1"].status is TargetConnectionStatus.NOT_TESTED

    yaml_content = """
adapter:
  type: openai_compatible
connection:
  base_url: https://example.test
parameters:
  model: first
"""
    first = await service.save_configuration("target-1", yaml_content)
    second = await service.save_configuration(
        "target-1", yaml_content.replace("first", "second")
    )
    assert (first.version, second.version) == (1, 2)
    assert (await service.get_target("target-1")).current_config_version == 2  # type: ignore[union-attr]
    assert b"first" in artifacts.content[first.source_artifact_id]
    assert b"second" in artifacts.content[second.source_artifact_id]
    assert (await service.get_configuration_yaml("target-1")).find("second") >= 0  # type: ignore[union-attr]

    await service.update_target("target-1", name="Renamed", metadata={"owner": "qa"})
    await service.set_enabled("target-1", False)
    assert (await service.get_target("target-1")).enabled is False  # type: ignore[union-attr]
    await service.set_enabled("target-1", True)
    await service.delete_target("target-1")
    assert "target-1" in repository.deleted


@pytest.mark.anyio
async def test_target_configuration_invalid_state_and_connection_states(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid configuration and all evaluator-observed connection states persist."""
    service, repository, _ = _service()
    await service.create_target("Demo", target_id="target-1")

    with pytest.raises(ValueError):
        await service.save_configuration("target-1", "adapter: [broken")
    assert (
        repository.targets["target-1"].configuration_status
        == TargetConfigurationStatus.INVALID.value
    )

    valid_yaml = """
adapter:
  type: openai_compatible
connection:
  base_url: https://example.test
parameters:
  model: test-model
"""
    await service.save_configuration("target-1", valid_yaml)

    import rag_eval.services.target_service as target_module

    for mode, expected in (
        ("connected", TargetConnectionStatus.CONNECTED),
        ("unverified", TargetConnectionStatus.UNVERIFIED),
        ("error", TargetConnectionStatus.DISCONNECTED),
    ):
        monkeypatch.setattr(
            target_module,
            "create_target_adapter",
            lambda _config, _credentials, mode=mode: HealthAdapter(mode),
        )
        state = await service.test_connection("target-1")
        assert state.status is expected


@pytest.mark.anyio
async def test_uploaded_python_adapter_creates_internal_versioned_configuration() -> (
    None
):
    """Python uploads persist source bytes and a canonical adapter configuration."""
    service, repository, artifacts = _service()
    await service.create_target("Uploaded", target_id="target-upload")

    await service.upload_python_adapter(
        "target-upload",
        b"def create_adapter():\n    return object()\n",
        filename="adapter.py",
    )

    target = await service.get_target("target-upload")
    assert target is not None
    assert target.adapter_type == "uploaded_python"
    assert target.configuration_status == TargetConfigurationStatus.CONFIGURED.value
    version = await repository.get_current_config_version("target-upload")
    assert version is not None
    source_artifact_id = version.declared_config["parameters"]["source_artifact_id"]
    assert artifacts.content[source_artifact_id].startswith(b"def create_adapter")
    assert source_artifact_id.encode() in artifacts.content[version.source_artifact_id]
