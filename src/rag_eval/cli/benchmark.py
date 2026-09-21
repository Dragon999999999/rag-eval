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
from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import Benchmark, CorpusMode, Document
from rag_eval.services import BenchmarkService


app = typer.Typer(
    help="Create and manage evaluation benchmarks."
)


# ============================================================================
# Commands
# ============================================================================


@app.command("create")
def create_benchmark(
    name: str = typer.Argument(
        ...,
        help="Benchmark name",
    ),
    corpus_mode: CorpusMode = typer.Option(
        CorpusMode.DOCUMENTS,
        "--corpus-mode",
        help="Benchmark corpus representation",
    ),
    cases: list[Path] = typer.Option(
        [],
        "--cases",
        help=(
            "JSON/JSONL case file. "
            "May be specified multiple times."
        ),
    ),
    docs: list[Path] = typer.Option(
        [],
        "--docs",
        help=(
            "Document file. "
            "May be specified multiple times."
        ),
    ),
    chunks: list[Path] = typer.Option(
        [],
        "--chunks",
        help=(
            "JSON/JSONL chunk file. "
            "May be specified multiple times."
        ),
    ),
) -> None:
    """Create a benchmark and optionally import contents."""

    if (
        corpus_mode is CorpusMode.DOCUMENTS
        and chunks
    ):
        raise typer.BadParameter(
            "--chunks cannot be used with "
            "--corpus-mode DOCUMENTS"
        )

    if (
        corpus_mode is CorpusMode.CHUNKS
        and docs
    ):
        raise typer.BadParameter(
            "--docs cannot be used with "
            "--corpus-mode CHUNKS"
        )

    if (
        corpus_mode is CorpusMode.EXTERNAL
        and (docs or chunks)
    ):
        raise typer.BadParameter(
            "EXTERNAL benchmarks cannot contain "
            "documents or chunks"
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


@app.command("list")
def list_benchmarks() -> None:
    """List all persisted benchmarks."""
    benchmarks = asyncio.run(
        _list_benchmarks()
    )

    if not benchmarks:
        typer.echo("No benchmarks found.")
        return

    for benchmark in benchmarks:
        typer.echo(
            f"{benchmark.manifest.benchmark_id}  "
            f"{benchmark.manifest.name}  "
            f"[{benchmark.manifest.corpus_mode.value}]  "
            f"cases={benchmark.case_count} "
            f"documents={benchmark.document_count} "
            f"chunks={benchmark.chunk_count}"
        )


@app.command("show")
def show_benchmark(
    benchmark_id: str = typer.Argument(...),
) -> None:
    """Show benchmark metadata and content counts."""
    benchmark = asyncio.run(
        _get_benchmark(benchmark_id)
    )

    typer.echo(
        f"Benchmark: {benchmark.manifest.name}"
    )
    typer.echo(
        f"ID: {benchmark.manifest.benchmark_id}"
    )
    typer.echo(
        "Corpus mode: "
        f"{benchmark.manifest.corpus_mode.value}"
    )
    typer.echo(
        f"Cases: {benchmark.case_count}"
    )
    typer.echo(
        f"Documents: {benchmark.document_count}"
    )
    typer.echo(
        f"Chunks: {benchmark.chunk_count}"
    )

    modes = ", ".join(
        mode.value
        for mode in benchmark.available_corpus_modes
    )

    typer.echo(
        f"Available modes: {modes or 'none'}"
    )


@app.command("add-cases")
def add_cases(
    benchmark_id: str = typer.Argument(...),
    files: list[Path] = typer.Argument(...),
) -> None:
    """Import cases from JSON/JSONL files."""
    count = asyncio.run(
        _add_cases(
            benchmark_id,
            files,
        )
    )

    typer.echo(
        f"Added {count} cases to {benchmark_id}"
    )


@app.command("add-documents")
def add_documents(
    benchmark_id: str = typer.Argument(...),
    files: list[Path] = typer.Argument(...),
) -> None:
    """Upload one or more atomic documents."""
    count = asyncio.run(
        _add_documents(
            benchmark_id,
            files,
        )
    )

    typer.echo(
        f"Added {count} documents to {benchmark_id}"
    )


@app.command("add-chunks")
def add_chunks(
    benchmark_id: str = typer.Argument(...),
    files: list[Path] = typer.Argument(...),
) -> None:
    """Import chunks from JSON/JSONL files."""
    count = asyncio.run(
        _add_chunks(
            benchmark_id,
            files,
        )
    )

    typer.echo(
        f"Added {count} chunks to {benchmark_id}"
    )


@app.command("set-corpus-mode")
def set_corpus_mode(
    benchmark_id: str = typer.Argument(...),
    corpus_mode: CorpusMode = typer.Argument(...),
) -> None:
    """Change DOCUMENTS/CHUNKS representation."""
    try:
        benchmark = asyncio.run(
            _set_corpus_mode(
                benchmark_id,
                corpus_mode,
            )
        )
    except ValueError as exc:
        raise typer.BadParameter(
            str(exc)
        ) from exc

    typer.echo(
        f"{benchmark.manifest.benchmark_id}: "
        f"corpus mode is now "
        f"{benchmark.manifest.corpus_mode.value}"
    )


@app.command("delete")
def delete_benchmark(
    benchmark_id: str = typer.Argument(...),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation",
    ),
) -> None:
    """Delete a benchmark."""
    if not yes:
        confirmed = typer.confirm(
            f"Delete benchmark {benchmark_id}?"
        )

        if not confirmed:
            raise typer.Abort()

    asyncio.run(
        _delete_benchmark(
            benchmark_id
        )
    )

    typer.echo(
        f"Deleted {benchmark_id}"
    )


# ============================================================================
# Async implementations
# ============================================================================


async def _create_benchmark(
    *,
    name: str,
    corpus_mode: CorpusMode,
    case_files: list[Path],
    document_files: list[Path],
    chunk_files: list[Path],
) -> str:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            async with session.begin():
                service, artifact_service = (
                    _build_services(session)
                )

                benchmark = await service.create(
                    name=name,
                    corpus_mode=corpus_mode,
                )

                benchmark_id = (
                    benchmark.manifest.benchmark_id
                )

                for path in case_files:
                    await service.add_cases(
                        benchmark_id,
                        load_cases(path),
                    )

                for path in document_files:
                    document = (
                        await _store_document(
                            artifact_service,
                            path,
                        )
                    )

                    await service.create_document(
                        benchmark_id,
                        document,
                    )

                for path in chunk_files:
                    await service.add_chunks(
                        benchmark_id,
                        load_chunks(path),
                    )

                return benchmark_id

    finally:
        await engine.dispose()


async def _list_benchmarks(
) -> list[Benchmark]:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            service, _ = _build_services(
                session
            )

            records = (
                await service.list_benchmarks()
            )

            result: list[Benchmark] = []

            for record in records:
                result.append(
                    await service.get(
                        record.benchmark_id
                    )
                )

            return result

    finally:
        await engine.dispose()


async def _get_benchmark(
    benchmark_id: str,
) -> Benchmark:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            service, _ = _build_services(
                session
            )

            return await service.get(
                benchmark_id
            )

    finally:
        await engine.dispose()


async def _add_cases(
    benchmark_id: str,
    files: list[Path],
) -> int:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            async with session.begin():
                service, _ = _build_services(
                    session
                )

                count = 0

                for path in files:
                    cases = load_cases(path)

                    count += await service.add_cases(
                        benchmark_id,
                        cases,
                    )

                return count

    finally:
        await engine.dispose()


async def _add_documents(
    benchmark_id: str,
    files: list[Path],
) -> int:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            async with session.begin():
                service, artifact_service = (
                    _build_services(session)
                )

                count = 0

                for path in files:
                    document = (
                        await _store_document(
                            artifact_service,
                            path,
                        )
                    )

                    await service.create_document(
                        benchmark_id,
                        document,
                    )

                    count += 1

                return count

    finally:
        await engine.dispose()


async def _add_chunks(
    benchmark_id: str,
    files: list[Path],
) -> int:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            async with session.begin():
                service, _ = _build_services(
                    session
                )

                count = 0

                for path in files:
                    chunks = load_chunks(
                        path
                    )

                    count += await service.add_chunks(
                        benchmark_id,
                        chunks,
                    )

                return count

    finally:
        await engine.dispose()


async def _set_corpus_mode(
    benchmark_id: str,
    corpus_mode: CorpusMode,
) -> Benchmark:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            async with session.begin():
                service, _ = _build_services(
                    session
                )

                return (
                    await service.set_corpus_mode(
                        benchmark_id,
                        corpus_mode,
                    )
                )

    finally:
        await engine.dispose()


async def _delete_benchmark(
    benchmark_id: str,
) -> None:
    engine = create_async_engine(
        get_settings()
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            async with session.begin():
                service, _ = _build_services(
                    session
                )

                await service.delete(
                    benchmark_id
                )

    finally:
        await engine.dispose()


# ============================================================================
# Composition helpers
# ============================================================================


def _build_services(
    session,
) -> tuple[
    BenchmarkService,
    ArtifactService,
]:
    """Build transaction-scoped services."""
    benchmark_repository = (
        BenchmarkRepository(session)
    )

    persistence_repository = (
        PersistenceRepository(session)
    )

    store = LocalArtifactStore(
        root=Path("./data")
    )

    artifact_service = ArtifactService(
        store,
        persistence_repository,
    )

    benchmark_service = BenchmarkService(
        benchmark_repository,
        artifact_service,
    )

    return (
        benchmark_service,
        artifact_service,
    )


async def _store_document(
    artifact_service: ArtifactService,
    path: Path,
) -> Document:
    """Persist one document artifact and build its canonical model."""
    mime_type = mimetypes.guess_type(
        path.name
    )[0]

    artifact = await artifact_service.put(
        path,
        artifact_type=ArtifactType.SOURCE_DOCUMENT,
        content_type=mime_type,
        metadata={
            "filename": path.name,
        },
    )

    return Document(
        document_id=f"document-{uuid4()}",
        filename=path.name,
        mime_type=mime_type,
        sha256=artifact.sha256,
        size_bytes=artifact.size_bytes,
        artifact=artifact,
    )