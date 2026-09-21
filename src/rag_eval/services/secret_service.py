"""Target secret extraction, encryption, persistence, and runtime resolution.

SecretService is the application-layer boundary for target credentials.

Responsibilities:

- detect plaintext secrets in incoming target configuration
- encrypt and persist those values through TargetRepository
- replace plaintext values with canonical SecretRef objects
- preserve existing SecretRef values during configuration editing
- decrypt SecretRef values only for transient adapter construction

It deliberately does not:

- persist target configuration
- parse YAML
- create target adapters
- expose plaintext secrets through public APIs

The encryption key must be supplied outside PostgreSQL, normally through an
environment variable or deployment secret.
"""

from __future__ import annotations

import hashlib
import re
from collections.abc import Mapping, Sequence
from typing import Any
from uuid import uuid4

from cryptography.fernet import Fernet, InvalidToken

from rag_eval.adapters import ResolvedTargetCredentials
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import EffectiveTargetConfig, SecretRef


# Exact normalized field names treated as secrets automatically.
#
# Do not include overly broad names such as "key", "secret", or "credential",
# because they produce too many false positives in arbitrary configuration.
_SECRET_FIELD_NAMES = frozenset(
    {
        "password",
        "passphrase",
        "token",
        "access_token",
        "refresh_token",
        "auth_token",
        "bearer_token",
        "api_key",
        "apikey",
        "client_secret",
        "secret_key",
        "private_key",
        "authorization",
        "proxy_authorization",
        "x_api_key",
    }
)


_SECRET_FIELD_SUFFIXES = (
    "_password",
    "_passphrase",
    "_token",
    "_api_key",
    "_client_secret",
    "_secret_key",
    "_private_key",
)


class SecretService:
    """Manage target-scoped secrets without exposing plaintext persistence."""

    def __init__(
        self,
        repository: TargetRepository,
        encryption_key: str | bytes,
    ) -> None:
        """Create the service using one externally supplied Fernet key.

        ``encryption_key`` must be a URL-safe base64-encoded 32-byte Fernet
        key. It should normally come from an environment/deployment secret
        rather than source control or PostgreSQL.
        """

        if isinstance(encryption_key, str):
            key = encryption_key.encode("ascii")
        else:
            key = encryption_key

        try:
            self._cipher = Fernet(key)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                "Invalid target-secret encryption key. "
                "Expected a Fernet-compatible URL-safe base64 key."
            ) from exc

        self._repository = repository

        # Useful for recording which application encryption key produced a
        # ciphertext without storing the key itself.
        self._key_version = hashlib.sha256(key).hexdigest()[:16]

    # ---------------------------------------------------------------------
    # Configuration ingestion
    # ---------------------------------------------------------------------

    async def extract_and_store(
        self,
        target_id: str,
        config: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Extract secrets from raw configuration and return safe configuration.

        Supported forms include automatic detection:

            auth:
              bearer_token: abc123

        which becomes approximately:

            auth:
              bearer_token:
                secret_id: sec-...
                name: auth.bearer_token

        Existing references survive unchanged:

            auth:
              bearer_token:
                secret_id: sec-123
                name: auth.bearer_token

        Explicit marking is also supported for custom fields:

            provider:
              unusual_credential:
                secret: true
                value: abc123

        The returned mapping is safe for canonical TargetConfig validation
        and durable persistence.
        """

        result = await self._sanitize_value(
            target_id=target_id,
            value=dict(config),
            path=(),
            field_name=None,
        )

        if not isinstance(result, dict):
            raise TypeError(
                "Sanitized target configuration must remain a mapping."
            )

        return result

    async def _sanitize_value(
        self,
        *,
        target_id: str,
        value: Any,
        path: tuple[str, ...],
        field_name: str | None,
    ) -> Any:
        """Recursively replace plaintext secret material with SecretRef data."""

        # Existing SecretRef from a previously sanitized target.yaml.
        #
        # This is important for frontend editing: loading a target.yaml,
        # changing an unrelated setting, then saving it must not create a
        # replacement secret.
        if self._looks_like_secret_ref(value):
            ref = SecretRef.model_validate(value)

            await self._validate_reference_ownership(
                target_id,
                ref,
            )

            return ref.model_dump(
                mode="json",
                exclude_none=True,
            )

        # Explicit custom secret syntax:
        #
        # field:
        #   secret: true
        #   value: something
        if self._looks_like_explicit_secret(value):
            plaintext = value.get("value")

            if plaintext is None:
                return None

            return await self._store_plaintext(
                target_id=target_id,
                path=path,
                plaintext=plaintext,
            )

        # Automatically recognized sensitive field.
        if (
            field_name is not None
            and self._is_secret_field(field_name)
            and value is not None
        ):
            # A mapping here may be some provider-specific nested structure.
            # Only treat scalar secret values automatically. Structured secret
            # objects should use explicit secret:true syntax.
            if not isinstance(
                value,
                (dict, list, tuple),
            ):
                return await self._store_plaintext(
                    target_id=target_id,
                    path=path,
                    plaintext=value,
                )

        if isinstance(value, Mapping):
            sanitized: dict[str, Any] = {}

            for key, child in value.items():
                key_string = str(key)

                sanitized[key_string] = await self._sanitize_value(
                    target_id=target_id,
                    value=child,
                    path=(*path, key_string),
                    field_name=key_string,
                )

            return sanitized

        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            items: list[Any] = []

            for index, child in enumerate(value):
                items.append(
                    await self._sanitize_value(
                        target_id=target_id,
                        value=child,
                        path=(*path, str(index)),
                        field_name=None,
                    )
                )

            return items

        return value

    async def _store_plaintext(
        self,
        *,
        target_id: str,
        path: tuple[str, ...],
        plaintext: Any,
    ) -> dict[str, Any]:
        """Encrypt one plaintext value and replace it with a SecretRef."""

        if not isinstance(plaintext, str):
            raise ValueError(
                f"Secret value at '{self._format_path(path)}' "
                "must be a string."
            )

        if not plaintext:
            raise ValueError(
                f"Secret value at '{self._format_path(path)}' "
                "must not be empty."
            )

        name = self._format_path(path)

        existing = await self._repository.get_secret_by_name(
            target_id,
            name,
        )

        secret_id = (
            existing.secret_id
            if existing is not None
            else f"sec-{uuid4()}"
        )

        encrypted_value = self._cipher.encrypt(
            plaintext.encode("utf-8")
        )

        await self._repository.persist_secret(
            secret_id=secret_id,
            target_id=target_id,
            name=name,
            encrypted_value=encrypted_value,
            key_version=self._key_version,
            metadata={
                "config_path": name,
            },
        )

        return SecretRef(
            secret_id=secret_id,
            name=name,
        ).model_dump(
            mode="json",
            exclude_none=True,
        )

    # ---------------------------------------------------------------------
    # Runtime resolution
    # ---------------------------------------------------------------------

    async def resolve_credentials(
        self,
        target_id: str,
        config: EffectiveTargetConfig,
    ) -> ResolvedTargetCredentials:
        """Resolve canonical SecretRef values into transient adapter credentials.

        Plaintext values returned here must only live long enough to construct
        and use the adapter. They must never be serialized or persisted.
        """

        bearer_token: str | None = None
        api_key: str | None = None
        api_key_header = "X-API-Key"

        auth = config.auth

        if auth is not None:
            bearer_ref = auth.bearer_token

            # auth_token is commonly used as an alternate spelling for bearer
            # authentication. Only use it automatically for token-like auth
            # modes.
            if (
                bearer_ref is None
                and auth.auth_token is not None
                and self._uses_bearer_auth(auth.type)
            ):
                bearer_ref = auth.auth_token

            if bearer_ref is not None:
                bearer_token = await self.resolve_secret(
                    target_id,
                    bearer_ref,
                )

            if auth.api_key is not None:
                api_key = await self.resolve_secret(
                    target_id,
                    auth.api_key,
                )

            configured_header = auth.parameters.get(
                "api_key_header"
            )

            if isinstance(configured_header, str):
                api_key_header = configured_header

        headers: dict[str, str] = {}

        connection = config.connection

        if connection is not None:
            for header_name, header_value in connection.headers.items():
                if isinstance(header_value, SecretRef):
                    headers[header_name] = await self.resolve_secret(
                        target_id,
                        header_value,
                    )

        return ResolvedTargetCredentials(
            bearer_token=bearer_token,
            api_key=api_key,
            api_key_header=api_key_header,
            headers=headers,
        )

    async def resolve_secret(
        self,
        target_id: str,
        reference: SecretRef,
    ) -> str:
        """Resolve one SecretRef to plaintext after checking target ownership."""

        record = await self._repository.get_secret(
            reference.secret_id
        )

        if record is None:
            raise KeyError(
                f"target secret not found: {reference.secret_id}"
            )

        if record.target_id != target_id:
            raise ValueError(
                f"secret '{reference.secret_id}' does not belong "
                f"to target '{target_id}'"
            )

        try:
            plaintext = self._cipher.decrypt(
                record.encrypted_value
            )
        except InvalidToken as exc:
            raise RuntimeError(
                f"unable to decrypt target secret: "
                f"{reference.secret_id}"
            ) from exc

        try:
            return plaintext.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(
                f"target secret '{reference.secret_id}' "
                "does not contain valid UTF-8 text"
            ) from exc

    # ---------------------------------------------------------------------
    # Secret replacement
    # ---------------------------------------------------------------------

    async def replace_secret(
        self,
        target_id: str,
        reference: SecretRef,
        plaintext: str,
    ) -> SecretRef:
        """Replace the value behind an existing stable SecretRef.

        The secret ID remains unchanged so the current target configuration
        does not need to be rewritten merely because a token was rotated.
        """

        record = await self._repository.get_secret(
            reference.secret_id
        )

        if record is None:
            raise KeyError(
                f"target secret not found: {reference.secret_id}"
            )

        if record.target_id != target_id:
            raise ValueError(
                f"secret '{reference.secret_id}' does not belong "
                f"to target '{target_id}'"
            )

        if not plaintext:
            raise ValueError(
                "replacement secret must not be empty"
            )

        encrypted_value = self._cipher.encrypt(
            plaintext.encode("utf-8")
        )

        await self._repository.persist_secret(
            secret_id=record.secret_id,
            target_id=target_id,
            name=record.name,
            encrypted_value=encrypted_value,
            key_version=self._key_version,
            metadata=dict(record.metadata_json or {}),
        )

        return SecretRef(
            secret_id=record.secret_id,
            name=record.name,
        )

    # ---------------------------------------------------------------------
    # Detection
    # ---------------------------------------------------------------------

    @staticmethod
    def _looks_like_secret_ref(
        value: Any,
    ) -> bool:
        """Return whether a value has the canonical SecretRef shape."""

        if not isinstance(value, Mapping):
            return False

        secret_id = value.get("secret_id")

        return (
            isinstance(secret_id, str)
            and bool(secret_id)
        )

    @staticmethod
    def _looks_like_explicit_secret(
        value: Any,
    ) -> bool:
        """Return whether YAML explicitly marks a value as secret."""

        return (
            isinstance(value, Mapping)
            and value.get("secret") is True
            and "value" in value
        )

    @classmethod
    def _is_secret_field(
        cls,
        name: str,
    ) -> bool:
        """Recognize common sensitive field names conservatively."""

        normalized = cls._normalize_field_name(
            name
        )

        if normalized in _SECRET_FIELD_NAMES:
            return True

        return any(
            normalized.endswith(suffix)
            for suffix in _SECRET_FIELD_SUFFIXES
        )

    @staticmethod
    def _normalize_field_name(
        name: str,
    ) -> str:
        """Normalize YAML/header field names for secret detection."""

        value = name.strip().lower()

        value = re.sub(
            r"[^a-z0-9]+",
            "_",
            value,
        )

        return value.strip("_")

    @staticmethod
    def _format_path(
        path: tuple[str, ...],
    ) -> str:
        """Return one stable target-local secret name from a config path."""

        if not path:
            raise ValueError(
                "secret configuration path must not be empty"
            )

        return ".".join(path)

    async def _validate_reference_ownership(
        self,
        target_id: str,
        reference: SecretRef,
    ) -> None:
        """Reject references to another target's secret."""

        record = await self._repository.get_secret(
            reference.secret_id
        )

        if record is None:
            raise KeyError(
                f"target secret not found: {reference.secret_id}"
            )

        if record.target_id != target_id:
            raise ValueError(
                f"secret '{reference.secret_id}' does not belong "
                f"to target '{target_id}'"
            )

    @staticmethod
    def _uses_bearer_auth(
        auth_type: str | None,
    ) -> bool:
        """Return whether auth_token should behave as a bearer credential."""

        if auth_type is None:
            return False

        return auth_type.strip().lower() in {
            "bearer",
            "bearer_token",
            "token",
            "auth_token",
        }