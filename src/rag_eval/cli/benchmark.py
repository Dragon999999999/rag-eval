"""CLI commands for creating and managing benchmarks."""

import asyncio
import mimetypes
from pathlib import Path
from uuid import uuid4

import typer

from rag_eval.artifacts.local import LocalArtifactStore
from rag_eval.artifacts.service import ArtifactService, ArtifactType
from rag_eval.config import get_settings
from rag_eval.datasets.native import load_cases, load_chunks
from rag_eval.db import create_async_engine, create_session_factory
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import CorpusMode, Document
from rag_eval.services import BenchmarkService

app = typer.Typer(help="Create and manage evaluation benchmarks.")


@app.command("create")
def create_benchmark(
    name: str = typer.Argument(..., help="Benchmark name"),
    corpus_mode: CorpusMode = typer.Option(
        CorpusMode.DOCUMENTS,
        "--corpus-mode",
        help="Benchmark corpus representation",
    ),
    cases: list[Path] = typer.Option(
        [],
        "--cases",
        help="JSON/JSONL case file. May be specified multiple times.",
    ),
    docs: list[Path] = typer.Option(
        [],
        "--docs",
        help="Document file. May be specified multiple times.",
    ),
    chunks: list[Path] = typer.Option(
        [],
        "--chunks",
        help="JSON/JSONL chunk file. May be specified multiple times.",
    ),
) -> None:
    """Create a benchmark and optionally add cases/documents/chunks."""

    if corpus_mode is CorpusMode.DOCUMENTS and chunks:
        raise typer.BadParameter(
            "--chunks cannot be used with --corpus-mode DOCUMENTS"
        )

    if corpus_mode is CorpusMode.CHUNKS and docs:
        raise typer.BadParameter(
            "--docs cannot be used with --corpus-mode CHUNKS"
        )

    if corpus_mode is CorpusMode.EXTERNAL:
        if docs or chunks:
            raise typer.BadParameter(
                "EXTERNAL benchmarks cannot contain documents or chunks"
            )

    benchmark_id = asyncio.run(
        _create_benchmark(
            name=name,
            corpus_mode=corpus_mode,
            case_files=cases,
            document_files=docs,
            chunk_files=chunks,
        )
    )

    typer.echo(benchmark_id)


@app.command("add-cases")
def add_cases(
    benchmark_id: str = typer.Argument(...),
    files: list[Path] = typer.Argument(...),
) -> None:
    """Add one or more JSON/JSONL case files."""

    count = asyncio.run(_add_cases(benchmark_id, files))
    typer.echo(f"Added {count} cases to {benchmark_id}")


@app.command("add-documents")
def add_documents(
    benchmark_id: str = typer.Argument(...),
    files: list[Path] = typer.Argument(...),
) -> None:
    """Add one or more document files."""

    count = asyncio.run(_add_documents(benchmark_id, files))
    typer.echo(f"Added {count} documents to {benchmark_id}")


@app.command("add-chunks")
def add_chunks(
    benchmark_id: str = typer.Argument(...),
    files: list[Path] = typer.Argument(...),
) -> None:
    """Add chunks from one or more JSON/JSONL files."""

    count = asyncio.run(_add_chunks(benchmark_id, files))
    typer.echo(f"Added {count} chunks to {benchmark_id}")


@app.command("show")
def show_benchmark(
    benchmark_id: str = typer.Argument(...),
) -> None:
    """Show benchmark metadata and content counts."""

    benchmark = asyncio.run(_get_benchmark(benchmark_id))

    typer.echo(f"Benchmark: {benchmark.manifest.name}")
    typer.echo(f"ID: {benchmark.manifest.benchmark_id}")
    typer.echo(f"Corpus mode: {benchmark.manifest.corpus_mode.value}")
    typer.echo(f"Cases: {benchmark.case_count}")
    typer.echo(f"Documents: {benchmark.document_count}")
    typer.echo(f"Chunks: {benchmark.chunk_count}")

    modes = ", ".join(
        mode.value for mode in benchmark.available_corpus_modes
    )
    typer.echo(f"Available modes: {modes or 'none'}")


async def _create_benchmark(
    *,
    name: str,
    corpus_mode: CorpusMode,
    case_files: list[Path],
    document_files: list[Path],
    chunk_files: list[Path],
) -> str:
    engine = create_async_engine(get_settings())

    try:
        session_factory = create_session_factory(engine)

        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)
            store = LocalArtifactStore(root=Path("./data"))
            artifact_service = ArtifactService(store, repository)
            service = BenchmarkService(repository)

            benchmark = await service.create(
                name=name,
                corpus_mode=corpus_mode,
            )

            for path in case_files:
                await service.add_cases(
                    benchmark.manifest.benchmark_id,
                    load_cases(path),
                )

            for path in document_files:
                content = path.read_bytes()
                mime_type = mimetypes.guess_type(path.name)[0]

                artifact = await artifact_service.put(
                    content,
                    artifact_type=ArtifactType.SOURCE_DOCUMENT,
                    content_type=mime_type,
                )

                document = Document(
                    document_id=f"document-{uuid4()}",
                    filename=path.name,
                    mime_type=mime_type,
                    size_bytes=len(content),
                    artifact=artifact,
                )

                await service.add_document(
                    benchmark.manifest.benchmark_id,
                    document,
                )

            for path in chunk_files:
                await service.add_chunks(
                    benchmark.manifest.benchmark_id,
                    load_chunks(path),
                )

            return benchmark.manifest.benchmark_id

    finally:
        await engine.dispose()


async def _add_cases(
    benchmark_id: str,
    files: list[Path],
) -> int:
    engine = create_async_engine(get_settings())

    try:
        session_factory = create_session_factory(engine)

        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)
            service = BenchmarkService(repository)

            count = 0

            for path in files:
                cases = load_cases(path)
                await service.add_cases(benchmark_id, cases)
                count += len(cases)

            return count

    finally:
        await engine.dispose()


async def _add_documents(
    benchmark_id: str,
    files: list[Path],
) -> int:
    engine = create_async_engine(get_settings())

    try:
        session_factory = create_session_factory(engine)

        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)
            service = BenchmarkService(repository)

            documents: list[Document] = []

            for path in files:
                document = Document(
                    document_id=f"document-{uuid4()}",
                    filename=path.name,
                    mime_type=mimetypes.guess_type(path.name)[0],
                    size_bytes=path.stat().st_size,
                )

                documents.append(document)

            return await service.add_documents(
                benchmark_id,
                documents,
            )

    finally:
        await engine.dispose()


async def _add_chunks(
    benchmark_id: str,
    files: list[Path],
) -> int:
    engine = create_async_engine(get_settings())

    try:
        session_factory = create_session_factory(engine)

        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)
            service = BenchmarkService(repository)

            count = 0

            for path in files:
                chunks = load_chunks(path)
                await service.add_chunks(benchmark_id, chunks)
                count += len(chunks)

            return count

    finally:
        await engine.dispose()


async def _get_benchmark(benchmark_id: str):
    engine = create_async_engine(get_settings())

    try:
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            repository = PersistenceRepository(session)
            service = BenchmarkService(repository)

            return await service.get(benchmark_id)

    finally:
        await engine.dispose()