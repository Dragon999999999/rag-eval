"""Command-line interface for the rag-eval application."""

import asyncio
from pathlib import Path

import typer

from rag_eval import __version__
from rag_eval.adapters import TargetAdapterError, create_target_adapter
from rag_eval.artifacts import ArtifactService, create_artifact_store
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
from rag_eval.db.models import RunRecord
from rag_eval.execution import BenchmarkExecutor
from rag_eval.models.enums import RunStatus
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


@app.command()
def run(
    config: Path = CONFIG_ARGUMENT,
) -> None:
    """Execute a benchmark run with durable persistence."""
    try:
        run_id = asyncio.run(_execute_run(config))
    except (
        ConfigurationError,
        DatasetValidationError,
        TargetAdapterError,
        TimeoutError,
        ValueError,
    ) as exc:
        typer.echo(f"run failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    typer.echo(f"run completed: {run_id}")


@app.command()
def status(
    run_id: str = typer.Argument(..., help="Run identifier to inspect"),
) -> None:
    """Display concise status of a persisted run."""
    try:
        asyncio.run(_show_run_status(run_id))
    except (KeyError, ConfigurationError, ValueError) as exc:
        typer.echo(f"status lookup failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc


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


async def _execute_run(config_path: Path) -> str:
    """Execute a benchmark run and return the run ID."""
    import uuid
    
    experiment = load_experiment_config(config_path)
    adapter = create_target_adapter(experiment.target)
    engine = create_async_engine(get_settings())
    
    run_id = f"run-{uuid.uuid4().hex}"
    
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)
            
            # Create run record
            run = RunRecord(
                run_id=run_id,
                name=experiment.run.name,
                status=RunStatus.PENDING.value,
                config_hash=configuration_hash(experiment),
                target_id=f"{experiment.target.adapter}-target",
                seed=experiment.run.seed,
                tags=experiment.run.tags,
                metadata_json=experiment.run.metadata,
            )
            
            # Persist canonical config
            canonical_config = experiment.model_dump(mode="json")
            await repository.create_run(run, canonical_config)
            
            # Persist target identity
            from rag_eval.models import TargetInfo
            target_info = TargetInfo(
                name=f"{experiment.target.adapter}-target",
                version="1.0",
                implementation=experiment.target.adapter,
            )
            await repository.persist_target(run.target_id, target_info)
            
            await session.flush()
        
        # Load dataset and execute
        if experiment.dataset.manifest is None:
            raise ConfigurationError("run requires dataset.manifest")
        
        dataset = NativeBenchmarkDataset(Path(experiment.dataset.manifest))
        dataset.validate()
        manifest = dataset.load_manifest()
        
        # Create artifact store
        store = create_artifact_store(get_settings())
        artifact_service = ArtifactService(store, repository)
        
        # Execute benchmark
        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)
            executor = BenchmarkExecutor(
                experiment, adapter, artifact_service, repository, session
            )
            result = await executor.execute(run_id, manifest)
        
        typer.echo(f"Run {run_id}: {result.completed}/{result.total_cases} completed")
        if result.failed > 0:
            typer.echo(f"  Failed: {result.failed}")
        
        return run_id
        
    finally:
        close = getattr(adapter, "aclose", None)
        if close is not None:
            await close()
        await engine.dispose()


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


async def _show_run_status(run_id: str) -> None:
    """Display status of a run."""
    engine = create_async_engine(get_settings())
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            repository = PersistenceRepository(session)
            run = await repository.get_run(run_id)
            
            if run is None:
                raise KeyError(f"run not found: {run_id}")
            
            typer.echo(f"Run: {run.run_id}")
            typer.echo(f"Status: {run.status}")
            typer.echo(f"Name: {run.name}")
            
            if run.started_at:
                typer.echo(f"Started: {run.started_at}")
            if run.finished_at:
                typer.echo(f"Finished: {run.finished_at}")
            
            # Count case executions
            case_executions = await repository.list_case_executions(run_id)
            
            total = len(case_executions)
            pending = sum(1 for c in case_executions if c.status == "PENDING")
            running = sum(1 for c in case_executions if c.status == "RUNNING")
            target_complete = sum(1 for c in case_executions if c.status == "TARGET_COMPLETE")
            complete = sum(1 for c in case_executions if c.status == "COMPLETE")
            failed = sum(1 for c in case_executions if c.status == "FAILED")
            
            typer.echo()
            typer.echo("Cases:")
            typer.echo(f"  total:            {total}")
            typer.echo(f"  pending:          {pending}")
            typer.echo(f"  running:          {running}")
            typer.echo(f"  target_complete:  {target_complete}")
            typer.echo(f"  complete:         {complete}")
            typer.echo(f"  failed:           {failed}")
            
    finally:
        await engine.dispose()
