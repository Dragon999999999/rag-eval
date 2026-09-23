"""Tests for scoring and reporting CLI compatibility."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from rag_eval.cli import app
from rag_eval.cli import score as score_cli

runner = CliRunner()


def test_score_help_lists_scoring_and_reporting_commands() -> None:
    """Score command group exposes score, report, compare, and export."""
    result = runner.invoke(app, ["score", "--help"])

    assert result.exit_code == 0
    for command in ("score", "report", "compare", "export"):
        assert command in result.stdout


def test_score_command_requires_run_id() -> None:
    """The nested score command keeps required argument validation."""
    result = runner.invoke(app, ["score", "score"])

    assert result.exit_code != 0


def test_score_commands_format_service_results(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Scoring, reporting, comparison, and export commands delegate correctly."""

    async def score_run(_run_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            scored_cases=2,
            total_cases=2,
            total_metrics_computed=4,
            total_metrics_unavailable=1,
            total_metrics_failed=0,
            aggregates_persisted=3,
        )

    async def generate_report(_run_id: str) -> str:
        return "report text"

    async def compare_runs(_run_a: str, _run_b: str) -> str:
        return "comparison text"

    async def export_run(_run_id: str, output_dir: Path) -> SimpleNamespace:
        return SimpleNamespace(
            export_path=output_dir / "run-1",
            files=["manifest.yaml", "metrics.parquet"],
        )

    monkeypatch.setattr(score_cli, "_score_run", score_run)
    monkeypatch.setattr(score_cli, "_generate_report", generate_report)
    monkeypatch.setattr(score_cli, "_compare_runs", compare_runs)
    monkeypatch.setattr(score_cli, "_export_run", export_run)

    scored = runner.invoke(app, ["score", "score", "run-1"])
    assert scored.exit_code == 0
    assert "Scored run run-1:" in scored.stdout
    assert "Cases: 2/2" in scored.stdout
    assert "Metrics unavailable: 1" in scored.stdout

    report_path = tmp_path / "report.txt"
    report = runner.invoke(app, ["score", "report", "run-1", "-o", str(report_path)])
    assert report.exit_code == 0
    assert report_path.read_text(encoding="utf-8") == "report text"
    assert "Report written to" in report.stdout

    comparison = runner.invoke(app, ["score", "compare", "run-a", "run-b"])
    assert comparison.exit_code == 0
    assert "comparison text" in comparison.stdout

    exported = runner.invoke(
        app,
        ["score", "export", "run-1", "-o", str(tmp_path / "exports")],
    )
    assert exported.exit_code == 0
    assert "manifest.yaml" in exported.stdout


def test_score_command_maps_service_errors_to_cli_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A missing run produces the documented nonzero CLI result."""

    async def fail(_run_id: str) -> object:
        raise KeyError("run-1 not found")

    monkeypatch.setattr(score_cli, "_score_run", fail)
    result = runner.invoke(app, ["score", "score", "run-1"])

    assert result.exit_code == 1
    assert "scoring failed: 'run-1 not found'" in result.output


def test_score_run_uses_split_test_and_target_repositories(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The score command wires TestRepository and TargetRepository separately."""
    import rag_eval.config

    class Engine:
        async def dispose(self) -> None:
            pass

    class SessionContext:
        async def __aenter__(self) -> "SessionContext":
            return self

        async def __aexit__(self, *_args: object) -> None:
            pass

        def begin(self) -> "SessionContext":
            return self

    class Factory:
        def __call__(self) -> SessionContext:
            return SessionContext()

    repositories: list[object] = []

    class TestRepository:
        def __init__(self, session: object) -> None:
            repositories.append(("test", self))

    class TargetRepository:
        def __init__(self, session: object) -> None:
            repositories.append(("target", self))

    class Service:
        def __init__(self, registry: object, test: object, target: object) -> None:
            assert registry == "registry"
            assert test is repositories[0][1]
            assert target is repositories[1][1]

        async def score_run(self, run_id: str) -> str:
            return run_id

    monkeypatch.setattr(rag_eval.config, "get_settings", lambda: object())
    monkeypatch.setattr(score_cli, "create_async_engine", lambda _settings: Engine())
    monkeypatch.setattr(score_cli, "create_session_factory", lambda _engine: Factory())
    monkeypatch.setattr(score_cli, "TestRepository", TestRepository)
    monkeypatch.setattr(score_cli, "TargetRepository", TargetRepository)
    monkeypatch.setattr(score_cli, "get_stage12_catalog", lambda: "registry")
    monkeypatch.setattr(score_cli, "ScoringService", Service)

    import asyncio

    assert asyncio.run(score_cli._score_run("run-1")) == "run-1"
    assert [kind for kind, _session in repositories] == ["test", "target"]
