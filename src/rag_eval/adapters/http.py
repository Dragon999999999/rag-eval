"""Async HTTP implementation of Target Protocol v1.

The adapter owns one reusable ``httpx.AsyncClient`` and translates HTTP
responses into the same canonical models used by the local Python adapter.
It deliberately performs no retry, polling, persistence, or metric work.
"""

import json
import time
from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any, TypeVar
from urllib.parse import quote

import httpx
from pydantic import BaseModel, ValidationError

from rag_eval.adapters.base import DocumentUpload
from rag_eval.adapters.errors import (
    TargetAdapterError,
    TargetProtocolError,
    UnsupportedCapabilityError,
)
from rag_eval.models import (
    Chunk,
    CreateCorpusRequest,
    CreateCorpusResponse,
    ErrorCategory,
    ErrorRecord,
    HealthStatus,
    Operation,
    QueryEvent,
    QueryRequest,
    QueryResponse,
    RequestRecoveryResult,
    RetrieveRequest,
    RetrieveResponse,
    TargetCapabilities,
)

ModelT = TypeVar("ModelT", bound=BaseModel)
_STATUS_CATEGORIES = {
    400: ErrorCategory.VALIDATION,
    401: ErrorCategory.AUTHENTICATION,
    403: ErrorCategory.AUTHORIZATION,
    404: ErrorCategory.NOT_FOUND,
    409: ErrorCategory.CONFLICT,
    413: ErrorCategory.RESOURCE_EXHAUSTED,
    415: ErrorCategory.VALIDATION,
    422: ErrorCategory.VALIDATION,
    429: ErrorCategory.RATE_LIMIT,
    500: ErrorCategory.INTERNAL,
    502: ErrorCategory.INVALID_RESPONSE,
    503: ErrorCategory.CONNECTION,
    504: ErrorCategory.TIMEOUT,
}


@dataclass(frozen=True, slots=True)
class TransportMetadata:
    """Raw transport information retained independently of canonical responses."""

    status_code: int
    headers: dict[str, str]
    raw_body: bytes | None
    idempotency_replayed: bool
    started_at_monotonic: float
    headers_at_monotonic: float
    completed_at_monotonic: float | None
    first_event_at_monotonic: float | None = None


class HttpTargetAdapter:
    """Call a remote Target Protocol v1 server with a pooled async HTTP client.

    Instances must be closed with ``aclose`` or used as an async context
    manager unless a caller-owned client is supplied.  ``last_transport`` is
    intentionally separate from target traces so callers can preserve raw HTTP
    material later without changing canonical response models.
    """

    def __init__(
        self,
        base_url: str,
        *,
        connect_timeout: float = 10.0,
        request_timeout: float = 60.0,
        total_timeout: float = 120.0,
        bearer_token: str | None = None,
        api_key: str | None = None,
        api_key_header: str = "X-API-Key",
        client: httpx.AsyncClient | None = None,
    ) -> None:
        """Create a reusable HTTP adapter.

        Args:
            base_url: Target origin or root URL, without a protocol path.
            connect_timeout: Maximum connection-establishment time in seconds.
            request_timeout: Read and write timeout in seconds.
            total_timeout: Pool-acquisition timeout in seconds.
            bearer_token: Optional token sent in the Authorization header.
            api_key: Optional key sent using ``api_key_header``.
            api_key_header: Header name for an explicit API key.
            client: Optional caller-owned client, useful for deterministic tests.

        Raises:
            ValueError: If incompatible authentication modes are configured.
        """
        if bearer_token is not None and api_key is not None:
            raise ValueError("Configure either bearer_token or api_key, not both.")
        protocol_root = f"{base_url.rstrip('/')}/eval/v1/"
        headers = {"X-Rag-Eval-Protocol": "1"}
        if bearer_token is not None:
            headers["Authorization"] = f"Bearer {bearer_token}"
        elif api_key is not None:
            headers[api_key_header] = api_key
        self._client = client or httpx.AsyncClient(
            base_url=protocol_root,
            headers=headers,
            timeout=httpx.Timeout(
                timeout=total_timeout,
                connect=connect_timeout,
                read=request_timeout,
                write=request_timeout,
                pool=total_timeout,
            ),
        )
        if client is not None:
            self._client.headers.update(headers)
            self._client.base_url = httpx.URL(protocol_root)
        self._owns_client = client is None
        self._capabilities: TargetCapabilities | None = None
        self.last_transport: TransportMetadata | None = None

    async def __aenter__(self) -> "HttpTargetAdapter":
        """Return this adapter for async-context-manager use."""
        return self

    async def __aexit__(self, *args: object) -> None:
        """Close the reusable client when leaving an async context."""
        await self.aclose()

    async def aclose(self) -> None:
        """Close the underlying client, including its pooled connections."""
        if self._owns_client:
            await self._client.aclose()

    async def capabilities(self) -> TargetCapabilities:
        """Discover, validate, and cache target capabilities."""
        if self._capabilities is None:
            payload = await self._json_request("capabilities", "GET", "capabilities")
            self._capabilities = self._normalize_capabilities(payload)
        return self._capabilities

    async def health(self) -> HealthStatus:
        """Return the target's canonical operational health status."""
        return await self._model_request("health", HealthStatus, "GET", "health")

    async def config_schema(self) -> dict[str, Any]:
        """Return target-provided generic JSON Schema without model generation."""
        return await self._json_request("config_schema", "GET", "config-schema")

    async def create_corpus(self, request: CreateCorpusRequest) -> CreateCorpusResponse:
        """Create a target corpus when ingestion is advertised."""
        await self._require_any_capability(
            "create_corpus", "document_ingestion", "chunk_ingestion"
        )
        return await self._model_request(
            "create_corpus",
            CreateCorpusResponse,
            "POST",
            "corpora",
            json_body=request.model_dump(mode="json"),
            request_id=request.request_id,
        )

    async def get_corpus(self, corpus_id: str) -> CreateCorpusResponse:
        """Get a corpus state when ingestion is advertised."""
        await self._require_any_capability(
            "get_corpus", "document_ingestion", "chunk_ingestion"
        )
        return await self._model_request(
            "get_corpus", CreateCorpusResponse, "GET", self._corpus_path(corpus_id)
        )

    async def delete_corpus(self, corpus_id: str) -> None:
        """Delete a target-owned corpus without adding polling behavior."""
        await self._require_any_capability(
            "delete_corpus", "document_ingestion", "chunk_ingestion"
        )
        await self._json_request(
            "delete_corpus", "DELETE", self._corpus_path(corpus_id)
        )

    async def upload_document(
        self, corpus_id: str, document: DocumentUpload
    ) -> Operation:
        """Upload a document multipart body while preserving its canonical identity."""
        await self._require_capability("upload_document", "document_ingestion")
        metadata = document.document.model_dump(mode="json", exclude_none=True)
        content = document.content
        filename = document.document.filename or "document"
        mime_type = document.document.mime_type or "application/octet-stream"
        path = self._corpus_path(corpus_id) + "/documents"
        if isinstance(content, Path):
            with content.open("rb") as file_handle:
                return await self._multipart_operation(
                    path,
                    filename,
                    file_handle,
                    mime_type,
                    metadata,
                    document.document.document_id,
                )
        return await self._multipart_operation(
            path, filename, content, mime_type, metadata, document.document.document_id
        )

    async def upload_chunks(
        self, corpus_id: str, chunks: AsyncIterator[Chunk]
    ) -> Operation:
        """Upload bounded JSON chunk batches and return the final target operation."""
        await self._require_capability("upload_chunks", "chunk_ingestion")
        limit = (await self.capabilities()).limits.get("max_chunks_per_request", 1000)
        if limit < 1:
            raise TargetProtocolError(
                "Target advertised an invalid max_chunks_per_request limit.",
                operation="upload_chunks",
            )
        batch: list[dict[str, Any]] = []
        final_operation: Operation | None = None
        batch_number = 0
        async for chunk in chunks:
            batch.append(chunk.model_dump(mode="json"))
            if len(batch) == limit:
                final_operation = await self._upload_chunk_batch(
                    corpus_id, batch, batch_number
                )
                batch = []
                batch_number += 1
        if batch:
            final_operation = await self._upload_chunk_batch(
                corpus_id, batch, batch_number
            )
        if final_operation is None:
            raise TargetProtocolError(
                "Chunk upload requires at least one chunk.", operation="upload_chunks"
            )
        return final_operation

    async def get_operation(self, operation_id: str) -> Operation:
        """Get one asynchronous operation state without polling it."""
        await self._require_any_capability(
            "get_operation", "document_ingestion", "chunk_ingestion"
        )
        return await self._model_request(
            "get_operation",
            Operation,
            "GET",
            f"operations/{quote(operation_id, safe='')}",
        )

    async def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        """Perform independent retrieval and preserve every returned stage."""
        await self._require_capability("retrieve", "retrieval")
        return await self._model_request(
            "retrieve",
            RetrieveResponse,
            "POST",
            "retrieve",
            json_body=request.model_dump(mode="json"),
            request_id=request.request_id,
        )

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Perform a non-streaming query without changing its context policy."""
        await self._require_capability("query", "query")
        return await self._model_request(
            "query",
            QueryResponse,
            "POST",
            "query",
            json_body=request.model_dump(mode="json"),
            request_id=request.request_id,
        )

    async def stream_query(self, request: QueryRequest) -> AsyncIterator[QueryEvent]:
        """Incrementally parse an SSE query stream in arrival order."""
        await self._require_capability("stream_query", "streaming")
        headers = self._request_headers(request.request_id)
        headers["Accept"] = "text/event-stream"
        started_at = time.monotonic()
        first_event_at: float | None = None
        sequence: int | None = None
        event_lines: list[str] = []
        try:
            async with self._client.stream(
                "POST",
                "query",
                headers=headers,
                json=request.model_dump(mode="json"),
            ) as response:
                headers_at = time.monotonic()
                if response.is_error:
                    raw_body = await response.aread()
                    self._set_transport(
                        response, raw_body, started_at, headers_at, time.monotonic()
                    )
                    self._raise_http_error("stream_query", response, raw_body)
                self._set_transport(response, None, started_at, headers_at, None)
                async for line in response.aiter_lines():
                    if line:
                        if line.startswith("data:"):
                            event_lines.append(line[5:].lstrip())
                        continue
                    if not event_lines:
                        continue
                    raw_event = "\n".join(event_lines)
                    event_lines = []
                    event = self._parse_sse_event(raw_event)
                    if sequence is not None and event.sequence <= sequence:
                        raise TargetProtocolError(
                            "Streaming event sequences must increase monotonically.",
                            operation="stream_query",
                        )
                    sequence = event.sequence
                    if first_event_at is None:
                        first_event_at = time.monotonic()
                    self._set_transport(
                        response,
                        None,
                        started_at,
                        headers_at,
                        None,
                        first_event_at,
                    )
                    yield event
                if event_lines:
                    event = self._parse_sse_event("\n".join(event_lines))
                    if sequence is not None and event.sequence <= sequence:
                        raise TargetProtocolError(
                            "Streaming event sequences must increase monotonically.",
                            operation="stream_query",
                        )
                    yield event
                self._set_transport(
                    response,
                    None,
                    started_at,
                    headers_at,
                    time.monotonic(),
                    first_event_at,
                )
        except TargetAdapterError:
            raise
        except httpx.HTTPError as exc:
            raise self._network_error("stream_query", exc) from exc

    async def recover_request(self, request_id: str) -> RequestRecoveryResult:
        """Look up a prior request when request recovery is advertised."""
        await self._require_capability("recover_request", "request_recovery")
        return await self._model_request(
            "recover_request",
            RequestRecoveryResult,
            "GET",
            f"requests/{quote(request_id, safe='')}",
            request_id=request_id,
        )

    async def _multipart_operation(
        self,
        path: str,
        filename: str,
        content: object,
        mime_type: str,
        metadata: dict[str, Any],
        request_id: str,
    ) -> Operation:
        """Send one protocol multipart document upload and normalize its operation."""
        payload = await self._json_request(
            "upload_document",
            "POST",
            path,
            files={
                "file": (filename, content, mime_type),
                "metadata": (None, json.dumps(metadata), "application/json"),
            },
            request_id=request_id,
        )
        return self._normalize(payload, Operation, "upload_document")

    async def _upload_chunk_batch(
        self, corpus_id: str, chunks: list[dict[str, Any]], batch_number: int
    ) -> Operation:
        """Send one bounded chunk batch without retaining other batches in memory."""
        payload = await self._json_request(
            "upload_chunks",
            "POST",
            self._corpus_path(corpus_id) + "/chunks",
            json_body={"chunks": chunks},
            request_id=f"{corpus_id}:chunks:{batch_number}",
        )
        return self._normalize(payload, Operation, "upload_chunks")

    async def _model_request(
        self,
        operation: str,
        model_type: type[ModelT],
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        request_id: str | None = None,
    ) -> ModelT:
        """Perform a JSON request then validate a canonical response model."""
        payload = await self._json_request(
            operation, method, path, json_body=json_body, request_id=request_id
        )
        return self._normalize(payload, model_type, operation)

    async def _json_request(
        self,
        operation: str,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, object] | None = None,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        """Perform one HTTP operation and retain raw response transport metadata."""
        started_at = time.monotonic()
        try:
            response = await self._client.request(
                method,
                path,
                headers=self._request_headers(request_id),
                json=json_body,
                files=files,
            )
        except httpx.HTTPError as exc:
            raise self._network_error(operation, exc) from exc
        completed_at = time.monotonic()
        raw_body = response.content
        self._set_transport(response, raw_body, started_at, completed_at, completed_at)
        if response.is_error:
            self._raise_http_error(operation, response, raw_body)
        if not raw_body:
            return {}
        try:
            payload = response.json()
        except json.JSONDecodeError as exc:
            raise TargetProtocolError(
                f"Target returned invalid JSON for '{operation}'.", operation=operation
            ) from exc
        if not isinstance(payload, dict):
            raise TargetProtocolError(
                f"Target returned a non-object JSON response for '{operation}'.",
                operation=operation,
            )
        return payload

    async def _require_capability(self, operation: str, capability: str) -> None:
        """Reject an unadvertised optional operation before issuing HTTP."""
        if not getattr(await self.capabilities(), capability):
            raise UnsupportedCapabilityError(capability, operation)

    async def _require_any_capability(
        self, operation: str, *capability_names: str
    ) -> None:
        """Require at least one capability for shared corpus operations."""
        capabilities = await self.capabilities()
        if not any(getattr(capabilities, name) for name in capability_names):
            raise UnsupportedCapabilityError(" or ".join(capability_names), operation)

    def _normalize_capabilities(self, payload: dict[str, Any]) -> TargetCapabilities:
        """Accept both flattened and documented nested capability envelopes."""
        if isinstance(payload.get("capabilities"), dict):
            flattened = dict(payload["capabilities"])
            for key in ("protocol_version", "target", "limits"):
                if key in payload:
                    flattened[key] = payload[key]
            idempotency = payload.get("idempotency")
            if isinstance(idempotency, dict) and "retention_seconds" in idempotency:
                flattened["idempotency_retention_seconds"] = idempotency[
                    "retention_seconds"
                ]
            payload = flattened
        result = self._normalize(payload, TargetCapabilities, "capabilities")
        self._validate_protocol_version(result.protocol_version, "capabilities")
        return result

    @staticmethod
    def _normalize(value: Any, model_type: type[ModelT], operation: str) -> ModelT:
        """Validate JSON returned by the remote target against a canonical model."""
        try:
            return model_type.model_validate(value)
        except (TypeError, ValidationError) as exc:
            raise TargetProtocolError(
                f"Target returned malformed output for '{operation}'.",
                operation=operation,
                details={"model": model_type.__name__},
            ) from exc

    @staticmethod
    def _validate_protocol_version(version: str, operation: str) -> None:
        """Reject protocol versions outside the supported v1 major version."""
        if version.split(".", 1)[0] != "1":
            raise TargetProtocolError(
                f"Unsupported target protocol version '{version}'.", operation=operation
            )

    @staticmethod
    def _corpus_path(corpus_id: str) -> str:
        """Return a safely escaped canonical corpus resource path."""
        return f"corpora/{quote(corpus_id, safe='')}"

    @staticmethod
    def _request_headers(request_id: str | None = None) -> dict[str, str]:
        """Return logical identity headers without generating replacement IDs."""
        if request_id is None:
            return {}
        return {"X-Request-ID": request_id, "Idempotency-Key": request_id}

    def _set_transport(
        self,
        response: httpx.Response,
        raw_body: bytes | None,
        started_at: float,
        headers_at: float,
        completed_at: float | None,
        first_event_at: float | None = None,
    ) -> None:
        """Store transport material without mixing it into target observations."""
        self.last_transport = TransportMetadata(
            status_code=response.status_code,
            headers=dict(response.headers),
            raw_body=raw_body,
            idempotency_replayed=response.headers.get(
                "Idempotency-Replayed", ""
            ).lower()
            == "true",
            started_at_monotonic=started_at,
            headers_at_monotonic=headers_at,
            completed_at_monotonic=completed_at,
            first_event_at_monotonic=first_event_at,
        )

    def _raise_http_error(
        self, operation: str, response: httpx.Response, raw_body: bytes
    ) -> None:
        """Raise a canonical adapter error from a protocol or HTTP status failure."""
        retry_after_ms = self._retry_after_ms(response)
        try:
            payload = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError):
            payload = None
        error_payload = payload.get("error") if isinstance(payload, dict) else None
        if isinstance(error_payload, dict):
            try:
                record = ErrorRecord.model_validate(error_payload)
            except ValidationError:
                record = None
            if record is not None:
                record = record.model_copy(
                    update={
                        "http_status": response.status_code,
                        "retry_after_ms": record.retry_after_ms or retry_after_ms,
                    }
                )
                error = TargetAdapterError(
                    record.message,
                    category=record.category,
                    code=record.code,
                    stage=record.stage or operation,
                    details=record.details,
                    retryable=record.retryable,
                    retry_after_ms=record.retry_after_ms,
                    http_status=response.status_code,
                    provider=record.provider,
                )
                error.record = record
                raise error
        category = _STATUS_CATEGORIES.get(response.status_code, ErrorCategory.UNKNOWN)
        raise TargetAdapterError(
            f"Target returned HTTP {response.status_code} for '{operation}'.",
            category=category,
            code=f"HTTP_{response.status_code}",
            stage=operation,
            details={"response_body": raw_body.decode("utf-8", errors="replace")},
            retryable=response.status_code in {429, 502, 503, 504},
            retry_after_ms=retry_after_ms,
            http_status=response.status_code,
        )

    @staticmethod
    def _retry_after_ms(response: httpx.Response) -> int | None:
        """Parse a Retry-After header without scheduling a retry."""
        retry_after = response.headers.get("Retry-After")
        if retry_after is None:
            return None
        try:
            return max(0, int(float(retry_after) * 1000))
        except ValueError:
            try:
                deadline = parsedate_to_datetime(retry_after)
            except (TypeError, ValueError):
                return None
            if deadline.tzinfo is None:
                deadline = deadline.replace(tzinfo=UTC)
            return max(0, int((deadline - datetime.now(UTC)).total_seconds() * 1000))

    @staticmethod
    def _network_error(operation: str, error: httpx.HTTPError) -> TargetAdapterError:
        """Normalize timeout and connection failures without retrying them."""
        if isinstance(error, httpx.TimeoutException):
            category = ErrorCategory.TIMEOUT
        elif isinstance(error, httpx.ConnectError):
            category = ErrorCategory.CONNECTION
        else:
            category = ErrorCategory.NETWORK
        return TargetAdapterError(
            f"Target HTTP operation '{operation}' failed: {type(error).__name__}.",
            category=category,
            code="HTTP_TRANSPORT_ERROR",
            stage=operation,
        )

    @staticmethod
    def _parse_sse_event(raw_event: str) -> QueryEvent:
        """Validate one SSE data event as a canonical QueryEvent."""
        try:
            payload = json.loads(raw_event)
        except json.JSONDecodeError as exc:
            raise TargetProtocolError(
                "Target emitted invalid JSON in an SSE event.", operation="stream_query"
            ) from exc
        return HttpTargetAdapter._normalize(payload, QueryEvent, "stream_query")
