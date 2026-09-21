"""Transport-independent contract for evaluated targets.

This module defines the boundary between evaluation execution and concrete
target adapters. Every adapter accepts and returns canonical protocol models
while keeping transport, authentication, and provider-specific behavior out
of the evaluation engine.
"""

from collections.abc import AsyncIterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable

from rag_eval.models import (
    Chunk,
    CreateCorpusRequest,
    CreateCorpusResponse,
    Document,
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

DocumentContent = bytes | Path | BinaryIO


@dataclass(frozen=True, slots=True)
class DocumentUpload:
    """Document identity plus transport-local content for target ingestion.

    ``document`` carries canonical evaluator-owned identity. ``content``
    remains transport-bound bytes, a stream, or a path so document payloads
    do not become in-memory canonical protocol models.
    """

    document: Document
    content: DocumentContent


@dataclass(frozen=True, slots=True)
class ResolvedTargetCredentials:
    """Transient plaintext credentials supplied to an adapter at runtime.

    These values are resolved from SecretRef objects immediately before
    adapter construction. They must never be persisted, serialized into
    target configuration, or returned through the API.
    """

    bearer_token: str | None = None
    api_key: str | None = None
    api_key_header: str = "X-API-Key"

    # Resolved secret-valued headers such as:
    # {"X-Custom-Token": "..."}
    headers: Mapping[str, str] = field(default_factory=dict)


@runtime_checkable
class TargetAdapter(Protocol):
    """Invoke an evaluated target exclusively through canonical models.

    Optional target operations remain part of the common adapter contract.
    Implementations raise ``UnsupportedCapabilityError`` when an advertised
    capability does not support an attempted operation.

    ``health`` is different: lack of a health mechanism is valid and returns
    ``None``. Target management interprets that as UNVERIFIED connectivity.
    """

    async def capabilities(self) -> TargetCapabilities:
        """Return capabilities exposed or normalized by this adapter."""
        ...

    async def health(self) -> HealthStatus | None:
        """Return operational health, or None if health cannot be verified."""
        ...

    async def create_corpus(
        self,
        request: CreateCorpusRequest,
    ) -> CreateCorpusResponse:
        """Create a target-owned evaluation corpus."""
        ...

    async def get_corpus(
        self,
        corpus_id: str,
    ) -> CreateCorpusResponse:
        """Return the current state of a target-owned corpus."""
        ...

    async def delete_corpus(
        self,
        corpus_id: str,
    ) -> None:
        """Delete an isolated target-owned evaluation corpus."""
        ...

    async def upload_document(
        self,
        corpus_id: str,
        document: DocumentUpload,
    ) -> Operation:
        """Upload one document and return its target-side ingestion operation."""
        ...

    async def upload_chunks(
        self,
        corpus_id: str,
        chunks: AsyncIterator[Chunk],
    ) -> Operation:
        """Upload chunks without collecting the entire corpus in memory."""
        ...

    async def get_operation(
        self,
        operation_id: str,
    ) -> Operation:
        """Return the current state of a target-side asynchronous operation."""
        ...

    async def retrieve(
        self,
        request: RetrieveRequest,
    ) -> RetrieveResponse:
        """Perform independent retrieval and preserve supplied stages."""
        ...

    async def query(
        self,
        request: QueryRequest,
    ) -> QueryResponse:
        """Perform a non-streaming canonical target query."""
        ...

    def stream_query(
        self,
        request: QueryRequest,
    ) -> AsyncIterator[QueryEvent]:
        """Yield target-produced streaming events in original order."""
        ...

    async def recover_request(
        self,
        request_id: str,
    ) -> RequestRecoveryResult:
        """Look up a prior logical request when recovery is supported."""
        ...

    async def aclose(self) -> None:
        """Release adapter-owned resources."""
        ...