"""Resolution of declared target configuration into effective configuration.

TargetConfig represents what the user explicitly wrote in target.yaml.

EffectiveTargetConfig represents the complete secret-safe configuration that
adapter construction will actually consume.

Resolution order:

    adapter defaults
        ↓
    explicit top-level target configuration
        ↓
    protocol declaration
        ↓
    protocol overrides

Merge semantics:

- mappings: recursively merged
- scalars: newer value replaces older value
- lists: newer list replaces older list completely
- null: explicitly replaces the previous value with null

Secrets remain SecretRef objects throughout resolution.
"""

from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from pydantic import ValidationError

from rag_eval.adapters.factory import (
    get_target_adapter_registration,
)
from rag_eval.models import (
    EffectiveTargetConfig,
    TargetConfig,
)


class TargetConfigResolver:
    """Resolve target.yaml configuration against registered adapter defaults."""

    def resolve(
        self,
        config: TargetConfig,
    ) -> EffectiveTargetConfig:
        """Return the complete effective configuration for one target."""

        registration = get_target_adapter_registration(
            config.adapter.type
        )

        defaults = deepcopy(
            dict(registration.defaults)
        )

        connection = self._resolve_optional_model_section(
            defaults.get("connection"),
            (
                config.connection.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                if config.connection is not None
                else None
            ),
        )

        auth = self._resolve_optional_model_section(
            defaults.get("auth"),
            (
                config.auth.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                if config.auth is not None
                else None
            ),
        )

        parameters = self._merge_mapping_sections(
            defaults.get("parameters"),
            config.parameters,
        )

        metadata = self._merge_mapping_sections(
            defaults.get("metadata"),
            config.metadata,
        )

        protocol = self._merge_mapping_sections(
            defaults.get("protocol"),
            config.protocol or {},
        )

        # "overrides" are intentionally protocol-level differences from the
        # selected base adapter. This enables concise Level-2 target.yaml:
        #
        # adapter:
        #   type: openai_compatible
        #
        # overrides:
        #   query:
        #     endpoint: /custom-generate
        #
        protocol = self._deep_merge(
            protocol,
            config.overrides,
        )

        payload: dict[str, Any] = {
            "schema_version": config.schema_version,
            "adapter_type": config.adapter.type,
            "protocol": protocol,
            "parameters": parameters,
            "metadata": metadata,
        }

        if connection is not None:
            payload["connection"] = connection

        if auth is not None:
            payload["auth"] = auth

        try:
            effective = EffectiveTargetConfig.model_validate(
                payload
            )
        except ValidationError as exc:
            raise ValueError(
                f"Unable to resolve target configuration "
                f"for adapter '{config.adapter.type}'."
            ) from exc

        # Run adapter-specific semantic validation after canonical Pydantic
        # validation.
        if registration.validator is not None:
            registration.validator(
                effective
            )

        return effective

    @classmethod
    def _resolve_optional_model_section(
        cls,
        defaults: Any,
        declared: Mapping[str, Any] | None,
    ) -> dict[str, Any] | None:
        """Resolve an optional structured configuration section."""

        if defaults is None and declared is None:
            return None

        default_mapping = (
            dict(defaults)
            if isinstance(defaults, Mapping)
            else {}
        )

        declared_mapping = (
            dict(declared)
            if declared is not None
            else {}
        )

        return cls._deep_merge(
            default_mapping,
            declared_mapping,
        )

    @classmethod
    def _merge_mapping_sections(
        cls,
        defaults: Any,
        declared: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Merge two mapping-valued configuration sections."""

        default_mapping = (
            dict(defaults)
            if isinstance(defaults, Mapping)
            else {}
        )

        return cls._deep_merge(
            default_mapping,
            declared,
        )

    @classmethod
    def _deep_merge(
        cls,
        base: Mapping[str, Any],
        override: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Recursively merge mappings using deterministic override semantics."""

        result: dict[str, Any] = deepcopy(
            dict(base)
        )

        for key, override_value in override.items():
            existing = result.get(
                key
            )

            if (
                isinstance(existing, Mapping)
                and isinstance(override_value, Mapping)
            ):
                result[key] = cls._deep_merge(
                    existing,
                    override_value,
                )
                continue

            # Scalars, lists, and explicit None replace the existing value.
            result[key] = deepcopy(
                override_value
            )

        return result