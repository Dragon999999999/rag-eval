"""Creation and management of canonical benchmarks."""

import json
from collections.abc import Sequence
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from rag_eval.artifacts import ArtifactService
from rag_eval.db.benchmark_models import BenchmarkRecord
from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.models import (
    ArtifactType,
    Benchmark,
    BenchmarkCase,
    BenchmarkManifest,
    Chunk,
    CorpusMode,
    Document,
)


class BenchmarkService:
    """Create and manage canonical evaluator-owned benchmarks.

    Cases and chunks are normalized database resources after import.

    Documents remain atomic artifact-backed resources.

    Corpus representation changes are orchestrated here rather than in the
    persistence repository.
    """

    def __init__(
        self,
        repository: BenchmarkRepository,
        artifact_service: ArtifactService | None = None,
    ) -> None:
        """Bind benchmark persistence and optional artifact access."""
        self._repository = repository
        self._artifact_service = artifact_service

    # ------------------------------------------------------------------
    # Benchmarks
    # ------------------------------------------------------------------

    async def create(
        self,
        *,
        name: str,
        corpus_mode: CorpusMode = CorpusMode.DOCUMENTS,
        version: str = "1",
    ) -> Benchmark:
        """Create an empty benchmark."""
        manifest = BenchmarkManifest(
            benchmark_id=f"benchmark-{uuid4()}",
            name=name,
            version=version,
            corpus_mode=corpus_mode,
        )

        await self._repository.create_benchmark(manifest)

        return Benchmark(manifest=manifest)

    async def list_benchmarks(
        self,
    ) -> Sequence[BenchmarkRecord]:
        """List all benchmark identities."""
        return await self._repository.list_benchmarks()

    async def get(
        self,
        benchmark_id: str,
    ) -> Benchmark:
        """Load one complete benchmark aggregate."""
        benchmark = await self._repository.get_benchmark(
            benchmark_id
        )

        if benchmark is None:
            raise KeyError(
                f"benchmark not found: {benchmark_id}"
            )

        return benchmark

    async def get_manifest(
        self,
        benchmark_id: str,
    ) -> BenchmarkManifest:
        """Load benchmark metadata without loading its contents."""
        manifest = (
            await self._repository.get_benchmark_manifest(
                benchmark_id
            )
        )

        if manifest is None:
            raise KeyError(
                f"benchmark not found: {benchmark_id}"
            )

        return manifest

    async def delete(
        self,
        benchmark_id: str,
    ) -> None:
        """Delete a benchmark.

        Artifact byte cleanup is intentionally handled separately.
        """
        deleted = await self._repository.delete_benchmark(
            benchmark_id
        )

        if not deleted:
            raise KeyError(
                f"benchmark not found: {benchmark_id}"
            )

    # ------------------------------------------------------------------
    # Cases
    # ------------------------------------------------------------------

    async def create_case(
        self,
        benchmark_id: str,
        case: BenchmarkCase,
    ) -> BenchmarkCase:
        """Create one benchmark case."""
        await self.get_manifest(benchmark_id)

        await self._repository.create_case(
            benchmark_id,
            case,
        )

        return case

    async def add_cases(
        self,
        benchmark_id: str,
        cases: Sequence[BenchmarkCase],
    ) -> int:
        """Create multiple benchmark cases."""
        await self.get_manifest(benchmark_id)

        for case in cases:
            await self._repository.create_case(
                benchmark_id,
                case,
            )

        return len(cases)

    async def get_case(
        self,
        benchmark_id: str,
        case_id: str,
    ) -> BenchmarkCase:
        """Load one benchmark case."""
        case = await self._repository.get_case(
            benchmark_id,
            case_id,
        )

        if case is None:
            raise KeyError(
                f"case {case_id} not found in "
                f"benchmark {benchmark_id}"
            )

        return case

    async def list_cases(
        self,
        benchmark_id: str,
    ) -> Sequence[BenchmarkCase]:
        """Load only the cases of a benchmark."""
        await self.get_manifest(benchmark_id)

        return await self._repository.list_cases(
            benchmark_id
        )

    async def delete_case(
        self,
        benchmark_id: str,
        case_id: str,
    ) -> None:
        """Delete one benchmark case."""
        deleted = await self._repository.delete_case(
            benchmark_id,
            case_id,
        )

        if not deleted:
            raise KeyError(
                f"case {case_id} not found in "
                f"benchmark {benchmark_id}"
            )

    # ------------------------------------------------------------------
    # Documents
    # ------------------------------------------------------------------

    async def create_document(
        self,
        benchmark_id: str,
        document: Document,
    ) -> Document:
        """Create one atomic benchmark document."""
        manifest = await self.get_manifest(
            benchmark_id
        )

        if manifest.corpus_mode is not CorpusMode.DOCUMENTS:
            raise ValueError(
                f"benchmark {benchmark_id} uses "
                f"{manifest.corpus_mode.value} corpus mode; "
                "documents may only be added in DOCUMENTS mode"
            )

        await self._repository.create_document(
            benchmark_id,
            document,
        )

        return document

    async def add_document(
        self,
        benchmark_id: str,
        document: Document,
    ) -> Document:
        """Backward-compatible alias for create_document()."""
        return await self.create_document(
            benchmark_id,
            document,
        )

    async def add_documents(
        self,
        benchmark_id: str,
        documents: Sequence[Document],
    ) -> int:
        """Create multiple atomic documents."""
        manifest = await self.get_manifest(
            benchmark_id
        )

        if manifest.corpus_mode is not CorpusMode.DOCUMENTS:
            raise ValueError(
                f"benchmark {benchmark_id} uses "
                f"{manifest.corpus_mode.value} corpus mode; "
                "documents may only be added in DOCUMENTS mode"
            )

        for document in documents:
            await self._repository.create_document(
                benchmark_id,
                document,
            )

        return len(documents)

    async def get_document(
        self,
        benchmark_id: str,
        document_id: str,
    ) -> Document:
        """Load one atomic benchmark document."""
        document = await self._repository.get_document(
            benchmark_id,
            document_id,
        )

        if document is None:
            raise KeyError(
                f"document {document_id} not found in "
                f"benchmark {benchmark_id}"
            )

        return document

    async def list_documents(
        self,
        benchmark_id: str,
    ) -> Sequence[Document]:
        """Load only the documents of a benchmark."""
        await self.get_manifest(benchmark_id)

        return await self._repository.list_documents(
            benchmark_id
        )

    async def delete_document(
        self,
        benchmark_id: str,
        document_id: str,
    ) -> None:
        """Delete one benchmark document.

        The immutable artifact bytes are not removed here.
        """
        deleted = await self._repository.delete_document(
            benchmark_id,
            document_id,
        )

        if not deleted:
            raise KeyError(
                f"document {document_id} not found in "
                f"benchmark {benchmark_id}"
            )

    # ------------------------------------------------------------------
    # Chunks
    # ------------------------------------------------------------------

    async def create_chunk(
        self,
        benchmark_id: str,
        chunk: Chunk,
    ) -> Chunk:
        """Create one canonical benchmark chunk."""
        manifest = await self.get_manifest(
            benchmark_id
        )

        if manifest.corpus_mode is not CorpusMode.CHUNKS:
            raise ValueError(
                f"benchmark {benchmark_id} uses "
                f"{manifest.corpus_mode.value} corpus mode; "
                "chunks may only be added in CHUNKS mode"
            )

        await self._repository.create_chunk(
            benchmark_id,
            chunk,
        )

        return chunk

    async def add_chunks(
        self,
        benchmark_id: str,
        chunks: Sequence[Chunk],
    ) -> int:
        """Create multiple canonical benchmark chunks."""
        manifest = await self.get_manifest(
            benchmark_id
        )

        if manifest.corpus_mode is not CorpusMode.CHUNKS:
            raise ValueError(
                f"benchmark {benchmark_id} uses "
                f"{manifest.corpus_mode.value} corpus mode; "
                "chunks may only be added in CHUNKS mode"
            )

        for chunk in chunks:
            await self._repository.create_chunk(
                benchmark_id,
                chunk,
            )

        return len(chunks)

    async def get_chunk(
        self,
        benchmark_id: str,
        chunk_id: str,
    ) -> Chunk:
        """Load one benchmark chunk."""
        chunk = await self._repository.get_chunk(
            benchmark_id,
            chunk_id,
        )

        if chunk is None:
            raise KeyError(
                f"chunk {chunk_id} not found in "
                f"benchmark {benchmark_id}"
            )

        return chunk

    async def list_chunks(
        self,
        benchmark_id: str,
    ) -> Sequence[Chunk]:
        """Load only the chunks of a benchmark."""
        await self.get_manifest(benchmark_id)

        return await self._repository.list_chunks(
            benchmark_id
        )

    async def delete_chunk(
        self,
        benchmark_id: str,
        chunk_id: str,
    ) -> None:
        """Delete one canonical benchmark chunk."""
        deleted = await self._repository.delete_chunk(
            benchmark_id,
            chunk_id,
        )

        if not deleted:
            raise KeyError(
                f"chunk {chunk_id} not found in "
                f"benchmark {benchmark_id}"
            )

    # ------------------------------------------------------------------
    # Corpus mode transitions
    # ------------------------------------------------------------------

    async def set_corpus_mode(
        self,
        benchmark_id: str,
        mode: CorpusMode,
    ) -> Benchmark:
        """Change the persisted corpus representation.

        Empty benchmarks can switch freely between DOCUMENTS and CHUNKS.

        CHUNKS -> DOCUMENTS:
            Serialize all chunks into one JSON document, persist the document,
            delete the normalized chunks, then switch mode.

        DOCUMENTS -> CHUNKS:
            Every document must contain valid canonical Chunk JSON or JSONL.
            All documents are validated first. If any document cannot be
            converted, no database representation change is performed.

        EXTERNAL transitions are deliberately not handled here.
        """
        manifest = await self.get_manifest(
            benchmark_id
        )

        current = manifest.corpus_mode

        if current is mode:
            return await self.get(benchmark_id)

        if (
            current is CorpusMode.EXTERNAL
            or mode is CorpusMode.EXTERNAL
        ):
            raise ValueError(
                "automatic corpus conversion involving "
                "EXTERNAL mode is not supported"
            )

        if (
            current is CorpusMode.CHUNKS
            and mode is CorpusMode.DOCUMENTS
        ):
            await self._chunks_to_documents(
                benchmark_id
            )

        elif (
            current is CorpusMode.DOCUMENTS
            and mode is CorpusMode.CHUNKS
        ):
            await self._documents_to_chunks(
                benchmark_id
            )

        else:
            raise ValueError(
                f"unsupported corpus mode transition: "
                f"{current.value} -> {mode.value}"
            )

        return await self.get(benchmark_id)

    async def _chunks_to_documents(
        self,
        benchmark_id: str,
    ) -> None:
        """Convert normalized chunks into one atomic JSON document."""
        chunks = list(
            await self._repository.list_chunks(
                benchmark_id
            )
        )

        if not chunks:
            await self._repository.set_corpus_mode(
                benchmark_id,
                CorpusMode.DOCUMENTS,
            )
            return

        artifact_service = self._require_artifact_service()

        payload = json.dumps(
            [
                chunk.model_dump(mode="json")
                for chunk in chunks
            ],
            ensure_ascii=False,
            indent=2,
        ).encode("utf-8")

        artifact = await artifact_service.put(
            payload,
            ArtifactType.SOURCE_DOCUMENT,
            content_type="application/json",
            metadata={
                "benchmark_id": benchmark_id,
                "generated_from": "chunks",
                "chunk_count": len(chunks),
            },
        )

        document = Document(
            document_id=f"document-{uuid4()}",
            filename="benchmark-chunks.json",
            mime_type="application/json",
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            artifact=artifact,
            metadata={
                "generated_from": "chunks",
                "chunk_count": len(chunks),
            },
        )

        # Create the replacement representation first.
        await self._repository.create_document(
            benchmark_id,
            document,
        )

        # Only remove chunks after the replacement document exists.
        for chunk in chunks:
            await self._repository.delete_chunk(
                benchmark_id,
                chunk.chunk_id,
            )

        await self._repository.set_corpus_mode(
            benchmark_id,
            CorpusMode.DOCUMENTS,
        )

    async def _documents_to_chunks(
        self,
        benchmark_id: str,
    ) -> None:
        """Convert chunk-formatted documents into normalized DB chunks.

        Every document is read and validated before any persistent benchmark
        content is changed.
        """
        documents = list(
            await self._repository.list_documents(
                benchmark_id
            )
        )

        if not documents:
            await self._repository.set_corpus_mode(
                benchmark_id,
                CorpusMode.CHUNKS,
            )
            return

        artifact_service = self._require_artifact_service()

        converted: list[Chunk] = []

        # Phase 1: read and validate everything without mutating benchmark
        # representation.
        for document in documents:
            if document.artifact is None:
                raise ValueError(
                    f"document {document.document_id} has "
                    "no artifact and cannot be converted to chunks"
                )

            content = await artifact_service.get(
                document.artifact
            )

            document_chunks = self._parse_chunks(
                content,
                filename=document.filename,
                document_id=document.document_id,
            )

            converted.extend(document_chunks)

        self._validate_unique_chunk_ids(
            converted
        )

        # Phase 2: persist the replacement representation.
        for chunk in converted:
            await self._repository.create_chunk(
                benchmark_id,
                chunk,
            )

        # Only remove documents after every chunk has been accepted.
        for document in documents:
            await self._repository.delete_document(
                benchmark_id,
                document.document_id,
            )

        await self._repository.set_corpus_mode(
            benchmark_id,
            CorpusMode.CHUNKS,
        )

    # ------------------------------------------------------------------
    # Complete benchmark import
    # ------------------------------------------------------------------

    async def register(
        self,
        benchmark: Benchmark,
    ) -> int:
        """Persist a complete canonical benchmark import."""
        benchmark_id = benchmark.manifest.benchmark_id

        await self._repository.create_benchmark(
            benchmark.manifest
        )

        for case in benchmark.cases:
            await self._repository.create_case(
                benchmark_id,
                case,
            )

        if (
            benchmark.manifest.corpus_mode
            is CorpusMode.DOCUMENTS
        ):
            for document in benchmark.documents:
                await self._repository.create_document(
                    benchmark_id,
                    document,
                )

        elif (
            benchmark.manifest.corpus_mode
            is CorpusMode.CHUNKS
        ):
            for chunk in benchmark.chunks:
                await self._repository.create_chunk(
                    benchmark_id,
                    chunk,
                )

        return benchmark.case_count

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _require_artifact_service(
        self,
    ) -> ArtifactService:
        if self._artifact_service is None:
            raise RuntimeError(
                "ArtifactService is required for corpus "
                "representation conversion"
            )

        return self._artifact_service

    @staticmethod
    def _parse_chunks(
        data: bytes,
        *,
        filename: str | None,
        document_id: str,
    ) -> list[Chunk]:
        """Parse one document as canonical Chunk JSON or JSONL.

        No generic PDF/text chunking happens here. The document must already
        contain records matching the canonical Chunk schema.
        """
        try:
            text = data.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"document {document_id} is not UTF-8 and "
                "cannot be converted to canonical chunks"
            ) from exc

        suffix = (
            Path(filename).suffix.lower()
            if filename
            else ""
        )

        if suffix == ".jsonl":
            return BenchmarkService._parse_chunk_jsonl(
                text,
                document_id=document_id,
            )

        try:
            payload = json.loads(text)
        except json.JSONDecodeError:
            # Permit extensionless/text JSONL documents as long as every
            # non-empty line is a valid canonical chunk.
            return BenchmarkService._parse_chunk_jsonl(
                text,
                document_id=document_id,
            )

        if not isinstance(payload, list):
            raise ValueError(
                f"document {document_id} must contain a JSON "
                "array of canonical chunks"
            )

        chunks: list[Chunk] = []

        for index, raw in enumerate(
            payload,
            start=1,
        ):
            try:
                chunks.append(
                    Chunk.model_validate(raw)
                )
            except ValidationError as exc:
                raise ValueError(
                    f"document {document_id} contains an "
                    f"invalid chunk at array index {index - 1}: "
                    f"{exc}"
                ) from exc

        return chunks

    @staticmethod
    def _parse_chunk_jsonl(
        text: str,
        *,
        document_id: str,
    ) -> list[Chunk]:
        chunks: list[Chunk] = []

        for line_number, line in enumerate(
            text.splitlines(),
            start=1,
        ):
            if not line.strip():
                continue

            try:
                raw = json.loads(line)
                chunks.append(
                    Chunk.model_validate(raw)
                )
            except (
                json.JSONDecodeError,
                ValidationError,
            ) as exc:
                raise ValueError(
                    f"document {document_id} contains "
                    f"invalid chunk JSONL at line "
                    f"{line_number}: {exc}"
                ) from exc

        if not chunks:
            raise ValueError(
                f"document {document_id} contains no chunks"
            )

        return chunks

    @staticmethod
    def _validate_unique_chunk_ids(
        chunks: Sequence[Chunk],
    ) -> None:
        seen: set[str] = set()

        for chunk in chunks:
            if chunk.chunk_id in seen:
                raise ValueError(
                    f"duplicate chunk_id during conversion: "
                    f"{chunk.chunk_id}"
                )

            seen.add(chunk.chunk_id)