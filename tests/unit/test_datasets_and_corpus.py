"""Tests for canonical benchmark loading and corpus preparation."""

from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest

from rag_eval.adapters import DocumentUpload, TargetAdapter
from rag_eval.adapters.errors import TargetAdapterError
from rag_eval.artifacts import ArtifactService
from rag_eval.config.models import CorpusConfig
from rag_eval.datasets import DatasetValidationError
from rag_eval.datasets.manifest import load_benchmark_file, validate_benchmark
from rag_eval.datasets.native import load_cases, load_chunks, load_documents
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import (
    ArtifactRef,
    Benchmark,
    BenchmarkManifest,
    Chunk,
    CorpusMode,
    CreateCorpusRequest,
    CreateCorpusResponse,
    Document,
    Operation,
    OperationStatus,
    TargetCapabilities,
    TargetInfo,
)
from rag_eval.services.corpus import CorpusPreparationService


class RecordingTargetRepository:
    """In-memory target repository boundary for corpus tests."""

    def __init__(self) -> None:
        self.corpora: list[object] = []
        self.documents: list[str] = []

    async def persist_corpus(self, record: object) -> None:
        self.corpora.append(record)

    async def persist_document(self, corpus_id: str, document: Document) -> None:
        del corpus_id
        self.documents.append(document.document_id)


class RecordingArtifactService:
    """Artifact service substitute returning deterministic document bytes."""

    async def get(self, artifact: ArtifactRef) -> bytes:
        return f"content:{artifact.artifact_id}".encode()


class IngestionTarget:
    """Target adapter substitute for corpus preparation tests."""

    def __init__(self, *, documents: bool = True, chunks: bool = True) -> None:
        self._capabilities = TargetCapabilities(
            target=TargetInfo(name="ingestion-target"),
            query=True,
            document_ingestion=documents,
            chunk_ingestion=chunks,
        )
        self.uploaded_documents: list[str] = []
        self.uploaded_chunks: list[list[Chunk]] = []
        self.operation_states: list[OperationStatus] = [
            OperationStatus.SUCCEEDED,
            OperationStatus.SUCCEEDED,
            OperationStatus.SUCCEEDED,
        ]

    async def capabilities(self) -> TargetCapabilities:
        return self._capabilities

    async def create_corpus(self, request: CreateCorpusRequest) -> CreateCorpusResponse:
        del request
        return CreateCorpusResponse(corpus_id="target-corpus", status="EMPTY")

    async def upload_document(
        self, corpus_id: str, document: DocumentUpload
    ) -> Operation:
        del corpus_id
        self.uploaded_documents.append(document.document.document_id)
        return Operation(
            operation_id="document-operation",
            kind="DOCUMENT_INGESTION",
            status=self.operation_states.pop(0),
        )

    async def upload_chunks(
        self, corpus_id: str, chunks: AsyncIterator[Chunk]
    ) -> Operation:
        del corpus_id
        self.uploaded_chunks.append([chunk async for chunk in chunks])
        return Operation(
            operation_id="chunk-operation",
            kind="CHUNK_INGESTION",
            status=self.operation_states.pop(0),
        )

    async def get_operation(self, operation_id: str) -> Operation:
        return Operation(
            operation_id=operation_id,
            kind="INGESTION",
            status=self.operation_states.pop(0),
        )


def _benchmark_payload() -> dict[str, object]:
    """Return a complete canonical benchmark payload."""
    return {
        "benchmark_id": "benchmark-1",
        "name": "fixture",
        "version": "1",
        "corpus_mode": "DOCUMENTS",
        "documents": [
            {
                "document_id": "document-1",
                "filename": "source.txt",
                "artifact": {
                    "artifact_id": "artifact-1",
                    "uri": "file:///source.txt",
                },
            }
        ],
        "chunks": [
            {
                "chunk_id": "chunk-1",
                "document_id": "document-1",
                "text": "source content",
            }
        ],
        "cases": [
            {
                "case_id": "case-1",
                "query": "Question",
                "gold_evidence": [
                    {"evidence_id": "evidence-1", "document_id": "document-1"}
                ],
            }
        ],
    }


def _benchmark() -> Benchmark:
    """Build a canonical benchmark with all supported corpus records."""
    payload = _benchmark_payload()
    return Benchmark.model_validate(
        {
            "manifest": {
                key: value
                for key, value in payload.items()
                if key not in {"documents", "chunks", "cases"}
            },
            "documents": payload["documents"],
            "chunks": payload["chunks"],
            "cases": payload["cases"],
        }
    )


def _corpus_service(
    target: IngestionTarget,
    repository: RecordingTargetRepository,
) -> CorpusPreparationService:
    """Adapt deterministic fakes to the production service boundary."""
    return CorpusPreparationService(
        "target-1",
        cast(TargetAdapter, target),
        cast(TargetRepository, repository),
        artifact_service=cast(ArtifactService, RecordingArtifactService()),
        poll_interval_seconds=0,
    )


def test_canonical_benchmark_file_loads_and_validates(tmp_path: Path) -> None:
    """Portable benchmark files become canonical Benchmark models."""
    import json

    path = tmp_path / "benchmark.json"
    path.write_text(json.dumps(_benchmark_payload()), encoding="utf-8")

    benchmark = load_benchmark_file(path)

    assert benchmark.manifest.benchmark_id == "benchmark-1"
    assert [case.case_id for case in benchmark.cases] == ["case-1"]
    assert [document.document_id for document in benchmark.documents] == [
        "document-1"
    ]
    assert [chunk.chunk_id for chunk in benchmark.chunks] == ["chunk-1"]


def test_canonical_record_loaders_support_jsonl(tmp_path: Path) -> None:
    """Cases, documents, and chunks use the same validated loaders."""
    case_path = tmp_path / "cases.jsonl"
    case_path.write_text('{"case_id":"case-1","query":"Q"}\n', encoding="utf-8")
    document_path = tmp_path / "documents.jsonl"
    document_path.write_text('{"document_id":"document-1"}\n', encoding="utf-8")
    chunk_path = tmp_path / "chunks.jsonl"
    chunk_path.write_text(
        '{"chunk_id":"chunk-1","document_id":"document-1","text":"T"}\n',
        encoding="utf-8",
    )

    assert load_cases(case_path)[0].case_id == "case-1"
    assert load_documents(document_path)[0].document_id == "document-1"
    assert load_chunks(chunk_path)[0].chunk_id == "chunk-1"


@pytest.mark.parametrize(
    ("record_type", "message"),
    [
        ("cases", "duplicate case_id"),
        ("documents", "duplicate document_id"),
        ("chunks", "duplicate chunk_id"),
    ],
)
def test_benchmark_validation_rejects_duplicate_owned_records(
    record_type: str, message: str
) -> None:
    """Benchmark-owned identities are unique within their resource type."""
    benchmark = _benchmark()
    records = getattr(benchmark, record_type)
    records.append(records[0])

    with pytest.raises(DatasetValidationError, match=message):
        validate_benchmark(benchmark)


def test_benchmark_validation_rejects_unknown_references() -> None:
    """Chunks and gold evidence must reference benchmark-owned documents."""
    benchmark = _benchmark()
    benchmark.chunks[0].document_id = "missing-document"

    with pytest.raises(DatasetValidationError, match="unknown document"):
        validate_benchmark(benchmark)


@pytest.mark.anyio
async def test_corpus_preparation_uses_canonical_documents_and_chunks() -> None:
    """Preparation persists target state while uploading canonical resources."""
    benchmark = _benchmark()
    repository = RecordingTargetRepository()
    target = IngestionTarget()

    documents = await _corpus_service(target, repository).prepare(
        benchmark, CorpusConfig(mode=CorpusMode.DOCUMENTS)
    )
    chunks = await _corpus_service(target, repository).prepare(
        benchmark, CorpusConfig(mode=CorpusMode.CHUNKS)
    )
    external = await _corpus_service(target, repository).prepare(
        benchmark,
        CorpusConfig(mode=CorpusMode.EXTERNAL, corpus_id="external-1"),
    )

    assert documents.status == "READY"
    assert chunks.status == "READY"
    assert external.corpus_id == "external-1"
    assert target.uploaded_documents == ["document-1"]
    assert [chunk.chunk_id for chunk in target.uploaded_chunks[0]] == ["chunk-1"]
    assert repository.documents == ["document-1"]


@pytest.mark.anyio
async def test_corpus_preparation_rejects_unsupported_and_failed_ingestion() -> None:
    """Capability gaps and terminal target failures are not reported as ready."""
    benchmark = _benchmark()
    repository = RecordingTargetRepository()

    with pytest.raises(TargetAdapterError) as unsupported:
        await _corpus_service(IngestionTarget(documents=False), repository).prepare(
            benchmark, CorpusConfig(mode=CorpusMode.DOCUMENTS)
        )
    assert unsupported.value.to_error_record().category == "UNSUPPORTED_CAPABILITY"

    failed = IngestionTarget()
    failed.operation_states = [OperationStatus.FAILED]
    with pytest.raises(TargetAdapterError, match="ended as"):
        await _corpus_service(failed, repository).prepare(
            benchmark, CorpusConfig(mode=CorpusMode.DOCUMENTS)
        )


@pytest.mark.anyio
async def test_corpus_preparation_requires_available_mode_and_artifact() -> None:
    """Incomplete canonical benchmarks fail before target-side mutation."""
    manifest = BenchmarkManifest(
        benchmark_id="benchmark-empty",
        name="empty",
        version="1",
        corpus_mode=CorpusMode.DOCUMENTS,
    )
    empty = Benchmark(manifest=manifest)
    with pytest.raises(ValueError, match="has no cases"):
        await _corpus_service(IngestionTarget(), RecordingTargetRepository()).prepare(
            empty, CorpusConfig(mode=CorpusMode.DOCUMENTS)
        )

    benchmark = _benchmark()
    benchmark.documents[0].artifact = None
    with pytest.raises(ValueError, match="no stored artifact"):
        await _corpus_service(IngestionTarget(), RecordingTargetRepository()).prepare(
            benchmark, CorpusConfig(mode=CorpusMode.DOCUMENTS)
        )
