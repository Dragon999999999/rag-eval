"""Native dataset and corpus-preparation service behavior."""

import hashlib
from collections.abc import AsyncIterator
from pathlib import Path
from typing import cast

import pytest

from rag_eval.adapters import DocumentUpload, TargetAdapter
from rag_eval.adapters.errors import TargetAdapterError
from rag_eval.config.models import CorpusConfig
from rag_eval.datasets import DatasetValidationError, NativeBenchmarkDataset
from rag_eval.db.models import CorpusRecord
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import (
    BenchmarkCase,
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
from rag_eval.services import BenchmarkRegistrationService, CorpusPreparationService


class RecordingRepository:
    """In-memory persistence substitute that records canonical registration calls."""

    def __init__(self) -> None:
        """Initialize deterministic recorded state."""
        self.targets: list[str] = []
        self.capabilities: list[str] = []
        self.corpora: list[object] = []
        self.documents: list[str] = []
        self.cases: list[str] = []

    async def persist_target(self, target_id: str, target: TargetInfo) -> None:
        """Record target persistence."""
        self.targets.append(target_id)

    async def persist_capabilities(
        self, target_id: str, capabilities: TargetCapabilities
    ) -> None:
        """Record capability persistence."""
        self.capabilities.append(target_id)

    async def persist_corpus(self, record: CorpusRecord) -> None:
        """Record corpus lifecycle state."""
        self.corpora.append(record)

    async def persist_document(self, corpus_id: str, document: Document) -> None:
        """Record document identity persistence."""
        self.documents.append(document.document_id)

    async def persist_benchmark_case(
        self, dataset_id: str, case: BenchmarkCase
    ) -> None:
        """Record benchmark truth persistence."""
        self.cases.append(case.case_id)


class IngestionTarget:
    """Deterministic target adapter substitute for corpus-service tests."""

    def __init__(self, *, documents: bool = True, chunks: bool = True) -> None:
        """Configure supported ingestion capabilities."""
        self._capabilities = TargetCapabilities(
            target=TargetInfo(
                target_id="target-1",
                name="ingestion-target",
            ),
            query=True,
            document_ingestion=documents,
            chunk_ingestion=chunks,
        )
        self.uploaded_documents: list[str] = []
        self.uploaded_chunks: list[list[Chunk]] = []
        self.operation_states: list[OperationStatus] = [OperationStatus.SUCCEEDED]

    async def capabilities(self) -> TargetCapabilities:
        """Return configured target capabilities."""
        return self._capabilities

    async def create_corpus(
        self, request: CreateCorpusRequest
    ) -> CreateCorpusResponse:
        """Return a new corpus identity."""
        return CreateCorpusResponse(corpus_id="target-corpus", status="EMPTY")

    async def upload_document(
        self, corpus_id: str, document: DocumentUpload
    ) -> Operation:
        """Record an uploaded document and return an asynchronous operation."""
        self.uploaded_documents.append(document.document.document_id)
        return Operation(
            operation_id=f"document-{len(self.uploaded_documents)}",
            kind="DOCUMENT_INGESTION",
            status=self.operation_states.pop(0),
        )

    async def upload_chunks(
        self, corpus_id: str, chunks: AsyncIterator[Chunk]
    ) -> Operation:
        """Consume only the target-facing chunk iterator."""
        self.uploaded_chunks.append([chunk async for chunk in chunks])
        return Operation(
            operation_id="chunks-1",
            kind="CHUNK_INGESTION",
            status=self.operation_states.pop(0),
        )

    async def get_operation(self, operation_id: str) -> Operation:
        """Return the next deterministic operation state."""
        return Operation(
            operation_id=operation_id,
            kind="INGESTION",
            status=self.operation_states.pop(0),
        )


def _write_dataset(
    tmp_path: Path, *, cases: str | None = None
) -> NativeBenchmarkDataset:
    """Create a native benchmark with one document and configurable JSONL cases."""
    document = tmp_path / "source.txt"
    document.write_text("source content", encoding="utf-8")
    digest = hashlib.sha256(document.read_bytes()).hexdigest()
    case_file = tmp_path / "cases.jsonl"
    case_file.write_text(
        cases or '{"case_id":"case-1","query":"Question"}\n', encoding="utf-8"
    )
    manifest = tmp_path / "manifest.yaml"
    manifest.write_text(
        "\n".join(
            [
                "benchmark_id: benchmark-1",
                "name: fixture",
                "version: '1'",
                "case_count: 1",
                "documents:",
                "  - document_id: document-1",
                "    filename: source.txt",
                "    path: source.txt",
                f"    sha256: {digest}",
                "chunks:",
                "  - chunk_id: chunk-1",
                "    document_id: document-1",
                "    text: source content",
                "cases: cases.jsonl",
            ]
        ),
        encoding="utf-8",
    )
    return NativeBenchmarkDataset(manifest)


def _corpus_service(
    target: IngestionTarget, repository: RecordingRepository
) -> CorpusPreparationService:
    """Adapt the focused fakes to the production service boundary."""
    return CorpusPreparationService(
        cast(TargetAdapter, target),
        cast(PersistenceRepository, repository),
    )


def test_native_dataset_streams_jsonl_and_validates_manifest(tmp_path: Path) -> None:
    """Native records become canonical models while JSONL cases remain iterable."""
    dataset = _write_dataset(tmp_path)
    dataset.validate()

    assert [case.case_id for case in dataset.iter_cases()] == ["case-1"]
    assert [chunk.chunk_id for chunk in dataset.iter_chunks()] == ["chunk-1"]
    assert dataset.manifest_sha256


@pytest.mark.parametrize(
    "cases, message",
    [
        (
            '{"case_id":"case-1","query":"Q"}\n{"case_id":"case-1","query":"Q"}\n',
            "duplicate case_id",
        ),
        (
            '{"case_id":"case-1","query":"Q","gold_evidence":[{"evidence_id":"e","document_id":"missing"}]}\n',
            "unknown document",
        ),
        ("not-json\n", "invalid JSONL"),
    ],
)
def test_dataset_validation_rejects_invalid_lazy_records(
    tmp_path: Path, cases: str, message: str
) -> None:
    """Duplicate identities, bad references, and bad JSONL fail before ingestion."""
    dataset = _write_dataset(tmp_path, cases=cases)
    with pytest.raises(DatasetValidationError, match=message):
        dataset.validate()


def test_dataset_validation_rejects_document_hash_mismatch(tmp_path: Path) -> None:
    """A declared document digest is verified against the exact local bytes."""
    dataset = _write_dataset(tmp_path)
    dataset._payload["documents"][0]["sha256"] = "0" * 64
    with pytest.raises(DatasetValidationError, match="SHA-256 mismatch"):
        dataset.validate()


def test_dataset_validation_rejects_duplicate_document_ids(tmp_path: Path) -> None:
    """Document identities are unique before corpus preparation begins."""
    dataset = _write_dataset(tmp_path)
    dataset._payload["documents"].append(dict(dataset._payload["documents"][0]))
    with pytest.raises(DatasetValidationError, match="duplicate document_id"):
        dataset.validate()


@pytest.mark.anyio
async def test_documents_chunks_external_and_case_registration(tmp_path: Path) -> None:
    """All corpus modes persist canonical state without running target queries."""
    dataset = _write_dataset(tmp_path)
    repository = RecordingRepository()
    registered = await BenchmarkRegistrationService(
        cast(PersistenceRepository, repository)
    ).register(dataset)
    target = IngestionTarget()
    documents = await _corpus_service(target, repository).prepare(
        dataset, CorpusConfig(mode=CorpusMode.DOCUMENTS)
    )

    assert registered == 1
    assert repository.cases == ["case-1"]
    assert documents.status == "READY"
    assert target.uploaded_documents == ["document-1"]

    chunk_target = IngestionTarget()
    chunks = await _corpus_service(chunk_target, repository).prepare(
        dataset, CorpusConfig(mode=CorpusMode.CHUNKS)
    )
    external = await _corpus_service(chunk_target, repository).prepare(
        dataset, CorpusConfig(mode=CorpusMode.EXTERNAL, corpus_id="external-1")
    )
    assert chunks.status == "READY"
    assert [chunk.chunk_id for chunk in chunk_target.uploaded_chunks[0]] == ["chunk-1"]
    assert external.corpus_id == "external-1"


@pytest.mark.anyio
async def test_unsupported_and_asynchronous_ingestion_failures_are_normalized(
    tmp_path: Path,
) -> None:
    """Capability gaps and terminal operation failures never become fake success."""
    dataset = _write_dataset(tmp_path)
    repository = RecordingRepository()
    with pytest.raises(TargetAdapterError) as unsupported:
        await _corpus_service(IngestionTarget(documents=False), repository).prepare(
            dataset, CorpusConfig(mode=CorpusMode.DOCUMENTS)
        )
    assert unsupported.value.to_error_record().category == "UNSUPPORTED_CAPABILITY"

    failed = IngestionTarget()
    failed.operation_states = [OperationStatus.PENDING, OperationStatus.FAILED]
    with pytest.raises(TargetAdapterError, match="ended as"):
        await CorpusPreparationService(
            cast(TargetAdapter, failed),
            cast(PersistenceRepository, repository),
            poll_interval_seconds=0,
        ).prepare(dataset, CorpusConfig(mode=CorpusMode.DOCUMENTS))


@pytest.mark.anyio
async def test_operation_poll_timeout_does_not_mark_ingestion_ready(
    tmp_path: Path,
) -> None:
    """Bounded polling reports timeout instead of fabricating a ready corpus."""
    dataset = _write_dataset(tmp_path)
    repository = RecordingRepository()
    pending = IngestionTarget()
    pending.operation_states = [OperationStatus.PENDING]
    with pytest.raises(TimeoutError, match="timed out"):
        await CorpusPreparationService(
            cast(TargetAdapter, pending),
            cast(PersistenceRepository, repository),
            poll_interval_seconds=0,
            poll_timeout_seconds=0,
        ).prepare(dataset, CorpusConfig(mode=CorpusMode.DOCUMENTS))
