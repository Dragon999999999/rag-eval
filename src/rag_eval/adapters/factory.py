"""Registry and construction of evaluated-target adapters.

This module is the single source of truth for built-in and registered target
adapters.

Each registration contains:

- adapter factory
- adapter defaults
- human-facing descriptor metadata
- optional effective-configuration validation

TargetConfigResolver consumes the same registry used by adapter construction,
preventing configuration defaults and runtime adapter selection from drifting
apart.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from copy import deepcopy
from dataclasses import dataclass
from typing import Any

from rag_eval.adapters.base import (
    ResolvedTargetCredentials,
    TargetAdapter,
)
from rag_eval.adapters.generic_http import GenericHttpTargetAdapter
from rag_eval.adapters.http import HttpTargetAdapter
from rag_eval.adapters.loader import load_python_target
from rag_eval.adapters.openai_compatible import OpenAICompatibleAdapter
from rag_eval.adapters.python import PythonTargetAdapter
from rag_eval.models import (
    EffectiveTargetConfig,
    SecretRef,
    TargetAdapterDescriptor,
)


AdapterFactory = Callable[
    [EffectiveTargetConfig, ResolvedTargetCredentials],
    TargetAdapter,
]

AdapterValidator = Callable[
    [EffectiveTargetConfig],
    None,
]


@dataclass(frozen=True, slots=True)
class TargetAdapterRegistration:
    """One registered target-adapter implementation and its defaults."""

    adapter_type: str
    factory: AdapterFactory | None

    defaults: Mapping[str, Any]

    description: str | None = None
    version: str | None = None

    supports_overrides: bool = True
    supports_full_protocol: bool = False

    validator: AdapterValidator | None = None

    def descriptor(self) -> TargetAdapterDescriptor:
        """Return public adapter metadata suitable for API/frontend use."""

        return TargetAdapterDescriptor(
            type=self.adapter_type,
            version=self.version,
            description=self.description,
            supports_overrides=self.supports_overrides,
            supports_full_protocol=self.supports_full_protocol,
            defaults=deepcopy(dict(self.defaults)),
        )


_ADAPTERS: dict[str, TargetAdapterRegistration] = {}


# ============================================================================
# Registry
# ============================================================================


def register_target_adapter(
    adapter_type: str,
    factory: AdapterFactory | None,
    *,
    defaults: Mapping[str, Any] | None = None,
    description: str | None = None,
    version: str | None = None,
    supports_overrides: bool = True,
    supports_full_protocol: bool = False,
    validator: AdapterValidator | None = None,
    replace: bool = False,
) -> None:
    """Register one target adapter and its configuration defaults."""

    normalized_type = adapter_type.strip()

    if not normalized_type:
        raise ValueError(
            "adapter_type must not be empty."
        )

    if (
        normalized_type in _ADAPTERS
        and not replace
    ):
        raise ValueError(
            f"Target adapter '{normalized_type}' "
            "is already registered."
        )

    _ADAPTERS[normalized_type] = TargetAdapterRegistration(
        adapter_type=normalized_type,
        factory=factory,
        defaults=deepcopy(dict(defaults or {})),
        description=description,
        version=version,
        supports_overrides=supports_overrides,
        supports_full_protocol=supports_full_protocol,
        validator=validator,
    )


def get_target_adapter_registration(
    adapter_type: str,
) -> TargetAdapterRegistration:
    """Return one adapter registration or raise for an unknown type."""

    registration = _ADAPTERS.get(
        adapter_type
    )

    if registration is None:
        available = ", ".join(
            sorted(_ADAPTERS)
        )

        raise ValueError(
            f"Unknown target adapter type '{adapter_type}'. "
            f"Available adapters: {available or 'none'}."
        )

    return registration


def registered_target_adapters() -> tuple[str, ...]:
    """Return all registered adapter names deterministically."""

    return tuple(
        sorted(_ADAPTERS)
    )


def target_adapter_descriptors(
) -> tuple[TargetAdapterDescriptor, ...]:
    """Return public descriptors for all registered adapters."""

    return tuple(
        _ADAPTERS[name].descriptor()
        for name in sorted(_ADAPTERS)
    )


# ============================================================================
# Runtime construction
# ============================================================================


def create_target_adapter(
    config: EffectiveTargetConfig,
    credentials: ResolvedTargetCredentials | None = None,
) -> TargetAdapter:
    """Construct the selected ordinary target adapter."""

    registration = get_target_adapter_registration(
        config.adapter_type
    )

    if registration.validator is not None:
        registration.validator(
            config
        )

    if registration.factory is None:
        raise ValueError(
            f"Target adapter '{config.adapter_type}' "
            "requires service-managed construction."
        )

    resolved_credentials = (
        credentials
        if credentials is not None
        else ResolvedTargetCredentials()
    )

    _validate_required_credentials(
        config,
        resolved_credentials,
    )

    return registration.factory(
        config,
        resolved_credentials,
    )


# ============================================================================
# Generic credential validation
# ============================================================================


def _validate_required_credentials(
    config: EffectiveTargetConfig,
    credentials: ResolvedTargetCredentials,
) -> None:
    """Ensure configured secret references were resolved before construction."""

    auth = config.auth

    if auth is not None:
        if (
            auth.bearer_token is not None
            and credentials.bearer_token is None
        ):
            raise ValueError(
                "Configured bearer_token SecretRef "
                "was not resolved."
            )

        if (
            auth.api_key is not None
            and credentials.api_key is None
        ):
            raise ValueError(
                "Configured api_key SecretRef "
                "was not resolved."
            )

    connection = config.connection

    if connection is None:
        return

    for name, value in connection.headers.items():
        if (
            isinstance(value, SecretRef)
            and name not in credentials.headers
        ):
            raise ValueError(
                f"Configured secret header '{name}' "
                "was not resolved."
            )


# ============================================================================
# Built-in factories
# ============================================================================


def _python_factory(
    config: EffectiveTargetConfig,
    credentials: ResolvedTargetCredentials,
) -> TargetAdapter:
    """Construct the in-process Python adapter."""

    del credentials

    import_path = config.parameters.get(
        "python_target"
    )

    if not isinstance(import_path, str) or not import_path:
        raise ValueError(
            "python adapter requires "
            "parameters.python_target."
        )

    return PythonTargetAdapter(
        load_python_target(
            import_path
        )
    )


def _rag_eval_protocol_factory(
    config: EffectiveTargetConfig,
    credentials: ResolvedTargetCredentials,
) -> TargetAdapter:
    """Construct the Rag-Eval Target Protocol v1 HTTP adapter."""

    connection = config.connection

    if (
        connection is None
        or connection.base_url is None
    ):
        raise ValueError(
            "rag_eval_protocol adapter requires "
            "connection.base_url."
        )

    headers: dict[str, str] = {}

    for name, value in connection.headers.items():
        if isinstance(value, str):
            headers[name] = value
            continue

        resolved = credentials.headers.get(
            name
        )

        if resolved is None:
            raise ValueError(
                f"Secret header '{name}' "
                "was not resolved."
            )

        headers[name] = resolved

    headers.update(
        credentials.headers
    )

    timeout = (
        connection.timeout_seconds
        or 60.0
    )

    verify_tls = (
        True
        if connection.verify_tls is None
        else connection.verify_tls
    )

    health_endpoint: str | None = "health"

    health_spec = config.protocol.get(
        "health"
    )

    if health_spec is None:
        health_endpoint = None

    elif isinstance(health_spec, Mapping):
        configured_endpoint = health_spec.get(
            "endpoint"
        )

        if configured_endpoint is None:
            health_endpoint = None

        elif isinstance(configured_endpoint, str):
            health_endpoint = configured_endpoint

        else:
            raise ValueError(
                "protocol.health.endpoint must be "
                "a string or null."
            )

    return HttpTargetAdapter(
        str(connection.base_url),
        request_timeout=timeout,
        bearer_token=credentials.bearer_token,
        api_key=credentials.api_key,
        api_key_header=credentials.api_key_header,
        headers=headers,
        verify_tls=verify_tls,
        health_endpoint=health_endpoint,
    )


def _openai_compatible_factory(
    config: EffectiveTargetConfig,
    credentials: ResolvedTargetCredentials,
) -> TargetAdapter:
    """Construct an OpenAI-compatible adapter."""

    return OpenAICompatibleAdapter(
        config,
        credentials,
    )


def _generic_http_factory(
    config: EffectiveTargetConfig,
    credentials: ResolvedTargetCredentials,
) -> TargetAdapter:
    """Construct a declarative generic HTTP adapter."""

    return GenericHttpTargetAdapter(
        config,
        credentials,
    )


# ============================================================================
# Built-in configuration validators
# ============================================================================


def _validate_http_connection(
    config: EffectiveTargetConfig,
) -> None:
    """Require a base URL for network-backed adapters."""

    if (
        config.connection is None
        or config.connection.base_url is None
    ):
        raise ValueError(
            f"{config.adapter_type} adapter requires "
            "connection.base_url."
        )


def _validate_openai_compatible(
    config: EffectiveTargetConfig,
) -> None:
    """Validate required OpenAI-compatible settings."""

    _validate_http_connection(
        config
    )

    model = config.parameters.get(
        "model"
    )

    if not isinstance(model, str) or not model:
        raise ValueError(
            "openai_compatible adapter requires "
            "parameters.model."
        )


def _validate_python(
    config: EffectiveTargetConfig,
) -> None:
    """Validate required local Python adapter settings."""

    import_path = config.parameters.get(
        "python_target"
    )

    if not isinstance(import_path, str) or not import_path:
        raise ValueError(
            "python adapter requires "
            "parameters.python_target."
        )


def _validate_generic_http(
    config: EffectiveTargetConfig,
) -> None:
    """Validate the minimum generic HTTP configuration."""

    _validate_http_connection(
        config
    )

    if not config.protocol:
        raise ValueError(
            "generic_http adapter requires "
            "a protocol configuration."
        )


# ============================================================================
# Built-in registrations
# ============================================================================


register_target_adapter(
    "python",
    _python_factory,
    defaults={
        "protocol": {},
        "parameters": {},
        "metadata": {},
    },
    description=(
        "In-process Python implementation of the "
        "canonical target protocol."
    ),
    version="1",
    supports_overrides=False,
    supports_full_protocol=False,
    validator=_validate_python,
)


register_target_adapter(
    "rag_eval_protocol",
    _rag_eval_protocol_factory,
    defaults={
        "connection": {
            "timeout_seconds": 60.0,
            "verify_tls": True,
            "headers": {},
            "metadata": {},
        },
        "protocol": {
            "health": {
                "method": "GET",
                "endpoint": "health",
            },
        },
        "parameters": {},
        "metadata": {},
    },
    description=(
        "Native Rag-Eval Target Protocol v1 over HTTP."
    ),
    version="1",
    supports_overrides=True,
    supports_full_protocol=False,
    validator=_validate_http_connection,
)


register_target_adapter(
    "openai_compatible",
    _openai_compatible_factory,
    defaults={
        "connection": {
            "timeout_seconds": 60.0,
            "verify_tls": True,
            "headers": {},
            "metadata": {},
        },
        "protocol": {
            "query": {
                "method": "POST",
                "endpoint": "chat/completions",
            },
        },
        "parameters": {},
        "metadata": {},
    },
    description=(
        "OpenAI-compatible chat-completions HTTP API."
    ),
    version="1",
    supports_overrides=True,
    supports_full_protocol=False,
    validator=_validate_openai_compatible,
)


register_target_adapter(
    "generic_http",
    _generic_http_factory,
    defaults={
        "connection": {
            "timeout_seconds": 60.0,
            "verify_tls": True,
            "headers": {},
            "metadata": {},
        },
        "protocol": {},
        "parameters": {},
        "metadata": {},
    },
    description=(
        "Declaratively configured JSON HTTP target."
    ),
    version="1",
    supports_overrides=True,
    supports_full_protocol=True,
    validator=_validate_generic_http,
)


register_target_adapter(
    "uploaded_python",
    None,
    defaults={
        "protocol": {},
        "parameters": {},
        "metadata": {},
    },
    description=(
        "Trusted user-supplied Python TargetAdapter."
    ),
    version="1",
    supports_overrides=False,
    supports_full_protocol=False,
)