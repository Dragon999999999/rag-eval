"""Command-line interface for the rag-eval application."""

import typer

from rag_eval import __version__
from rag_eval.cli import benchmark as benchmark_commands
from rag_eval.cli import score as score_commands
from rag_eval.cli import target as target_commands
from rag_eval.cli import test as test_commands

app = typer.Typer(
    name="rag-eval",
    help="Infrastructure foundation for reproducible RAG evaluation.",
    no_args_is_help=True,
)


# ---------------------------------------------------------------------------
# Command groups
# ---------------------------------------------------------------------------

app.add_typer(
    benchmark_commands.app,
    name="benchmark",
)

app.add_typer(
    target_commands.app,
    name="target",
)

app.add_typer(
    test_commands.app,
    name="test",
)

app.add_typer(
    score_commands.app,
    name="score",
)


@app.callback()
def main() -> None:
    """Provide the rag-eval command group."""


@app.command()
def version() -> None:
    """Print the installed application version."""
    typer.echo(f"rag-eval {__version__}")