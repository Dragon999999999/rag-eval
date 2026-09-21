from collections.abc import AsyncIterator

from rag_eval.adapters import (
    DocumentUpload,
    TargetAdapter,
)
from rag_eval.adapters.errors import UnsupportedCapabilityError
from rag_eval.models import (
    Answer,
    Chunk,
    CreateCorpusRequest,
    CreateCorpusResponse,
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
)


class MyAdapter:
    async def capabilities(self) -> TargetCapabilities:
        return TargetCapabilities(
            protocol_version="1.0",
            target=TargetInfo(
                name="My custom target",
                implementation="custom-python",
            ),
            query=True,
            retrieval=False,
        )

    async def health(self) -> HealthStatus | None:
        return None

    async def query(
        self,
        request: QueryRequest,
    ) -> QueryResponse:
        # Any custom HTTP/database/library logic can live here.
        result = f"received: {request.query}"

        return QueryResponse(
            request_id=request.request_id,
            answer=Answer(
                text=result,
            ),
        )

    async def retrieve(
        self,
        request: RetrieveRequest,
    ) -> RetrieveResponse:
        raise UnsupportedCapabilityError(
            "retrieval",
            "retrieve",
        )

    async def create_corpus(
        self,
        request: CreateCorpusRequest,
    ) -> CreateCorpusResponse:
        raise UnsupportedCapabilityError(
            "document_ingestion",
            "create_corpus",
        )

    async def get_corpus(
        self,
        corpus_id: str,
    ) -> CreateCorpusResponse:
        raise UnsupportedCapabilityError(
            "document_ingestion",
            "get_corpus",
        )

    async def delete_corpus(
        self,
        corpus_id: str,
    ) -> None:
        raise UnsupportedCapabilityError(
            "document_ingestion",
            "delete_corpus",
        )

    async def upload_document(
        self,
        corpus_id: str,
        document: DocumentUpload,
    ) -> Operation:
        raise UnsupportedCapabilityError(
            "document_ingestion",
            "upload_document",
        )

    async def upload_chunks(
        self,
        corpus_id: str,
        chunks: AsyncIterator[Chunk],
    ) -> Operation:
        raise UnsupportedCapabilityError(
            "chunk_ingestion",
            "upload_chunks",
        )

    async def get_operation(
        self,
        operation_id: str,
    ) -> Operation:
        raise UnsupportedCapabilityError(
            "document_ingestion",
            "get_operation",
        )

    async def stream_query(
        self,
        request: QueryRequest,
    ) -> AsyncIterator[QueryEvent]:
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
        raise UnsupportedCapabilityError(
            "request_recovery",
            "recover_request",
        )

    async def aclose(self) -> None:
        return None


def create_adapter() -> TargetAdapter:
    return MyAdapter()