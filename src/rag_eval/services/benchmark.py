"""Creation and management of canonical benchmarks."""

from collections.abc import Sequence
from uuid import uuid4

from rag_eval.db.models import BenchmarkRecord
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import (
    Benchmark,
    BenchmarkCase,
    BenchmarkManifest,
    Chunk,
    CorpusMode,
    Document,
)


class BenchmarkService:
    """Create and modify canonical evaluator-owned benchmarks."""

    def __init__(self, repository: PersistenceRepository) -> None:
        """Bind the service to the caller-managed persistence repository."""
        self._repository = repository

    async def create(
        self,
        *,
        name: str,
        corpus_mode: CorpusMode = CorpusMode.DOCUMENTS,
        version: str = "1",
    ) -> Benchmark:
        """Create an empty benchmark and persist its identity."""
        manifest = BenchmarkManifest(
            benchmark_id=f"benchmark-{uuid4()}",
            name=name,
            version=version,
            corpus_mode=corpus_mode,
        )

        await self._repository.persist_benchmark(manifest)

        return Benchmark(manifest=manifest)


    async def list(self) -> Sequence[BenchmarkRecord]:
        """List all persisted benchmarks."""
        return await self._repository.list_benchmarks()


    async def get(self, benchmark_id: str) -> Benchmark:
        """Load a complete benchmark by ID."""
        benchmark = await self._repository.get_benchmark(benchmark_id)

        if benchmark is None:
            raise KeyError(f"benchmark not found: {benchmark_id}")

        return benchmark

    async def add_cases(
        self,
        benchmark_id: str,
        cases: Sequence[BenchmarkCase],
    ) -> int:
        """Add canonical benchmark cases."""
        await self.get(benchmark_id)

        count = 0

        for case in cases:
            await self._repository.persist_benchmark_case(
                benchmark_id,
                case,
            )
            count += 1

        return count

    async def add_document(
        self,
        benchmark_id: str,
        document: Document,
    ) -> Document:
        """Add one evaluator-owned document to a DOCUMENTS benchmark."""
        benchmark = await self.get(benchmark_id)

        if benchmark.manifest.corpus_mode is not CorpusMode.DOCUMENTS:
            raise ValueError(
                f"benchmark {benchmark_id} uses "
                f"{benchmark.manifest.corpus_mode.value} corpus mode; "
                "documents may only be added to DOCUMENTS benchmarks"
            )

        await self._repository.persist_benchmark_document(
            benchmark_id,
            document,
        )

        return document


    async def add_documents(
        self,
        benchmark_id: str,
        documents: Sequence[Document],
    ) -> int:
        """Add multiple evaluator-owned documents."""
        for document in documents:
            await self.add_document(
                benchmark_id,
                document,
            )

        return len(documents)

    async def add_chunks(
        self,
        benchmark_id: str,
        chunks: Sequence[Chunk],
    ) -> int:
        """Add canonical chunks to a CHUNKS benchmark."""
        benchmark = await self.get(benchmark_id)

        if benchmark.manifest.corpus_mode is not CorpusMode.CHUNKS:
            raise ValueError(
                f"benchmark {benchmark_id} uses "
                f"{benchmark.manifest.corpus_mode.value} corpus mode; "
                "chunks may only be added to CHUNKS benchmarks"
            )

        count = 0

        for chunk in chunks:
            await self._repository.persist_benchmark_chunk(
                benchmark_id,
                chunk,
            )
            count += 1

        return count

    async def register(self, benchmark: Benchmark) -> int:
        """Persist a complete canonical benchmark.

        Useful for benchmark imports. Normal API/CLI creation can instead use
        create(), add_cases(), add_documents(), and add_chunks().
        """
        await self._repository.persist_benchmark(benchmark.manifest)

        for case in benchmark.cases:
            await self._repository.persist_benchmark_case(
                benchmark.manifest.benchmark_id,
                case,
            )

        if benchmark.manifest.corpus_mode is CorpusMode.DOCUMENTS:
            for document in benchmark.documents:
                await self._repository.persist_benchmark_document(
                    benchmark.manifest.benchmark_id,
                    document,
                )

        elif benchmark.manifest.corpus_mode is CorpusMode.CHUNKS:
            for chunk in benchmark.chunks:
                await self._repository.persist_benchmark_chunk(
                    benchmark.manifest.benchmark_id,
                    chunk,
                )

        return benchmark.case_count
