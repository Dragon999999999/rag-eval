"""Transport-independent contract for evaluated targets.

This module is the boundary between execution and target transports.  Every
implementation returns canonical Stage 2 models, may perform target I/O, and
raises normalized adapter errors for unsupported or malformed operations.
"""

from collections.abc import AsyncIterator
from dataclasses import dataclass
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

    ``document`` carries the canonical evaluator-owned identity.  ``content``
    deliberately remains a transport-bound byte, stream, or path so document
    payloads do not become an in-memory canonical protocol model.
    """

    document: Document
    content: DocumentContent


@runtime_checkable
class TargetAdapter(Protocol):
    """Invoke an evaluated target exclusively through canonical models.

    Optional methods are part of the common contract.  Implementations must
    raise ``UnsupportedCapabilityError`` before invoking a target operation
    that has not been advertised by ``capabilities``.
    """

    async def capabilities(self) -> TargetCapabilities:
        """Return the target's advertised protocol capabilities."""

    async def health(self) -> HealthStatus:
        """Return operational health, separate from evaluation evidence."""

    async def create_corpus(self, request: CreateCorpusRequest) -> CreateCorpusResponse:
        """Create a target-owned evaluation corpus."""

    async def get_corpus(self, corpus_id: str) -> CreateCorpusResponse:
        """Return the current state of a target-owned corpus."""

    async def delete_corpus(self, corpus_id: str) -> None:
        """Delete an isolated target-owned evaluation corpus."""

    async def upload_document(
        self, corpus_id: str, document: DocumentUpload
    ) -> Operation:
        """Upload one document and return its target-side ingestion operation."""

    async def upload_chunks(
        self, corpus_id: str, chunks: AsyncIterator[Chunk]
    ) -> Operation:
        """Upload chunks without requiring all corpus chunks in memory."""

    async def get_operation(self, operation_id: str) -> Operation:
        """Return the current state of a target-side asynchronous operation."""

    async def retrieve(self, request: RetrieveRequest) -> RetrieveResponse:
        """Perform independent retrieval and preserve all supplied stages."""

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Perform a non-streaming canonical target query."""

    def stream_query(self, request: QueryRequest) -> AsyncIterator[QueryEvent]:
        """Yield target-produced streaming events in their original order."""

    async def recover_request(self, request_id: str) -> RequestRecoveryResult:
        """Look up a prior logical request when recovery is advertised."""
