"""Command-line interface for the rag-eval application."""

import typer

from rag_eval import __version__

app = typer.Typer(
    name="rag-eval",
    help="Infrastructure foundation for reproducible RAG evaluation.",
    no_args_is_help=True,
)


@app.callback()
def main() -> None:
    """Provide the rag-eval command group."""


@app.command()
def version() -> None:
    """Print the installed application version."""
    typer.echo(f"rag-eval {__version__}")
