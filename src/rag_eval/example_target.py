"""Small local Target Protocol v1 implementation used by the bundled example."""

from rag_eval.adapters import DocumentUpload
from rag_eval.models import (
    CreateCorpusRequest,
    CreateCorpusResponse,
    HealthStatus,
    Operation,
    QueryRequest,
    QueryResponse,
    TargetCapabilities,
)


class ExampleTarget:
    """In-memory corpus target for verifying configuration and preparation wiring.

    It exists only as a local example target; it does not retrieve, persist, or
    model real RAG behavior.
    """

    async def capabilities(self) -> TargetCapabilities:
        """Advertise the minimal operations exercised by corpus preparation."""
        return TargetCapabilities(
            target={
                "name": "rag-eval-example-target",
                "version": "1",
                "implementation": "in-memory-example",
            },
            query=True,
            document_ingestion=True,
            chunk_ingestion=True,
        )

    async def health(self) -> HealthStatus:
        """Report that the local example target is operational."""
        return HealthStatus(status="READY", target={"name": "rag-eval-example-target"})

    async def create_corpus(self, request: CreateCorpusRequest) -> CreateCorpusResponse:
        """Return a stable example corpus identity without external side effects."""
        return CreateCorpusResponse(corpus_id="example-corpus", status="EMPTY")

    async def upload_document(
        self, corpus_id: str, document: DocumentUpload
    ) -> Operation:
        """Accept one example document and complete ingestion immediately."""
        return Operation(
            operation_id=f"document-{document.document.document_id}",
            kind="DOCUMENT_INGESTION",
            status="SUCCEEDED",
        )

    async def upload_chunks(self, corpus_id: str, chunks: object) -> Operation:
        """Accept chunks for the example without materializing target-side state."""
        return Operation(
            operation_id="example-chunks", kind="CHUNK_INGESTION", status="SUCCEEDED"
        )

    async def query(self, request: QueryRequest) -> QueryResponse:
        """Return a minimal response so the target satisfies the loader contract."""
        return QueryResponse(request_id=request.request_id, answer={"text": "example"})
