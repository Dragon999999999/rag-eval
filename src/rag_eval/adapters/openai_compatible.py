"""Adapter for OpenAI-compatible chat-completions APIs.

This adapter translates the canonical rag-eval target protocol into the
widely supported OpenAI-compatible ``/chat/completions`` HTTP shape.

It intentionally supports only capabilities it can normalize reliably.
Provider-specific extensions belong in EffectiveTargetConfig or a dedicated
adapter rather than leaking into evaluation execution.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

import httpx
from pydantic import ValidationError

from rag_eval.adapters.base import (
    DocumentUpload,
    ResolvedTargetCredentials,
)
from rag_eval.adapters.errors import (
    TargetAdapterError,
    TargetProtocolError,
    UnsupportedCapabilityError,
)
from rag_eval.models import (
    Answer,
    Chunk,
    CreateCorpusRequest,
    CreateCorpusResponse,
    EffectiveTargetConfig,
    ErrorCategory,
    HealthState,
    HealthStatus,
    Operation,
    QueryEvent,
    QueryRequest,
    QueryResponse,
    RequestRecoveryResult,
    RetrieveRequest,
    RetrieveResponse,
    TargetCapabilities,
    TargetInfo,
    Usage,
    UsageCapabilities,
)


class OpenAICompatibleAdapter:
    """Invoke an OpenAI-compatible chat-completions target."""

    def __init__(
        self,
        config: EffectiveTargetConfig,
        credentials: ResolvedTargetCredentials,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create an adapter from fully resolved target configuration."""

        connection = config.connection

        if connection is None or connection.base_url is None:
            raise ValueError(
                "openai_compatible adapter requires connection.base_url."
            )

        model = config.parameters.get("model")

        if not isinstance(model, str) or not model:
            raise ValueError(
                "openai_compatible adapter requires parameters.model."
            )

        self._config = config
        self._model = model
        self._protocol = dict(config.protocol)

        headers: dict[str, str] = {
            "Accept": "application/json",
            "Content-Type": "application/json",
        }

        # Plain non-secret configured headers.
        for name, value in connection.headers.items():
            if isinstance(value, str):
                headers[name] = value

        # Already-resolved secret-valued headers.
        headers.update(credentials.headers)

        # OpenAI-compatible APIs overwhelmingly use bearer authentication.
        token = (
            credentials.bearer_token
            or credentials.api_key
        )

        if token is not None:
            headers["Authorization"] = f"Bearer {token}"

        timeout = connection.timeout_seconds or 60.0
        verify_tls = (
            True
            if connection.verify_tls is None
            else connection.verify_tls
        )

        self._client = client or httpx.AsyncClient(
            base_url=str(connection.base_url).rstrip("/") + "/",
            headers=headers,
            timeout=httpx.Timeout(timeout),
            verify=verify_tls,
        )

        if client is not None:
            self._client.headers.update(headers)
            self._client.base_url = httpx.URL(
                str(connection.base_url).rstrip("/") + "/"
            )

        self._owns_client = client is None

    async def aclose(self) -> None:
        """Release the owned HTTP client."""

        if self._owns_client:
            await self._client.aclose()

    # ------------------------------------------------------------------
    # Capabilities / health
    # ------------------------------------------------------------------

    async def capabilities(self) -> TargetCapabilities:
        """Return normalized capabilities for an OpenAI-compatible target."""

        target = self._target_info()

        payload: dict[str, Any] = {
            "protocol_version": "1.0",
            "target": target.model_dump(mode="json"),
            "query": True,
            "streaming": False,
            "conversation_history": True,
            "retrieval": False,
            "retrieval_stages": False,
            "document_ingestion": False,
            "chunk_ingestion": False,
            "context_injection": False,
            "citations": False,
            "confidence": False,
            "target_trace": False,
            "effective_configuration": False,
            "idempotency": False,
            "request_recovery": False,
            "usage": UsageCapabilities(
                tokens=True,
            ).model_dump(mode="json"),
        }

        configured = self._protocol.get("capabilities")

        if isinstance(configured, dict):
            payload.update(configured)

            # Evaluator-normalized target identity must not disappear when
            # capabilities are overridden.
            payload.setdefault(
                "target",
                target.model_dump(mode="json"),
            )

        return TargetCapabilities.model_validate(
            payload
        )

    async def health(self) -> HealthStatus | None:
        """Check an explicitly configured health endpoint.

        OpenAI compatibility itself does not define a health endpoint.
        Therefore lack of a configured endpoint returns None and the target
        management layer records the target as UNVERIFIED.
        """

        spec = self._protocol.get("health")

        if not isinstance(spec, dict):
            return None

        endpoint = spec.get("endpoint")

        if not isinstance(endpoint, str) or not endpoint:
            return None

        method = spec.get("method", "GET")

        if not isinstance(method, str):
            raise ValueError(
                "protocol.health.method must be a string."
            )

        await self._request_json(
            "health",
            method,
            endpoint,
        )

        return HealthStatus(
            status=HealthState.READY,
            target=self._target_info(),
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        request: QueryRequest,
    ) -> QueryResponse:
        """Translate a canonical query into OpenAI chat completions."""

        endpoint = self._chat_endpoint()

        messages = [
            self._normalize_message(
                message.model_dump(
                    mode="json",
                    exclude_none=True,
                )
            )
            for message in request.history
        ]

        messages.append(
            {
                "role": "user",
                "content": request.query,
            }
        )

        body: dict[str, Any] = {
            "model": self._model,
            "messages": messages,
            "stream": False,
        }

        # Query parameters such as temperature/max_tokens are intentionally
        # forwarded to the provider.
        body.update(request.parameters)

        payload = await self._request_json(
            "query",
            "POST",
            endpoint,
            json_body=body,
        )

        answer_text = self._extract_answer(
            payload
        )

        usage = self._normalize_usage(
            payload.get("usage")
        )

        return QueryResponse(
            request_id=request.request_id,
            answer=Answer(
                text=answer_text,
            ),
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Unsupported operations
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        request: RetrieveRequest,
    ) -> RetrieveResponse:
        """Reject retrieval because OpenAI chat compatibility exposes none."""

        raise UnsupportedCapabilityError(
            "retrieval",
            "retrieve",
        )

    async def create_corpus(
        self,
        request: CreateCorpusRequest,
    ) -> CreateCorpusResponse:
        """Reject corpus creation."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "create_corpus",
        )

    async def get_corpus(
        self,
        corpus_id: str,
    ) -> CreateCorpusResponse:
        """Reject corpus inspection."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "get_corpus",
        )

    async def delete_corpus(
        self,
        corpus_id: str,
    ) -> None:
        """Reject corpus deletion."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "delete_corpus",
        )

    async def upload_document(
        self,
        corpus_id: str,
        document: DocumentUpload,
    ) -> Operation:
        """Reject document ingestion."""

        raise UnsupportedCapabilityError(
            "document_ingestion",
            "upload_document",
        )

    async def upload_chunks(
        self,
        corpus_id: str,
        chunks: AsyncIterator[Chunk],
    ) -> Operation:
        """Reject chunk ingestion."""

        raise UnsupportedCapabilityError(
            "chunk_ingestion",
            "upload_chunks",
        )

    async def get_operation(
        self,
        operation_id: str,
    ) -> Operation:
        """Reject ingestion-operation lookup."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "get_operation",
        )

    async def stream_query(
        self,
        request: QueryRequest,
    ) -> AsyncIterator[QueryEvent]:
        """Reject streaming until canonical event normalization is enabled."""

        raise UnsupportedCapabilityError(
            "streaming",
            "stream_query",
        )

        if False:
            yield QueryEvent.model_construct()

    async def recover_request(
        self,
        request_id: str,
    ) -> RequestRecoveryResult:
        """Reject request recovery."""

        raise UnsupportedCapabilityError(
            "request_recovery",
            "recover_request",
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _target_info(self) -> TargetInfo:
        """Build normalized provider identity from effective configuration."""

        target_name = self._config.metadata.get(
            "target_name"
        )

        if not isinstance(target_name, str):
            target_name = (
                f"OpenAI-compatible ({self._model})"
            )

        implementation = self._config.metadata.get(
            "implementation"
        )

        version = self._config.metadata.get(
            "version"
        )

        return TargetInfo(
            name=target_name,
            version=(
                version
                if isinstance(version, str)
                else None
            ),
            implementation=(
                implementation
                if isinstance(implementation, str)
                else "openai-compatible"
            ),
            metadata={
                "model": self._model,
            },
        )

    def _chat_endpoint(self) -> str:
        """Return configured or standard chat-completions endpoint."""

        query_spec = self._protocol.get("query")

        if isinstance(query_spec, dict):
            endpoint = query_spec.get("endpoint")

            if isinstance(endpoint, str) and endpoint:
                return endpoint

        return "chat/completions"

    @staticmethod
    def _normalize_message(
        message: dict[str, Any],
    ) -> dict[str, Any]:
        """Reduce one canonical message to OpenAI role/content shape."""

        role = message.get("role")
        content = message.get("content")

        if role is None or content is None:
            raise TargetProtocolError(
                "Canonical conversation history message lacks role/content.",
                operation="query",
            )

        return {
            "role": str(role),
            "content": content,
        }

    @staticmethod
    def _extract_answer(
        payload: dict[str, Any],
    ) -> str:
        """Extract assistant text from a chat-completions response."""

        choices = payload.get("choices")

        if not isinstance(choices, list) or not choices:
            raise TargetProtocolError(
                "OpenAI-compatible response contains no choices.",
                operation="query",
            )

        first = choices[0]

        if not isinstance(first, dict):
            raise TargetProtocolError(
                "OpenAI-compatible choice is not an object.",
                operation="query",
            )

        message = first.get("message")

        if not isinstance(message, dict):
            raise TargetProtocolError(
                "OpenAI-compatible choice contains no message.",
                operation="query",
            )

        content = message.get("content")

        if isinstance(content, str):
            return content

        # Some compatible APIs emit structured content blocks.
        if isinstance(content, list):
            text_parts: list[str] = []

            for item in content:
                if not isinstance(item, dict):
                    continue

                text = item.get("text")

                if isinstance(text, str):
                    text_parts.append(text)

            if text_parts:
                return "".join(text_parts)

        raise TargetProtocolError(
            "OpenAI-compatible response contains no textual assistant content.",
            operation="query",
        )

    @staticmethod
    def _normalize_usage(
        value: Any,
    ) -> Usage | None:
        """Normalize common OpenAI token-usage fields."""

        if not isinstance(value, dict):
            return None

        tokens: dict[str, int] = {}

        mappings = {
            "prompt_tokens": "prompt",
            "completion_tokens": "completion",
            "total_tokens": "total",
        }

        for provider_name, canonical_name in mappings.items():
            count = value.get(provider_name)

            if isinstance(count, int):
                tokens[canonical_name] = count

        return Usage(
            tokens=tokens,
            metadata={
                "provider_usage": value,
            },
        )

    async def _request_json(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Perform one provider request and normalize transport failures."""

        try:
            response = await self._client.request(
                method.upper(),
                path.lstrip("/"),
                json=json_body,
            )

        except httpx.TimeoutException as exc:
            raise TargetAdapterError(
                f"OpenAI-compatible operation '{operation}' timed out.",
                category=ErrorCategory.TIMEOUT,
                code="OPENAI_COMPATIBLE_TIMEOUT",
                stage=operation,
                retryable=True,
            ) from exc

        except httpx.ConnectError as exc:
            raise TargetAdapterError(
                f"Unable to connect during '{operation}'.",
                category=ErrorCategory.CONNECTION,
                code="OPENAI_COMPATIBLE_CONNECTION_ERROR",
                stage=operation,
                retryable=True,
            ) from exc

        except httpx.HTTPError as exc:
            raise TargetAdapterError(
                f"HTTP transport failed during '{operation}'.",
                category=ErrorCategory.NETWORK,
                code="OPENAI_COMPATIBLE_HTTP_ERROR",
                stage=operation,
            ) from exc

        if response.is_error:
            raise TargetAdapterError(
                f"OpenAI-compatible target returned HTTP "
                f"{response.status_code} during '{operation}'.",
                category=self._status_category(
                    response.status_code
                ),
                code=f"HTTP_{response.status_code}",
                stage=operation,
                http_status=response.status_code,
                retryable=response.status_code
                in {429, 502, 503, 504},
                details={
                    "response_body": response.text,
                },
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise TargetProtocolError(
                f"OpenAI-compatible target returned invalid JSON "
                f"during '{operation}'.",
                operation=operation,
            ) from exc

        if not isinstance(payload, dict):
            raise TargetProtocolError(
                f"OpenAI-compatible target returned a non-object "
                f"response during '{operation}'.",
                operation=operation,
            )

        return payload

    @staticmethod
    def _status_category(
        status_code: int,
    ) -> ErrorCategory:
        """Map common HTTP status codes to canonical categories."""

        if status_code == 401:
            return ErrorCategory.AUTHENTICATION

        if status_code == 403:
            return ErrorCategory.AUTHORIZATION

        if status_code == 404:
            return ErrorCategory.NOT_FOUND

        if status_code == 429:
            return ErrorCategory.RATE_LIMIT

        if status_code >= 500:
            return ErrorCategory.CONNECTION

        return ErrorCategory.INVALID_RESPONSE