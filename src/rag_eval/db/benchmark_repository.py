"""Persistence repository for canonical benchmark resources."""

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.models import (
    ArtifactRecord,
    BenchmarkCaseRecord,
    BenchmarkChunkRecord,
    BenchmarkDocumentRecord,
    BenchmarkRecord,
)
from rag_eval.models import (
    ArtifactRef,
    Benchmark,
    BenchmarkCase,
    BenchmarkManifest,
    Chunk,
    CorpusMode,
    Document,
)


class BenchmarkRepository:
    """Persistence operations for benchmarks and their owned resources."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind repository to one caller-managed transaction/session."""
        self._session = session

    # ------------------------------------------------------------------
    # Benchmark
    # ------------------------------------------------------------------

    async def create_benchmark(
        self,
        manifest: BenchmarkManifest,
    ) -> BenchmarkRecord:
        """Create one benchmark.

        Benchmark IDs are immutable and duplicate creation is rejected.
        """
        existing = await self._session.get(
            BenchmarkRecord,
            manifest.benchmark_id,
        )

        if existing is not None:
            raise ValueError(
                f"benchmark already exists: {manifest.benchmark_id}"
            )

        record = BenchmarkRecord(
            benchmark_id=manifest.benchmark_id,
            name=manifest.name,
            version=manifest.version,
            schema_version=manifest.schema_version,
            corpus_mode=manifest.corpus_mode.value,
            content_hash=manifest.content_hash,
            corpus_id=manifest.corpus_id,
            source=manifest.source,
            tags=manifest.tags,
            metadata_json=manifest.metadata,
        )

        if manifest.created_at is not None:
            record.created_at = manifest.created_at

        self._session.add(record)
        await self._session.flush()

        return record

    async def get_benchmark_manifest(
        self,
        benchmark_id: str,
    ) -> BenchmarkManifest | None:
        """Load benchmark identity and metadata without loading its contents."""
        record = await self._session.get(
            BenchmarkRecord,
            benchmark_id,
        )

        if record is None:
            return None

        return self._manifest_from_record(record)

    async def get_benchmark(
        self,
        benchmark_id: str,
    ) -> Benchmark | None:
        """Load the full benchmark aggregate."""
        manifest = await self.get_benchmark_manifest(
            benchmark_id
        )

        if manifest is None:
            return None

        cases = await self.list_cases(benchmark_id)
        documents = await self.list_documents(benchmark_id)
        chunks = await self.list_chunks(benchmark_id)

        return Benchmark(
            manifest=manifest,
            cases=list(cases),
            documents=list(documents),
            chunks=list(chunks),
        )

    async def list_benchmarks(
        self,
    ) -> Sequence[BenchmarkRecord]:
        """List benchmark identities without loading all contents."""
        result = await self._session.scalars(
            select(BenchmarkRecord).order_by(
                BenchmarkRecord.name,
                BenchmarkRecord.benchmark_id,
            )
        )

        return result.all()

    async def set_corpus_mode(
        self,
        benchmark_id: str,
        mode: CorpusMode,
    ) -> BenchmarkRecord:
        """Persist the benchmark's selected corpus representation.

        Conversion and validation must happen in BenchmarkService before this
        method is called.
        """
        record = await self._session.get(
            BenchmarkRecord,
            benchmark_id,
        )

        if record is None:
            raise KeyError(
                f"benchmark not found: {benchmark_id}"
            )

        record.corpus_mode = mode.value

        await self._session.flush()
        return record

    async def delete_benchmark(
        self,
        benchmark_id: str,
    ) -> bool:
        """Delete a benchmark and its DB-owned children.

        Artifact bytes are intentionally not deleted here.
        """
        record = await self._session.get(
            BenchmarkRecord,
            benchmark_id,
        )

        if record is None:
            return False

        await self._session.delete(record)
        await self._session.flush()

        return True

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    async def create_case(
        self,
        benchmark_id: str,
        case: BenchmarkCase,
    ) -> BenchmarkCaseRecord:
        """Create one case.

        Cases are database resources after import; the source JSON/JSONL file
        has no persistence meaning.
        """
        await self._require_benchmark(benchmark_id)

        existing = await self._session.get(
            BenchmarkCaseRecord,
            case.case_id,
        )

        if existing is not None:
            raise ValueError(
                f"benchmark case already exists: {case.case_id}"
            )

        record = BenchmarkCaseRecord(
            case_id=case.case_id,
            benchmark_id=benchmark_id,
            query=case.query,
            history=[
                message.model_dump(mode="json")
                for message in case.history
            ],
            reference_answer=case.reference_answer,
            gold_evidence=[
                evidence.model_dump(mode="json")
                for evidence in case.gold_evidence
            ],
            answerability=(
                case.answerability.value
                if case.answerability is not None
                else None
            ),
            tags=case.tags,
            metadata_json={
                **case.metadata,
                "difficulty": case.difficulty,
                "language": case.language,
            },
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def get_case(
        self,
        benchmark_id: str,
        case_id: str,
    ) -> BenchmarkCase | None:
        """Load one case belonging to a benchmark."""
        record = await self._session.get(
            BenchmarkCaseRecord,
            case_id,
        )

        if (
            record is None
            or record.benchmark_id != benchmark_id
        ):
            return None

        return self._case_from_record(record)

    async def list_cases(
        self,
        benchmark_id: str,
    ) -> Sequence[BenchmarkCase]:
        """Load only the cases belonging to a benchmark."""
        result = await self._session.scalars(
            select(BenchmarkCaseRecord)
            .where(
                BenchmarkCaseRecord.benchmark_id
                == benchmark_id
            )
            .order_by(BenchmarkCaseRecord.case_id)
        )

        return [
            self._case_from_record(record)
            for record in result.all()
        ]

    async def delete_case(
        self,
        benchmark_id: str,
        case_id: str,
    ) -> bool:
        """Delete one case."""
        record = await self._session.get(
            BenchmarkCaseRecord,
            case_id,
        )

        if (
            record is None
            or record.benchmark_id != benchmark_id
        ):
            return False

        await self._session.delete(record)
        await self._session.flush()

        return True

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def create_document(
        self,
        benchmark_id: str,
        document: Document,
    ) -> BenchmarkDocumentRecord:
        """Attach one atomic source document to a benchmark."""
        await self._require_benchmark(benchmark_id)

        existing = await self._session.get(
            BenchmarkDocumentRecord,
            document.document_id,
        )

        if existing is not None:
            raise ValueError(
                f"benchmark document already exists: "
                f"{document.document_id}"
            )

        record = BenchmarkDocumentRecord(
            document_id=document.document_id,
            benchmark_id=benchmark_id,
            filename=document.filename,
            mime_type=document.mime_type,
            sha256=document.sha256,
            size_bytes=document.size_bytes,
            artifact_id=(
                document.artifact.artifact_id
                if document.artifact is not None
                else None
            ),
            metadata_json=document.metadata,
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def get_document(
        self,
        benchmark_id: str,
        document_id: str,
    ) -> Document | None:
        """Load one atomic benchmark document."""
        record = await self._session.get(
            BenchmarkDocumentRecord,
            document_id,
        )

        if (
            record is None
            or record.benchmark_id != benchmark_id
        ):
            return None

        return await self._document_from_record(record)

    async def list_documents(
        self,
        benchmark_id: str,
    ) -> Sequence[Document]:
        """Load only the documents belonging to a benchmark."""
        result = await self._session.scalars(
            select(BenchmarkDocumentRecord)
            .where(
                BenchmarkDocumentRecord.benchmark_id
                == benchmark_id
            )
            .order_by(
                BenchmarkDocumentRecord.document_id
            )
        )

        documents: list[Document] = []

        for record in result.all():
            documents.append(
                await self._document_from_record(record)
            )

        return documents

    async def delete_document(
        self,
        benchmark_id: str,
        document_id: str,
    ) -> bool:
        """Delete the benchmark-document relationship.

        This does not delete the underlying immutable artifact bytes.
        Artifact lifecycle remains owned by ArtifactService.
        """
        record = await self._session.get(
            BenchmarkDocumentRecord,
            document_id,
        )

        if (
            record is None
            or record.benchmark_id != benchmark_id
        ):
            return False

        await self._session.delete(record)
        await self._session.flush()

        return True

    # ------------------------------------------------------------------
    # Chunks
    # ------------------------------------------------------------------

    async def create_chunk(
        self,
        benchmark_id: str,
        chunk: Chunk,
    ) -> BenchmarkChunkRecord:
        """Create one canonical database-backed chunk.

        The uploaded JSON/JSONL source is not preserved as an atomic resource.
        """
        await self._require_benchmark(benchmark_id)

        existing = await self._session.get(
            BenchmarkChunkRecord,
            chunk.chunk_id,
        )

        if existing is not None:
            raise ValueError(
                f"benchmark chunk already exists: "
                f"{chunk.chunk_id}"
            )

        record = BenchmarkChunkRecord(
            chunk_id=chunk.chunk_id,
            benchmark_id=benchmark_id,
            document_id=chunk.document_id,
            text=chunk.text,
            location=(
                chunk.location.model_dump(mode="json")
                if chunk.location is not None
                else None
            ),
            metadata_json=chunk.metadata,
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def get_chunk(
        self,
        benchmark_id: str,
        chunk_id: str,
    ) -> Chunk | None:
        """Load one chunk belonging to a benchmark."""
        record = await self._session.get(
            BenchmarkChunkRecord,
            chunk_id,
        )

        if (
            record is None
            or record.benchmark_id != benchmark_id
        ):
            return None

        return self._chunk_from_record(record)

    async def list_chunks(
        self,
        benchmark_id: str,
    ) -> Sequence[Chunk]:
        """Load only the chunks belonging to a benchmark."""
        result = await self._session.scalars(
            select(BenchmarkChunkRecord)
            .where(
                BenchmarkChunkRecord.benchmark_id
                == benchmark_id
            )
            .order_by(BenchmarkChunkRecord.chunk_id)
        )

        return [
            self._chunk_from_record(record)
            for record in result.all()
        ]

    async def delete_chunk(
        self,
        benchmark_id: str,
        chunk_id: str,
    ) -> bool:
        """Delete one canonical chunk."""
        record = await self._session.get(
            BenchmarkChunkRecord,
            chunk_id,
        )

        if (
            record is None
            or record.benchmark_id != benchmark_id
        ):
            return False

        await self._session.delete(record)
        await self._session.flush()

        return True

    # ------------------------------------------------------------------
    # Internal conversion helpers
    # ------------------------------------------------------------------

    async def _require_benchmark(
        self,
        benchmark_id: str,
    ) -> BenchmarkRecord:
        record = await self._session.get(
            BenchmarkRecord,
            benchmark_id,
        )

        if record is None:
            raise KeyError(
                f"benchmark not found: {benchmark_id}"
            )

        return record

    @staticmethod
    def _manifest_from_record(
        record: BenchmarkRecord,
    ) -> BenchmarkManifest:
        return BenchmarkManifest(
            benchmark_id=record.benchmark_id,
            name=record.name,
            version=record.version,
            schema_version=record.schema_version,
            corpus_mode=CorpusMode(record.corpus_mode),
            content_hash=record.content_hash,
            corpus_id=record.corpus_id,
            created_at=record.created_at,
            source=record.source,
            tags=list(record.tags or []),
            metadata=dict(record.metadata_json or {}),
        )

    @staticmethod
    def _case_from_record(
        record: BenchmarkCaseRecord,
    ) -> BenchmarkCase:
        metadata = dict(record.metadata_json or {})

        difficulty = metadata.pop(
            "difficulty",
            None,
        )
        language = metadata.pop(
            "language",
            None,
        )

        return BenchmarkCase.model_validate(
            {
                "case_id": record.case_id,
                "query": record.query,
                "history": record.history or [],
                "reference_answer": record.reference_answer,
                "gold_evidence": record.gold_evidence or [],
                "answerability": record.answerability,
                "tags": record.tags or [],
                "difficulty": difficulty,
                "language": language,
                "metadata": metadata,
            }
        )

    async def _document_from_record(
        self,
        record: BenchmarkDocumentRecord,
    ) -> Document:
        artifact = None

        if record.artifact_id is not None:
            artifact_record = await self._session.get(
                ArtifactRecord,
                record.artifact_id,
            )

            if artifact_record is None:
                raise ValueError(
                    f"artifact {record.artifact_id} "
                    f"referenced by document "
                    f"{record.document_id} does not exist"
                )

            artifact = ArtifactRef(
                artifact_id=artifact_record.artifact_id,
                uri=artifact_record.uri,
                sha256=artifact_record.sha256,
                size_bytes=artifact_record.size_bytes,
                content_type=artifact_record.content_type,
                created_at=artifact_record.created_at,
                metadata=dict(
                    artifact_record.metadata_json or {}
                ),
            )

        return Document(
            document_id=record.document_id,
            filename=record.filename,
            mime_type=record.mime_type,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            artifact=artifact,
            metadata=dict(record.metadata_json or {}),
        )

    @staticmethod
    def _chunk_from_record(
        record: BenchmarkChunkRecord,
    ) -> Chunk:
        return Chunk.model_validate(
            {
                "chunk_id": record.chunk_id,
                "document_id": record.document_id,
                "text": record.text,
                "location": record.location,
                "metadata": dict(
                    record.metadata_json or {}
                ),
            }
        )