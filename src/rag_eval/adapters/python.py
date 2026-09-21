"""In-process adapter for local Python implementations of Target Protocol v1."""

import inspect
from collections.abc import AsyncIterator
from typing import Any, TypeVar

from pydantic import BaseModel, ValidationError

from rag_eval.adapters.base import DocumentUpload
from rag_eval.adapters.errors import (
    TargetAdapterError,
    TargetProtocolError,
    UnsupportedCapabilityError,
)
from rag_eval.adapters.loader import target_method
from rag_eval.models import (
    Chunk,
    CreateCorpusRequest,
    CreateCorpusResponse,
    ErrorCategory,
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


class PythonTargetAdapter:
    """Normalize an in-process target behind the common adapter contract.

    The target receives canonical request models and returns canonical models
    or dictionaries that validate as those models.  This adapter performs no
    persistence, retries, latency measurement, or capability emulation.
    """

    def __init__(self, target: object) -> None:
        """Wrap a previously loaded Python target implementation."""
        self._target = target
        self._capabilities: TargetCapabilities | None = None

    async def capabilities(self) -> TargetCapabilities:
        """Discover and cache the target's advertised capabilities."""
        if self._capabilities is None:
            self._capabilities = await self._invoke_and_normalize(
                "capabilities", TargetCapabilities
            )
        return self._capabilities

    async def health(self) -> HealthStatus | None:
        """Return health when the local target implements a health operation."""

        method = getattr(self._target, "health", None)

        if not callable(method):
            return None

        return await self._invoke_and_normalize(
            "health",
            HealthStatus,
        )

    async def create_corpus(self, request: CreateCorpusRequest) -> CreateCorpusResponse:
        """Create a corpus when target ingestion is advertised."""
        await self._require_any_capability(
            "create_corpus", "document_ingestion", "chunk_ingestion"
        )
        return await self._invoke_and_normalize(
            "create_corpus", CreateCorpusResponse, request
        )

    async def get_corpus(self, corpus_id: str) -> CreateCorpusResponse:
        """Get corpus state when target ingestion is advertised."""
        await self._require_any_capability(
            "get_corpus", "document_ingestion", "chunk_ingestion"
        )
        return await self._invoke_and_normalize(
            "get_corpus", CreateCorpusResponse, corpus_id
        )

    async def delete_corpus(self, corpus_id: str) -> None:
        """Delete a corpus when target ingestion is advertised."""
        await self._require_any_capability(
            "delete_corpus", "document_ingestion", "chunk_ingestion"
        )
        await self._invoke("delete_corpus", corpus_id)

    async def upload_document(
        self, corpus_id: str, document: DocumentUpload
    ) -> Operation:
        """Pass document payload mechanics directly to the local target."""
        await self._require_capability("upload_document", "document_ingestion")
        return await self._invoke_and_normalize(
            "upload_document", Operation, corpus_id, document
        )

    async def upload_chunks(
        self, corpus_id: str, chunks: AsyncIterator[Chunk]
    ) -> Operation:
        """Pass the chunk iterator through without collecting it."""
        await self._require_capability("upload_chunks", "chunk_ingestion")
        return await self._invoke_and_normalize(
            "upload_chunks", Operation, corpus_id, chunks
        )

    async def get_operation(self, operation_id: str) -> Operation:
        """Get ingestion-operation state when target ingestion is advertised."""
        await self._require_any_capability(
            "get_operation", "document_ingestion", "chunk_ingestion"
        )
        return await self._invoke_and_normalize(
            "get_operation", Operation, operation_id
        )

    async def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        """Retrieve through the target without altering retrieval stages."""
        await self._require_capability("retrieve", "retrieval")
        return await self._invoke_and_normalize("retrieve", RetrieveResponse, request)

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Execute a canonical non-streaming query."""
        await self._require_capability("query", "query")
        return await self._invoke_and_normalize("query", QueryResponse, request)

    async def stream_query(self, request: QueryRequest) -> AsyncIterator[QueryEvent]:
        """Yield normalized target events without buffering or reordering them."""
        await self._require_capability("stream_query", "streaming")
        result = await self._invoke_stream(request)
        if not hasattr(result, "__aiter__"):
            raise TargetProtocolError(
                "Target stream_query must return an async iterator.",
                operation="stream_query",
            )
        try:
            async for event in result:
                yield self._normalize(event, QueryEvent, "stream_query")
        except TargetAdapterError:
            raise
        except Exception as exc:
            raise TargetAdapterError(
                f"Target operation 'stream_query' raised {type(exc).__name__}.",
                category=ErrorCategory.INTERNAL,
                code="TARGET_OPERATION_ERROR",
                stage="stream_query",
            ) from exc

    async def recover_request(self, request_id: str) -> RequestRecoveryResult:
        """Recover a prior request when recovery is advertised."""
        await self._require_capability("recover_request", "request_recovery")
        return await self._invoke_and_normalize(
            "recover_request", RequestRecoveryResult, request_id
        )

    async def _require_capability(self, operation: str, capability: str) -> None:
        """Reject an optional operation before the target is invoked."""
        capabilities = await self.capabilities()
        if not getattr(capabilities, capability):
            raise UnsupportedCapabilityError(capability, operation)

    async def _require_any_capability(
        self, operation: str, *capability_names: str
    ) -> None:
        """Require at least one advertised capability for a shared operation."""
        capabilities = await self.capabilities()
        if not any(getattr(capabilities, name) for name in capability_names):
            raise UnsupportedCapabilityError(" or ".join(capability_names), operation)

    async def _invoke_and_normalize(
        self, operation: str, model_type: type[ModelT], *args: object
    ) -> ModelT:
        """Invoke a target method then validate its canonical response model."""
        value = await self._invoke(operation, *args)
        return self._normalize(value, model_type, operation)

    async def _invoke(self, operation: str, *args: object) -> Any:
        """Invoke an async target operation and normalize target exceptions."""
        method = target_method(self._target, operation)
        try:
            value = method(*args)
            if not inspect.isawaitable(value):
                raise TargetProtocolError(
                    f"Target operation '{operation}' must be async.",
                    operation=operation,
                )
            return await value
        except TargetAdapterError:
            raise
        except Exception as exc:
            raise TargetAdapterError(
                f"Target operation '{operation}' raised {type(exc).__name__}.",
                category=ErrorCategory.INTERNAL,
                code="TARGET_OPERATION_ERROR",
                stage=operation,
            ) from exc

    async def _invoke_stream(self, request: QueryRequest) -> Any:
        """Invoke a streaming operation that may be an async generator or coroutine."""
        method = target_method(self._target, "stream_query")
        try:
            value = method(request)
            if inspect.isawaitable(value):
                value = await value
            return value
        except TargetAdapterError:
            raise
        except Exception as exc:
            raise TargetAdapterError(
                f"Target operation 'stream_query' raised {type(exc).__name__}.",
                category=ErrorCategory.INTERNAL,
                code="TARGET_OPERATION_ERROR",
                stage="stream_query",
            ) from exc

    async def aclose(self) -> None:
        """Release adapter resources."""

        return None

    @staticmethod
    def _normalize(value: Any, model_type: type[ModelT], operation: str) -> ModelT:
        """Validate a returned model or dictionary as its canonical response."""
        try:
            return model_type.model_validate(value)
        except (TypeError, ValidationError) as exc:
            raise TargetProtocolError(
                f"Target returned malformed output for '{operation}'.",
                operation=operation,
                details={"model": model_type.__name__},
            ) from exc
