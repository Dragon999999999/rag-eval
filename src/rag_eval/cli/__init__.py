"""Command-line interface for the rag-eval application."""

import asyncio
from pathlib import Path

import typer

from rag_eval import __version__
from rag_eval.adapters import TargetAdapterError, create_target_adapter
from rag_eval.config import (
    ConfigurationError,
    configuration_hash,
    expand_matrix,
    get_settings,
    load_experiment_config,
)
from rag_eval.datasets import DatasetValidationError, NativeBenchmarkDataset
from rag_eval.db import (
    PersistenceRepository,
    create_async_engine,
    create_session_factory,
)
from rag_eval.services import BenchmarkRegistrationService, CorpusPreparationService

app = typer.Typer(
    name="rag-eval",
    help="Infrastructure foundation for reproducible RAG evaluation.",
    no_args_is_help=True,
)
CONFIG_ARGUMENT = typer.Argument(..., exists=True, readable=True)
corpus_app = typer.Typer(help="Prepare and register benchmark corpora.")
app.add_typer(corpus_app, name="corpus")


@app.callback()
def main() -> None:
    """Provide the rag-eval command group."""


@app.command()
def version() -> None:
    """Print the installed application version."""
    typer.echo(f"rag-eval {__version__}")


@app.command()
def validate(
    config: Path = CONFIG_ARGUMENT,
) -> None:
    """Load and validate a YAML experiment configuration without execution."""
    try:
        load_experiment_config(config)
    except ConfigurationError as exc:
        typer.echo(f"configuration invalid: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo("configuration valid")


@app.command()
def plan(
    config: Path = CONFIG_ARGUMENT,
) -> None:
    """Display a validated, non-executing experiment matrix summary."""
    try:
        experiment = load_experiment_config(config)
        combinations = expand_matrix(experiment)
    except ConfigurationError as exc:
        typer.echo(f"configuration invalid: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo("configuration valid")
    typer.echo(f"matrix combinations: {len(combinations)}")
    typer.echo(f"target adapter: {experiment.target.adapter}")
    typer.echo(f"corpus mode: {experiment.target.corpus.mode}")
    typer.echo(f"metrics mode: {experiment.metrics.mode}")
    typer.echo(f"configuration hash: {configuration_hash(experiment)}")


@corpus_app.command("prepare")
def corpus_prepare(config: Path = CONFIG_ARGUMENT) -> None:
    """Validate, register, and prepare a corpus without executing benchmark queries."""
    try:
        experiment = load_experiment_config(config)
        if experiment.dataset.manifest is None:
            raise ConfigurationError("corpus preparation requires dataset.manifest")
        dataset = NativeBenchmarkDataset(Path(experiment.dataset.manifest))
        dataset.validate()
        prepared, case_count = asyncio.run(_prepare_corpus(experiment, dataset))
    except (
        ConfigurationError,
        DatasetValidationError,
        TargetAdapterError,
        TimeoutError,
        ValueError,
    ) as exc:
        typer.echo(f"corpus preparation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"corpus {prepared.corpus_id}: {prepared.status}")
    typer.echo(f"registered cases: {case_count}")


async def _prepare_corpus(experiment: object, dataset: NativeBenchmarkDataset):
    """Wire configuration-owned resources for the CLI corpus preparation command."""
    adapter = create_target_adapter(experiment.target)
    engine = create_async_engine(get_settings())
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)
            case_count = await BenchmarkRegistrationService(repository).register(
                dataset
            )
            prepared = await CorpusPreparationService(
                adapter,
                repository,
                poll_timeout_seconds=experiment.execution.total_timeout,
            ).prepare(dataset, experiment.target.corpus)
        return prepared, case_count
    finally:
        close = getattr(adapter, "aclose", None)
        if close is not None:
            await close()
        await engine.dispose()
