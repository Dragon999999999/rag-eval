"""Tests for Stage 13 CLI commands."""

from typer.testing import CliRunner

from rag_eval.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    """Version command should work."""
    result = runner.invoke(app, ["version"])
    assert result.exit_code == 0
    assert "rag-eval" in result.stdout


def test_cli_help() -> None:
    """Help should list all commands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    # Check main commands are present
    assert "validate" in result.stdout
    assert "plan" in result.stdout
    assert "run" in result.stdout
    assert "status" in result.stdout
    assert "corpus" in result.stdout
    assert "target" in result.stdout
    assert "score" in result.stdout


def test_score_help() -> None:
    """Score subcommands should be accessible."""
    result = runner.invoke(app, ["score", "--help"])
    assert result.exit_code == 0
    assert "score" in result.stdout
    assert "report" in result.stdout
    assert "compare" in result.stdout
    assert "export" in result.stdout


def test_target_capabilities_help() -> None:
    """Target capabilities command should exist."""
    result = runner.invoke(app, ["target", "capabilities", "--help"])
    assert result.exit_code == 0


def test_corpus_prepare_help() -> None:
    """Corpus prepare command should exist."""
    result = runner.invoke(app, ["corpus", "prepare", "--help"])
    assert result.exit_code == 0


def test_validate_requires_config() -> None:
    """Validate should fail gracefully without config."""
    result = runner.invoke(app, ["validate"])
    # Should fail with missing argument error
    assert result.exit_code != 0


def test_score_requires_run_id() -> None:
    """Score should fail gracefully without run_id."""
    result = runner.invoke(app, ["score", "score"])
    # Should fail with missing argument error
    assert result.exit_code != 0
