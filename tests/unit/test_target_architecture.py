"""Unit coverage for target configuration, adapters, and secret handling."""

from dataclasses import dataclass, field
from typing import Any

import pytest
from cryptography.fernet import Fernet

from rag_eval.adapters import (
    ResolvedTargetCredentials,
    create_target_adapter,
    get_target_adapter_registration,
    registered_target_adapters,
    target_adapter_descriptors,
)
from rag_eval.adapters.uploaded_python import (
    UploadedPythonAdapterError,
    load_uploaded_python_adapter,
    validate_uploaded_python_source,
)
from rag_eval.config.target_resolver import TargetConfigResolver
from rag_eval.models import (
    SecretRef,
    TargetAdapterSelection,
    TargetConfig,
)
from rag_eval.models.target import TargetAuthConfig, TargetConnectionConfig
from rag_eval.services.secret_service import SecretService


@dataclass
class StoredSecret:
    """Minimal encrypted secret record used by SecretService tests."""

    secret_id: str
    target_id: str
    name: str
    encrypted_value: bytes
    key_version: str | None = None
    metadata_json: dict[str, Any] = field(default_factory=dict)


class MemorySecretRepository:
    """Typed in-memory implementation of the target secret boundary."""

    def __init__(self) -> None:
        self.records: dict[str, StoredSecret] = {}

    async def get_secret_by_name(
        self, target_id: str, name: str
    ) -> StoredSecret | None:
        return next(
            (
                record
                for record in self.records.values()
                if record.target_id == target_id and record.name == name
            ),
            None,
        )

    async def get_secret(self, secret_id: str) -> StoredSecret | None:
        return self.records.get(secret_id)

    async def persist_secret(
        self,
        *,
        secret_id: str,
        target_id: str,
        name: str,
        encrypted_value: bytes,
        key_version: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> StoredSecret:
        record = StoredSecret(
            secret_id=secret_id,
            target_id=target_id,
            name=name,
            encrypted_value=encrypted_value,
            key_version=key_version,
            metadata_json=dict(metadata or {}),
        )
        self.records[secret_id] = record
        return record


def test_adapter_registry_descriptors_and_service_managed_entries() -> None:
    """The registry publishes deterministic descriptors and factory metadata."""
    names = registered_target_adapters()
    assert names == tuple(sorted(names))
    assert {"python", "rag_eval_protocol", "openai_compatible", "generic_http"} <= set(
        names
    )

    descriptors = {
        descriptor.type: descriptor for descriptor in target_adapter_descriptors()
    }
    assert descriptors["generic_http"].supports_full_protocol is True
    assert descriptors["uploaded_python"].supports_full_protocol is False
    assert get_target_adapter_registration("uploaded_python").factory is None


def test_target_config_resolver_applies_defaults_and_recursive_overrides() -> None:
    """Built-in defaults and recursive target overrides produce effective config."""
    declared = TargetConfig(
        adapter=TargetAdapterSelection(type="openai_compatible"),
        connection=TargetConnectionConfig(base_url="https://api.example.test"),
        parameters={"model": "test-model"},
        overrides={
            "query": {
                "endpoint": "v1/custom-chat",
                "headers": {"X-Test": "enabled"},
            }
        },
    )
    effective = TargetConfigResolver().resolve(declared)

    assert effective.adapter_type == "openai_compatible"
    assert effective.protocol["query"] == {
        "method": "POST",
        "endpoint": "v1/custom-chat",
        "headers": {"X-Test": "enabled"},
    }
    assert effective.connection is not None
    assert effective.connection.timeout_seconds == 60.0
    assert effective.parameters["model"] == "test-model"


def test_target_config_resolver_supports_full_generic_http_protocol() -> None:
    """generic_http accepts a complete declarative Level-3 protocol."""
    effective = TargetConfigResolver().resolve(
        TargetConfig(
            adapter=TargetAdapterSelection(type="generic_http"),
            connection=TargetConnectionConfig(base_url="https://target.test"),
            protocol={
                "health": {"method": "GET", "endpoint": "healthz"},
                "query": {
                    "method": "POST",
                    "endpoint": "answer",
                    "request_body": {"question": "query"},
                    "response_mapping": {"answer": "answer.text"},
                },
            },
        )
    )
    assert effective.protocol["health"]["endpoint"] == "healthz"
    assert effective.protocol["query"]["response_mapping"]["answer"] == "answer.text"


def test_target_config_resolver_rejects_unknown_and_incomplete_adapters() -> None:
    """Unknown adapters and incomplete generic declarations fail early."""
    with pytest.raises(ValueError, match="Unknown target adapter"):
        TargetConfigResolver().resolve(
            TargetConfig(adapter=TargetAdapterSelection(type="does-not-exist"))
        )
    with pytest.raises(ValueError, match="generic_http"):
        TargetConfigResolver().resolve(
            TargetConfig(
                adapter=TargetAdapterSelection(type="generic_http"),
                connection=TargetConnectionConfig(base_url="https://target.test"),
            )
        )


def test_factory_builds_native_protocol_adapter_from_effective_config() -> None:
    """Runtime factories consume EffectiveTargetConfig, not legacy config."""
    declared = TargetConfig(
        adapter=TargetAdapterSelection(type="rag_eval_protocol"),
        connection=TargetConnectionConfig(base_url="https://target.test"),
    )
    adapter = create_target_adapter(TargetConfigResolver().resolve(declared))
    assert adapter.__class__.__name__ == "HttpTargetAdapter"


def test_factory_builds_openai_and_generic_http_adapters() -> None:
    """Registry factories select concrete provider adapters from canonical config."""
    resolver = TargetConfigResolver()
    openai = resolver.resolve(
        TargetConfig(
            adapter=TargetAdapterSelection(type="openai_compatible"),
            connection=TargetConnectionConfig(base_url="https://target.test"),
            parameters={"model": "test-model"},
        )
    )
    generic = resolver.resolve(
        TargetConfig(
            adapter=TargetAdapterSelection(type="generic_http"),
            connection=TargetConnectionConfig(base_url="https://target.test"),
            protocol={
                "health": {"method": "GET", "endpoint": "health"},
                "query": {
                    "method": "POST",
                    "endpoint": "query",
                    "request_body": {"query": "query"},
                    "response_mapping": {"answer": "answer"},
                },
            },
        )
    )
    assert create_target_adapter(openai).__class__.__name__ == "OpenAICompatibleAdapter"
    assert (
        create_target_adapter(generic).__class__.__name__ == "GenericHttpTargetAdapter"
    )


@pytest.mark.anyio
async def test_secret_service_extracts_encrypts_and_preserves_references() -> None:
    """Plaintext secrets become encrypted stable references across edits."""
    repository = MemorySecretRepository()
    service = SecretService(repository, Fernet.generate_key())
    first = await service.extract_and_store(
        "target-1", {"auth": {"api_key": "first-secret"}}
    )
    reference = SecretRef.model_validate(first["auth"]["api_key"])
    stored = repository.records[reference.secret_id]

    assert reference.name == "auth.api_key"
    assert b"first-secret" not in stored.encrypted_value
    second = await service.extract_and_store(
        "target-1", {"auth": {"api_key": first["auth"]["api_key"]}}
    )
    assert second["auth"]["api_key"]["secret_id"] == reference.secret_id

    replaced = await service.replace_secret("target-1", reference, "second-secret")
    assert replaced.secret_id == reference.secret_id
    assert await service.resolve_secret("target-1", replaced) == "second-secret"


@pytest.mark.anyio
async def test_secret_service_rejects_cross_target_and_decrypt_failures() -> None:
    """Secret references are target-scoped and ciphertext failures are explicit."""
    repository = MemorySecretRepository()
    service = SecretService(repository, Fernet.generate_key())
    payload = await service.extract_and_store("target-1", {"token": "secret"})
    reference = SecretRef.model_validate(payload["token"])

    with pytest.raises(ValueError, match="does not belong"):
        await service.resolve_secret("target-2", reference)
    repository.records[reference.secret_id].encrypted_value = b"invalid-ciphertext"
    with pytest.raises(RuntimeError, match="unable to decrypt"):
        await service.resolve_secret("target-1", reference)
    with pytest.raises(ValueError, match="Invalid target-secret encryption key"):
        SecretService(repository, "not-a-fernet-key")


@pytest.mark.anyio
async def test_secret_service_resolves_runtime_credentials() -> None:
    """Runtime credential resolution decrypts auth and secret headers transiently."""
    repository = MemorySecretRepository()
    service = SecretService(repository, Fernet.generate_key())
    safe = await service.extract_and_store(
        "target-1",
        {
            "adapter": {"type": "openai_compatible"},
            "auth": {"api_key": "api-secret"},
            "connection": {
                "base_url": "https://target.test",
                "headers": {"authorization": "header-secret"},
            },
            "parameters": {"model": "test-model"},
        },
    )
    config = TargetConfig.model_validate(safe)
    effective = TargetConfigResolver().resolve(config)
    credentials = await service.resolve_credentials("target-1", effective)

    assert credentials.api_key == "api-secret"
    assert credentials.headers == {"authorization": "header-secret"}
    assert safe["auth"]["api_key"]["secret_id"] != "api-secret"


def test_uploaded_python_source_validates_syntax_and_interface() -> None:
    """Level-4 uploads require valid source and the complete adapter contract."""
    validate_uploaded_python_source(b"def create_adapter():\n    return object()\n")
    with pytest.raises(UploadedPythonAdapterError, match="invalid syntax"):
        validate_uploaded_python_source(b"def broken(:\n", filename="broken.py")
    with pytest.raises(UploadedPythonAdapterError, match="complete TargetAdapter"):
        load_uploaded_python_adapter(b"def create_adapter():\n    return object()\n")


def test_uploaded_python_adapter_loads_canonical_factory() -> None:
    """A complete uploaded adapter is loaded only through create_adapter()."""
    source = (
        b"from tests.unit.adapter_targets import FullCapabilityTarget\n"
        b"def create_adapter():\n"
        b"    return FullCapabilityTarget()\n"
    )
    adapter = load_uploaded_python_adapter(source)
    assert callable(getattr(adapter, "query", None))


def test_effective_config_keeps_secret_refs_unresolved() -> None:
    """Adapter resolution preserves SecretRef values until runtime credentials."""
    reference = SecretRef(secret_id="secret-1", name="auth.bearer_token")
    effective = TargetConfigResolver().resolve(
        TargetConfig(
            adapter=TargetAdapterSelection(type="rag_eval_protocol"),
            connection=TargetConnectionConfig(base_url="https://target.test"),
            auth=TargetAuthConfig(bearer_token=reference),
        )
    )
    assert effective.auth is not None
    assert effective.auth.bearer_token == reference
    assert ResolvedTargetCredentials(bearer_token="runtime-token").bearer_token == (
        "runtime-token"
    )
