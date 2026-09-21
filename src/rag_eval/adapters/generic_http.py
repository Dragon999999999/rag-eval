"""Declarative generic HTTP target adapter.

GenericHttpTargetAdapter allows uncommon HTTP targets to participate in
rag-eval without requiring a custom Python adapter.

The adapter interprets EffectiveTargetConfig.protocol. It intentionally
provides a small declarative mapping language rather than arbitrary code.

Example:

    protocol:
      query:
        method: POST
        endpoint: /ask

        request:
          body:
            question: "$request.query"
            history: "$request.history"

        response:
          answer_path: "$.result.answer"
          usage_path: "$.usage"

Response paths support simple object keys and list indexes:

    $.result.answer
    result.answer
    $.choices.0.message.content
"""

from __future__ import annotations

from typing import Any
from collections.abc import AsyncIterator, Mapping, Sequence

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
    Citation,
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
    RetrievalResult,
    RetrieveRequest,
    RetrieveResponse,
    TargetCapabilities,
    TargetInfo,
    Usage,
)


_MISSING = object()


class GenericHttpTargetAdapter:
    """Invoke an arbitrary JSON HTTP API using declarative mappings."""

    def __init__(
        self,
        config: EffectiveTargetConfig,
        credentials: ResolvedTargetCredentials,
        *,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Construct a generic HTTP adapter."""

        connection = config.connection

        if connection is None or connection.base_url is None:
            raise ValueError(
                "generic_http adapter requires connection.base_url."
            )

        self._config = config
        self._protocol = dict(config.protocol)

        headers: dict[str, str] = {
            "Accept": "application/json",
        }

        for name, value in connection.headers.items():
            if isinstance(value, str):
                headers[name] = value

        headers.update(credentials.headers)

        if credentials.bearer_token is not None:
            headers["Authorization"] = (
                f"Bearer {credentials.bearer_token}"
            )

        elif credentials.api_key is not None:
            headers[
                credentials.api_key_header
            ] = credentials.api_key

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
    # Capabilities
    # ------------------------------------------------------------------

    async def capabilities(self) -> TargetCapabilities:
        """Return capabilities inferred from the declarative protocol."""

        target = self._target_info()

        query_spec = self._operation_spec(
            "query"
        )

        retrieve_spec = self._operation_spec(
            "retrieve"
        )

        configured = self._protocol.get(
            "capabilities"
        )

        payload: dict[str, Any] = {
            "protocol_version": "1.0",
            "target": target.model_dump(mode="json"),
            "query": query_spec is not None,
            "streaming": False,
            "conversation_history": (
                query_spec is not None
                and self._template_references(
                    query_spec,
                    "$request.history",
                )
            ),
            "retrieval": retrieve_spec is not None,
            "retrieval_stages": False,
            "document_ingestion": False,
            "chunk_ingestion": False,
            "context_injection": False,
            "citations": self._query_response_has(
                "citations_path"
            ),
            "confidence": False,
            "target_trace": False,
            "effective_configuration": False,
            "idempotency": False,
            "request_recovery": False,
        }

        if isinstance(configured, Mapping):
            payload.update(
                dict(configured)
            )

            payload.setdefault(
                "target",
                target.model_dump(mode="json"),
            )

        try:
            return TargetCapabilities.model_validate(
                payload
            )

        except ValidationError as exc:
            raise TargetProtocolError(
                "Configured generic HTTP capabilities are invalid.",
                operation="capabilities",
            ) from exc

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    async def health(self) -> HealthStatus | None:
        """Invoke a configured health endpoint.

        Absence of protocol.health means health cannot be verified.
        """

        spec = self._operation_spec(
            "health"
        )

        if spec is None:
            return None

        method = self._method(
            spec
        )

        endpoint = self._endpoint(
            "health",
            spec,
        )

        payload = await self._request_json(
            "health",
            method,
            endpoint,
        )

        response_spec = self._response_spec(
            spec
        )

        # A configured status_path allows semantic validation rather than
        # treating every HTTP 2xx response as healthy.
        status_path = response_spec.get(
            "status_path"
        )

        if isinstance(status_path, str):
            status = self._extract_path(
                payload,
                status_path,
            )

            healthy_values = response_spec.get(
                "healthy_values",
                ["ok", "healthy", "ready", True],
            )

            if status not in healthy_values:
                raise TargetProtocolError(
                    "Generic HTTP health endpoint returned a non-healthy "
                    "status value.",
                    operation="health",
                    details={
                        "status": status,
                    },
                )

        return HealthStatus(
            status=HealthState.READY,
            target=self._target_info(),
            details=(
                payload
                if isinstance(payload, dict)
                else {"response": payload}
            ),
        )

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(
        self,
        request: QueryRequest,
    ) -> QueryResponse:
        """Execute one declaratively mapped generation request."""

        spec = self._require_operation(
            "query"
        )

        request_payload = request.model_dump(
            mode="json",
            exclude_none=True,
        )

        body = self._build_body(
            spec,
            request_payload,
        )

        payload = await self._request_json(
            "query",
            self._method(spec),
            self._endpoint("query", spec),
            json_body=body,
        )

        response_spec = self._response_spec(
            spec
        )

        if response_spec.get(
            "canonical"
        ) is True:
            try:
                return QueryResponse.model_validate(
                    payload
                )
            except ValidationError as exc:
                raise TargetProtocolError(
                    "Generic HTTP query response is not a valid "
                    "canonical QueryResponse.",
                    operation="query",
                ) from exc

        answer_path = response_spec.get(
            "answer_path"
        )

        if not isinstance(answer_path, str):
            raise TargetProtocolError(
                "generic_http query requires "
                "response.answer_path unless response.canonical=true.",
                operation="query",
            )

        answer_value = self._extract_path(
            payload,
            answer_path,
        )

        if not isinstance(answer_value, str):
            raise TargetProtocolError(
                "Configured query answer_path did not resolve to a string.",
                operation="query",
                details={
                    "answer_path": answer_path,
                },
            )

        citations = self._normalize_citations(
            payload,
            response_spec,
        )

        retrieval = self._optional_model_path(
            payload,
            response_spec.get("retrieval_path"),
            RetrievalResult,
            "query",
        )

        usage = self._optional_model_path(
            payload,
            response_spec.get("usage_path"),
            Usage,
            "query",
        )

        return QueryResponse(
            request_id=request.request_id,
            answer=Answer(
                text=answer_value,
                citations=citations,
            ),
            retrieval=retrieval,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Retrieval
    # ------------------------------------------------------------------

    async def retrieve(
        self,
        request: RetrieveRequest,
    ) -> RetrieveResponse:
        """Execute one declaratively mapped retrieval request."""

        spec = self._require_operation(
            "retrieve"
        )

        request_payload = request.model_dump(
            mode="json",
            exclude_none=True,
        )

        body = self._build_body(
            spec,
            request_payload,
        )

        payload = await self._request_json(
            "retrieve",
            self._method(spec),
            self._endpoint("retrieve", spec),
            json_body=body,
        )

        response_spec = self._response_spec(
            spec
        )

        if response_spec.get(
            "canonical"
        ) is True:
            try:
                return RetrieveResponse.model_validate(
                    payload
                )
            except ValidationError as exc:
                raise TargetProtocolError(
                    "Generic HTTP retrieval response is not a valid "
                    "canonical RetrieveResponse.",
                    operation="retrieve",
                ) from exc

        retrieval_path = response_spec.get(
            "retrieval_path"
        )

        if not isinstance(retrieval_path, str):
            raise TargetProtocolError(
                "generic_http retrieve requires "
                "response.retrieval_path unless response.canonical=true.",
                operation="retrieve",
            )

        retrieval_value = self._extract_path(
            payload,
            retrieval_path,
        )

        try:
            retrieval = RetrievalResult.model_validate(
                retrieval_value
            )
        except ValidationError as exc:
            raise TargetProtocolError(
                "Configured retrieval_path does not contain a valid "
                "canonical RetrievalResult.",
                operation="retrieve",
                details={
                    "retrieval_path": retrieval_path,
                },
            ) from exc

        usage = self._optional_model_path(
            payload,
            response_spec.get("usage_path"),
            Usage,
            "retrieve",
        )

        return RetrieveResponse(
            request_id=request.request_id,
            retrieval=retrieval,
            usage=usage,
        )

    # ------------------------------------------------------------------
    # Unsupported operations
    # ------------------------------------------------------------------

    async def create_corpus(
        self,
        request: CreateCorpusRequest,
    ) -> CreateCorpusResponse:
        """Reject declarative ingestion until explicitly implemented."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "create_corpus",
        )

    async def get_corpus(
        self,
        corpus_id: str,
    ) -> CreateCorpusResponse:
        """Reject declarative corpus inspection."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "get_corpus",
        )

    async def delete_corpus(
        self,
        corpus_id: str,
    ) -> None:
        """Reject declarative corpus deletion."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "delete_corpus",
        )

    async def upload_document(
        self,
        corpus_id: str,
        document: DocumentUpload,
    ) -> Operation:
        """Reject declarative document upload."""

        raise UnsupportedCapabilityError(
            "document_ingestion",
            "upload_document",
        )

    async def upload_chunks(
        self,
        corpus_id: str,
        chunks: AsyncIterator[Chunk],
    ) -> Operation:
        """Reject declarative chunk upload."""

        raise UnsupportedCapabilityError(
            "chunk_ingestion",
            "upload_chunks",
        )

    async def get_operation(
        self,
        operation_id: str,
    ) -> Operation:
        """Reject declarative async-operation lookup."""

        raise UnsupportedCapabilityError(
            "document_ingestion or chunk_ingestion",
            "get_operation",
        )

    async def stream_query(
        self,
        request: QueryRequest,
    ) -> AsyncIterator[QueryEvent]:
        """Reject declarative streaming in the initial adapter version."""

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
        """Reject declarative request recovery."""

        raise UnsupportedCapabilityError(
            "request_recovery",
            "recover_request",
        )

    # ------------------------------------------------------------------
    # Request mapping
    # ------------------------------------------------------------------

    def _build_body(
        self,
        spec: Mapping[str, Any],
        request: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """Render one configured request body against canonical request data."""

        request_spec = spec.get(
            "request"
        )

        if request_spec is None:
            return dict(request)

        if not isinstance(request_spec, Mapping):
            raise ValueError(
                "operation.request must be a mapping."
            )

        body_template = request_spec.get(
            "body"
        )

        if body_template is None:
            return dict(request)

        rendered = self._render_template(
            body_template,
            request,
        )

        if not isinstance(rendered, dict):
            raise ValueError(
                "operation.request.body must render to an object."
            )

        return rendered

    def _render_template(
        self,
        value: Any,
        request: Mapping[str, Any],
    ) -> Any:
        """Recursively render $request.* values inside configured templates."""

        if isinstance(value, str):
            if value == "$request":
                return dict(request)

            if value.startswith(
                "$request."
            ):
                return self._extract_path(
                    request,
                    value[len("$request."):],
                )

            return value

        if isinstance(value, Mapping):
            return {
                str(key): self._render_template(
                    child,
                    request,
                )
                for key, child in value.items()
            }

        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return [
                self._render_template(
                    child,
                    request,
                )
                for child in value
            ]

        return value

    # ------------------------------------------------------------------
    # Response mapping
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_path(
        value: Any,
        path: str,
    ) -> Any:
        """Extract a simple dotted path from a JSON-compatible value."""

        normalized = path.strip()

        if normalized == "$":
            return value

        if normalized.startswith("$."):
            normalized = normalized[2:]

        if not normalized:
            return value

        current = value

        for segment in normalized.split("."):
            if isinstance(current, Mapping):
                if segment not in current:
                    raise TargetProtocolError(
                        f"Response path '{path}' does not exist.",
                        operation="response_mapping",
                        details={
                            "missing_segment": segment,
                        },
                    )

                current = current[segment]
                continue

            if isinstance(current, Sequence) and not isinstance(
                current,
                (str, bytes, bytearray),
            ):
                try:
                    index = int(segment)
                except ValueError as exc:
                    raise TargetProtocolError(
                        f"Response path '{path}' expected a numeric "
                        "list index.",
                        operation="response_mapping",
                    ) from exc

                try:
                    current = current[index]
                except IndexError as exc:
                    raise TargetProtocolError(
                        f"Response path '{path}' contains an out-of-range "
                        "list index.",
                        operation="response_mapping",
                    ) from exc

                continue

            raise TargetProtocolError(
                f"Response path '{path}' traverses a non-container value.",
                operation="response_mapping",
            )

        return current

    def _normalize_citations(
        self,
        payload: Any,
        response_spec: Mapping[str, Any],
    ) -> list[Citation]:
        """Normalize optional canonical citation objects."""

        path = response_spec.get(
            "citations_path"
        )

        if not isinstance(path, str):
            return []

        value = self._extract_path(
            payload,
            path,
        )

        if not isinstance(value, list):
            raise TargetProtocolError(
                "Configured citations_path does not resolve to a list.",
                operation="query",
            )

        try:
            return [
                Citation.model_validate(item)
                for item in value
            ]

        except ValidationError as exc:
            raise TargetProtocolError(
                "Configured citations are not valid canonical Citation "
                "objects.",
                operation="query",
            ) from exc

    def _optional_model_path(
        self,
        payload: Any,
        path: Any,
        model_type: type[Any],
        operation: str,
    ) -> Any | None:
        """Normalize an optional response sub-object into a canonical model."""

        if not isinstance(path, str):
            return None

        value = self._extract_path(
            payload,
            path,
        )

        try:
            return model_type.model_validate(
                value
            )

        except ValidationError as exc:
            raise TargetProtocolError(
                f"Response path '{path}' is not valid "
                f"{model_type.__name__}.",
                operation=operation,
            ) from exc

    # ------------------------------------------------------------------
    # Protocol configuration
    # ------------------------------------------------------------------

    def _operation_spec(
        self,
        name: str,
    ) -> dict[str, Any] | None:
        """Return one configured operation specification."""

        value = self._protocol.get(
            name
        )

        if value is None:
            return None

        if not isinstance(value, Mapping):
            raise ValueError(
                f"protocol.{name} must be a mapping."
            )

        return dict(value)

    def _require_operation(
        self,
        name: str,
    ) -> dict[str, Any]:
        """Return a configured operation or raise an unsupported error."""

        spec = self._operation_spec(
            name
        )

        if spec is None:
            raise UnsupportedCapabilityError(
                name,
                name,
            )

        return spec

    @staticmethod
    def _method(
        spec: Mapping[str, Any],
    ) -> str:
        """Return configured HTTP method."""

        value = spec.get(
            "method",
            "POST",
        )

        if not isinstance(value, str) or not value:
            raise ValueError(
                "operation.method must be a non-empty string."
            )

        return value.upper()

    @staticmethod
    def _endpoint(
        operation: str,
        spec: Mapping[str, Any],
    ) -> str:
        """Return configured operation endpoint."""

        value = spec.get(
            "endpoint"
        )

        if not isinstance(value, str) or not value:
            raise ValueError(
                f"protocol.{operation}.endpoint is required."
            )

        return value

    @staticmethod
    def _response_spec(
        spec: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Return normalized response mapping configuration."""

        value = spec.get(
            "response",
            {},
        )

        if not isinstance(value, Mapping):
            raise ValueError(
                "operation.response must be a mapping."
            )

        return dict(value)

    def _query_response_has(
        self,
        field: str,
    ) -> bool:
        """Return whether query response mapping declares one feature."""

        query = self._operation_spec(
            "query"
        )

        if query is None:
            return False

        return field in self._response_spec(
            query
        )

    @staticmethod
    def _template_references(
        value: Any,
        reference: str,
    ) -> bool:
        """Return whether arbitrary nested configuration contains a reference."""

        if value == reference:
            return True

        if isinstance(value, Mapping):
            return any(
                GenericHttpTargetAdapter._template_references(
                    child,
                    reference,
                )
                for child in value.values()
            )

        if isinstance(value, Sequence) and not isinstance(
            value,
            (str, bytes, bytearray),
        ):
            return any(
                GenericHttpTargetAdapter._template_references(
                    child,
                    reference,
                )
                for child in value
            )

        return False

    # ------------------------------------------------------------------
    # Target identity
    # ------------------------------------------------------------------

    def _target_info(self) -> TargetInfo:
        """Build evaluator-normalized target identity."""

        name = self._config.metadata.get(
            "target_name"
        )

        version = self._config.metadata.get(
            "version"
        )

        implementation = self._config.metadata.get(
            "implementation"
        )

        return TargetInfo(
            name=(
                name
                if isinstance(name, str)
                else "Generic HTTP target"
            ),
            version=(
                version
                if isinstance(version, str)
                else None
            ),
            implementation=(
                implementation
                if isinstance(implementation, str)
                else "generic-http"
            ),
        )

    # ------------------------------------------------------------------
    # HTTP transport
    # ------------------------------------------------------------------

    async def _request_json(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
    ) -> Any:
        """Perform one configured HTTP request."""

        try:
            response = await self._client.request(
                method.upper(),
                path.lstrip("/"),
                json=json_body,
            )

        except httpx.TimeoutException as exc:
            raise TargetAdapterError(
                f"Generic HTTP operation '{operation}' timed out.",
                category=ErrorCategory.TIMEOUT,
                code="GENERIC_HTTP_TIMEOUT",
                stage=operation,
                retryable=True,
            ) from exc

        except httpx.ConnectError as exc:
            raise TargetAdapterError(
                f"Unable to connect during '{operation}'.",
                category=ErrorCategory.CONNECTION,
                code="GENERIC_HTTP_CONNECTION_ERROR",
                stage=operation,
                retryable=True,
            ) from exc

        except httpx.HTTPError as exc:
            raise TargetAdapterError(
                f"HTTP transport failed during '{operation}'.",
                category=ErrorCategory.NETWORK,
                code="GENERIC_HTTP_TRANSPORT_ERROR",
                stage=operation,
            ) from exc

        if response.is_error:
            raise TargetAdapterError(
                f"Generic HTTP target returned HTTP "
                f"{response.status_code} during '{operation}'.",
                category=self._status_category(
                    response.status_code
                ),
                code=f"HTTP_{response.status_code}",
                stage=operation,
                retryable=response.status_code
                in {429, 502, 503, 504},
                http_status=response.status_code,
                details={
                    "response_body": response.text,
                },
            )

        if not response.content:
            return {}

        try:
            return response.json()

        except ValueError as exc:
            raise TargetProtocolError(
                f"Generic HTTP target returned invalid JSON "
                f"during '{operation}'.",
                operation=operation,
            ) from exc

    @staticmethod
    def _status_category(
        status_code: int,
    ) -> ErrorCategory:
        """Map HTTP failures into canonical error categories."""

        if status_code == 400:
            return ErrorCategory.VALIDATION

        if status_code == 401:
            return ErrorCategory.AUTHENTICATION

        if status_code == 403:
            return ErrorCategory.AUTHORIZATION

        if status_code == 404:
            return ErrorCategory.NOT_FOUND

        if status_code == 409:
            return ErrorCategory.CONFLICT

        if status_code == 429:
            return ErrorCategory.RATE_LIMIT

        if status_code >= 500:
            return ErrorCategory.CONNECTION

        return ErrorCategory.INVALID_RESPONSE