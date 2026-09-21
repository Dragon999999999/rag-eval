"""Preparation of canonical benchmark corpora through the TargetAdapter boundary."""

import asyncio
import hashlib
import json
from dataclasses import dataclass
from time import monotonic
from uuid import uuid4

from rag_eval.adapters import DocumentContent, DocumentUpload, TargetAdapter
from rag_eval.adapters.errors import TargetAdapterError
from rag_eval.artifacts import ArtifactService
from rag_eval.config.models import CorpusConfig
from rag_eval.db.models import CorpusRecord
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import (
    Benchmark,
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
    """Prepare one benchmark corpus through the TargetAdapter boundary.

    The benchmark owns the available source representation.
    The experiment/run selects one mode from benchmark.available_corpus_modes.

    This service never executes benchmark queries or generates chunks.
    """

    def __init__(
        self,
        target_id: str,
        adapter: TargetAdapter,
        repository: TargetRepository,
        *,
        artifact_service: ArtifactService | None = None,
        poll_interval_seconds: float = 0.1,
        poll_timeout_seconds: float = 120.0,
    ) -> None:
        """Bind one registered target, its adapter, and persistence."""

        self._target_id = target_id
        self._adapter = adapter
        self._repository = repository
        self._artifact_service = artifact_service
        self._poll_interval_seconds = poll_interval_seconds
        self._poll_timeout_seconds = poll_timeout_seconds

    async def prepare(
        self,
        benchmark: Benchmark,
        corpus_config: CorpusConfig,
    ) -> PreparedCorpus:
        """Prepare DOCUMENTS, CHUNKS, or EXTERNAL corpus for a benchmark."""
        manifest = benchmark.manifest

        if not benchmark.is_complete:
            raise ValueError(
                f"benchmark {manifest.benchmark_id} has no cases"
            )

        if corpus_config.mode not in benchmark.available_corpus_modes:
            available = ", ".join(
                sorted(mode.value for mode in benchmark.available_corpus_modes)
            )

            raise ValueError(
                f"corpus mode {corpus_config.mode.value} is not available "
                f"for benchmark {manifest.benchmark_id}; "
                f"available modes: {available or 'none'}"
            )

        capabilities = await self._adapter.capabilities()

        content_hash = self._content_hash(
            benchmark,
            corpus_config,
        )

        if corpus_config.mode is CorpusMode.EXTERNAL:
            if corpus_config.corpus_id is None:
                raise ValueError(
                    "EXTERNAL corpus mode requires a target corpus_id"
                )

            await self._persist_corpus(
                corpus_config.corpus_id,
                CorpusMode.EXTERNAL,
                "READY",
                content_hash,
                {
                    "external": True,
                    "benchmark_id": manifest.benchmark_id,
                },
            )

            return PreparedCorpus(
                corpus_id=corpus_config.corpus_id,
                status="READY",
                mode=CorpusMode.EXTERNAL,
                content_hash=content_hash,
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

        if (
            corpus_config.mode is CorpusMode.CHUNKS
            and not capabilities.chunk_ingestion
        ):
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
                    "benchmark_content_hash": manifest.content_hash,
                },
            )
        )

        await self._persist_corpus(
            created.corpus_id,
            corpus_config.mode,
            created.status,
            content_hash,
            {
                "benchmark_id": manifest.benchmark_id,
                "requested_configuration": corpus_config.parameters,
                "effective_configuration": (
                    created.configuration.effective
                    if created.configuration
                    else {}
                ),
            },
        )

        try:
            if corpus_config.mode is CorpusMode.DOCUMENTS:
                await self._prepare_documents(
                    benchmark,
                    created.corpus_id,
                )

            elif corpus_config.mode is CorpusMode.CHUNKS:
                await self._prepare_chunks(
                    benchmark,
                    created.corpus_id,
                )

        except Exception:
            await self._persist_corpus(
                created.corpus_id,
                corpus_config.mode,
                "FAILED",
                content_hash,
                {
                    "benchmark_id": manifest.benchmark_id,
                },
            )
            raise

        await self._persist_corpus(
            created.corpus_id,
            corpus_config.mode,
            "READY",
            content_hash,
            {
                "benchmark_id": manifest.benchmark_id,
            },
        )

        return PreparedCorpus(
            corpus_id=created.corpus_id,
            status="READY",
            mode=corpus_config.mode,
            content_hash=content_hash,
        )

    async def _prepare_documents(
        self,
        benchmark: Benchmark,
        corpus_id: str,
    ) -> None:
        """Upload all benchmark documents to the target corpus."""
        for document in benchmark.documents:
            await self._repository.persist_document(
                corpus_id,
                document,
            )

            content = await self._document_content(document)

            operation = await self._adapter.upload_document(
                corpus_id,
                DocumentUpload(
                    document,
                    content,
                ),
            )

            await self._await_operation(operation)

    async def _prepare_chunks(
        self,
        benchmark: Benchmark,
        corpus_id: str,
    ) -> None:
        """Upload all canonical benchmark chunks to the target corpus."""

        async def chunks():
            for chunk in benchmark.chunks:
                yield chunk

        operation = await self._adapter.upload_chunks(
            corpus_id,
            chunks(),
        )

        await self._await_operation(operation)

    async def _document_content(
        self,
        document: Document,
    ) -> DocumentContent:
        """Resolve stored document bytes for target upload."""
        if document.artifact is None:
            raise ValueError(
                f"document {document.document_id} has no stored artifact"
            )

        if self._artifact_service is None:
            raise ValueError(
                "ArtifactService is required for DOCUMENTS corpus preparation"
            )

        return await self._artifact_service.get(document.artifact)

    async def _await_operation(
        self,
        operation: Operation,
    ) -> Operation:
        """Poll one ingestion operation until terminal completion."""
        current = operation
        deadline = monotonic() + self._poll_timeout_seconds

        while current.status in {
            OperationStatus.PENDING,
            OperationStatus.RUNNING,
        }:
            if monotonic() >= deadline:
                raise TimeoutError(
                    f"ingestion operation timed out: "
                    f"{current.operation_id}"
                )

            await asyncio.sleep(self._poll_interval_seconds)

            current = await self._adapter.get_operation(
                current.operation_id
            )

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
                f"ingestion operation {current.operation_id} "
                f"ended as {current.status}",
                category=ErrorCategory.INGESTION,
                code="INGESTION_OPERATION_FAILED",
                stage="ingestion",
            )

        return current

    async def _persist_corpus(
        self,
        corpus_id: str,
        mode: CorpusMode,
        status: str,
        content_hash: str,
        metadata: dict[str, object],
    ) -> None:
        """Persist one target-corpus lifecycle state."""
        await self._repository.persist_corpus(
            CorpusRecord(
                corpus_id=corpus_id,
                target_id=self._target_id,
                mode=mode.value,
                status=status,
                content_hash=content_hash,
                metadata_json=metadata,
            )
        )

    @staticmethod
    def _content_hash(
        benchmark: Benchmark,
        config: CorpusConfig,
    ) -> str:
        """Build deterministic target-corpus identity."""
        digest = hashlib.sha256()

        configuration = {
            "benchmark_id": benchmark.manifest.benchmark_id,
            "mode": config.mode.value,
            "corpus_id": config.corpus_id,
            "parameters": config.parameters,
        }

        digest.update(
            json.dumps(
                configuration,
                sort_keys=True,
                separators=(",", ":"),
            ).encode()
        )

        if config.mode is CorpusMode.DOCUMENTS:
            for document in benchmark.documents:
                digest.update(
                    document.model_dump_json().encode()
                )

        elif config.mode is CorpusMode.CHUNKS:
            for chunk in benchmark.chunks:
                digest.update(
                    chunk.model_dump_json().encode()
                )

        return digest.hexdigest()
