"""Preparation of canonical benchmark corpora through the TargetAdapter boundary."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from rag_eval.adapters import DocumentUpload, TargetAdapter
from rag_eval.adapters.errors import TargetAdapterError
from rag_eval.artifacts import ArtifactService
from rag_eval.config.models import CorpusConfig
from rag_eval.datasets import BenchmarkDataset
from rag_eval.db.models import CorpusRecord
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import (
    CorpusMode,
    CreateCorpusRequest,
    Document,
    ErrorCategory,
    Operation,
    OperationStatus,
)


@dataclass(frozen=True, slots=True)
class PreparedCorpus:
    """Durable outcome of one corpus preparation operation."""

    corpus_id: str
    status: str
    mode: CorpusMode
    content_hash: str


class CorpusPreparationService:
    """Create, ingest, poll, and persist benchmark corpora through TargetAdapter.

    This service owns bounded ingestion polling. It never executes target
    queries, generates chunks, or branches on the adapter's transport.
    """

    def __init__(
        self,
        adapter: TargetAdapter,
        repository: PersistenceRepository,
        *,
        artifact_service: ArtifactService | None = None,
        poll_interval_seconds: float = 0.1,
        poll_timeout_seconds: float = 120.0,
    ) -> None:
        """Bind target, persistence, and optional existing artifact access."""
        self._adapter = adapter
        self._repository = repository
        self._artifact_service = artifact_service
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_timeout_seconds = poll_timeout_seconds

    async def prepare(
        self, dataset: BenchmarkDataset, corpus_config: CorpusConfig
    ) -> PreparedCorpus:
        """Validate and prepare one DOCUMENTS, CHUNKS, or EXTERNAL corpus."""
        dataset.validate()
        manifest = dataset.load_manifest()
        capabilities = await self._adapter.capabilities()
        target_id = self._target_id(capabilities.target)
        await self._repository.persist_target(target_id, capabilities.target)
        await self._repository.persist_capabilities(target_id, capabilities)
        content_hash = self._content_hash(dataset, corpus_config)

        if corpus_config.mode is CorpusMode.EXTERNAL:
            if corpus_config.corpus_id is None:
                raise ValueError(
                    "EXTERNAL corpus mode requires target.corpus.corpus_id"
                )
            await self._persist_corpus(
                corpus_config.corpus_id,
                target_id,
                corpus_config.mode,
                "READY",
                content_hash,
                {"external": True, "manifest_id": manifest.benchmark_id},
            )
            return PreparedCorpus(
                corpus_config.corpus_id, "READY", corpus_config.mode, content_hash
            )

        if (
            corpus_config.mode is CorpusMode.DOCUMENTS
            and not capabilities.document_ingestion
        ):
            raise TargetAdapterError(
                "Target does not advertise document ingestion.",
                category=ErrorCategory.UNSUPPORTED_CAPABILITY,
                code="UNSUPPORTED_CAPABILITY",
                stage="corpus_prepare",
            )
        if corpus_config.mode is CorpusMode.CHUNKS and not capabilities.chunk_ingestion:
            raise TargetAdapterError(
                "Target does not advertise chunk ingestion.",
                category=ErrorCategory.UNSUPPORTED_CAPABILITY,
                code="UNSUPPORTED_CAPABILITY",
                stage="corpus_prepare",
            )

        created = await self._adapter.create_corpus(
            CreateCorpusRequest(
                request_id=str(uuid4()),
                name=manifest.name,
                mode=corpus_config.mode,
                parameters=corpus_config.parameters,
                metadata={
                    "benchmark_id": manifest.benchmark_id,
                    "manifest_sha256": getattr(dataset, "manifest_sha256", None),
                },
            )
        )
        await self._persist_corpus(
            created.corpus_id,
            target_id,
            corpus_config.mode,
            created.status,
            content_hash,
            {
                "manifest_id": manifest.benchmark_id,
                "requested_configuration": corpus_config.parameters,
                "effective_configuration": created.configuration.effective
                if created.configuration
                else {},
            },
        )
        try:
            if corpus_config.mode is CorpusMode.DOCUMENTS:
                for document in dataset.iter_documents():
                    await self._repository.persist_document(created.corpus_id, document)
                    content = await self._document_content(dataset, document)
                    operation = await self._adapter.upload_document(
                        created.corpus_id, DocumentUpload(document, content)
                    )
                    await self._await_operation(operation)
            else:
                document_count = 0
                for document in dataset.iter_documents():
                    await self._repository.persist_document(created.corpus_id, document)
                    document_count += 1

                async def chunks():
                    for chunk in dataset.iter_chunks():
                        yield chunk

                operation = await self._adapter.upload_chunks(
                    created.corpus_id, chunks()
                )
                await self._await_operation(operation)
                await self._persist_corpus(
                    created.corpus_id,
                    target_id,
                    corpus_config.mode,
                    "BUILDING",
                    content_hash,
                    {
                        "manifest_id": manifest.benchmark_id,
                        "document_count": document_count,
                    },
                )
        except Exception:
            await self._persist_corpus(
                created.corpus_id,
                target_id,
                corpus_config.mode,
                "FAILED",
                content_hash,
                {"manifest_id": manifest.benchmark_id},
            )
            raise
        await self._persist_corpus(
            created.corpus_id,
            target_id,
            corpus_config.mode,
            "READY",
            content_hash,
            {"manifest_id": manifest.benchmark_id},
        )
        return PreparedCorpus(
            created.corpus_id, "READY", corpus_config.mode, content_hash
        )

    async def _document_content(
        self, dataset: BenchmarkDataset, document: Document
    ) -> object:
        """Resolve supported local or durable-artifact document bytes for upload."""
        path = dataset.source_path(document)
        if path is not None:
            return path
        artifact = document.artifact
        if artifact is not None and self._artifact_service is not None:
            return await self._artifact_service.get(artifact)
        raise ValueError(f"document {document.document_id} has no readable source")

    async def _await_operation(self, operation: Operation) -> Operation:
        """Poll one ingestion operation until terminal success, failure, or timeout."""
        current = operation
        deadline = monotonic() + self._poll_timeout_seconds
        while current.status in {OperationStatus.PENDING, OperationStatus.RUNNING}:
            if monotonic() >= deadline:
                raise TimeoutError(
                    f"ingestion operation timed out: {current.operation_id}"
                )
            await asyncio.sleep(self._poll_interval_seconds)
            current = await self._adapter.get_operation(current.operation_id)
        if current.status is not OperationStatus.SUCCEEDED:
            if current.error is not None:
                error = TargetAdapterError(
                    current.error.message,
                    category=current.error.category,
                    code=current.error.code,
                    stage=current.error.stage or "ingestion",
                )
                error.record = current.error
                raise error
            raise TargetAdapterError(
                f"ingestion operation {current.operation_id} ended as {current.status}",
                category=ErrorCategory.INGESTION,
                code="INGESTION_OPERATION_FAILED",
                stage="ingestion",
            )
        return current

    async def _persist_corpus(
        self,
        corpus_id: str,
        target_id: str,
        mode: CorpusMode,
        status: str,
        content_hash: str,
        metadata: dict[str, object],
    ) -> None:
        """Persist one corpus lifecycle transition through the Stage 4 repository."""
        await self._repository.persist_corpus(
            CorpusRecord(
                corpus_id=corpus_id,
                target_id=target_id,
                mode=mode.value,
                status=status,
                content_hash=content_hash,
                metadata_json=metadata,
            )
        )

    @staticmethod
    def _content_hash(dataset: BenchmarkDataset, config: CorpusConfig) -> str:
        """Build deterministic corpus identity from canonical input metadata only."""
        digest = hashlib.sha256()
        values = (
            dataset.load_manifest().model_dump(mode="json"),
            {"mode": config.mode.value, "parameters": config.parameters},
        )
        for value in values:
            digest.update(
                json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
            )
        for document in dataset.iter_documents():
            digest.update(document.model_dump_json().encode())
        if config.mode is CorpusMode.CHUNKS:
            for chunk in dataset.iter_chunks():
                digest.update(chunk.model_dump_json().encode())
        return digest.hexdigest()

    @staticmethod
    def _target_id(target: object) -> str:
        """Derive a stable persistence key when a target omits explicit identity."""
        target_id = getattr(target, "target_id", None)
        if target_id is not None:
            return target_id
        return ":".join(
            str(value or "unknown")
            for value in (
                getattr(target, "name", None),
                getattr(target, "version", None),
                getattr(target, "implementation", None),
            )
        )
