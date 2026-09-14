"""Command-line interface for the rag-eval application."""

from pathlib import Path

import typer

from rag_eval import __version__
from rag_eval.config import (
    ConfigurationError,
    configuration_hash,
    expand_matrix,
    load_experiment_config,
)

app = typer.Typer(
    name="rag-eval",
    help="Infrastructure foundation for reproducible RAG evaluation.",
    no_args_is_help=True,
)
CONFIG_ARGUMENT = typer.Argument(..., exists=True, readable=True)


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
