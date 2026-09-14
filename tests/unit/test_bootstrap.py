"""Tests for the Stage 1 application bootstrap."""

from typer.testing import CliRunner

import rag_eval
import rag_eval.artifacts
from rag_eval.cli import app
from rag_eval.config import Settings
from rag_eval.db import create_async_engine, create_session_factory


def test_package_imports_with_version() -> None:
    """The top-level and infrastructure package boundaries are importable."""
    assert rag_eval.__version__ == "0.1.0"
    assert rag_eval.artifacts.__name__ == "rag_eval.artifacts"


def test_cli_version_command_starts_successfully() -> None:
    """The minimal CLI can run without external infrastructure."""
    result = CliRunner().invoke(app, ["version"])

    assert result.exit_code == 0
    assert result.stdout == "rag-eval 0.1.0\n"


def test_settings_build_async_postgres_url_from_environment(monkeypatch) -> None:
    """Settings derive a correctly escaped async PostgreSQL connection URL."""
    monkeypatch.setenv("RAG_EVAL_POSTGRES_HOST", "database.internal")
    monkeypatch.setenv("RAG_EVAL_POSTGRES_PORT", "5433")
    monkeypatch.setenv("RAG_EVAL_POSTGRES_DATABASE", "evaluation")
    monkeypatch.setenv("RAG_EVAL_POSTGRES_USER", "service")
    monkeypatch.setenv("RAG_EVAL_POSTGRES_PASSWORD", "pass word")

    settings = Settings(_env_file=None)

    assert settings.async_database_url == (
        "postgresql+asyncpg://service:pass+word@database.internal:5433/evaluation"
    )


def test_database_factories_are_importable_without_connecting() -> None:
    """Database wiring can be constructed without PostgreSQL being available."""
    engine = create_async_engine(Settings(_env_file=None))
    session_factory = create_session_factory(engine)

    assert engine.dialect.name == "postgresql"
    assert session_factory.kw["bind"] is engine
