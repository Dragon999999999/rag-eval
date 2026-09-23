"""Tests for the test-definition and test-run CLI commands."""

from pathlib import Path

import pytest
from typer.testing import CliRunner

from rag_eval.cli import app
from rag_eval.cli import test as test_cli

runner = CliRunner()


def test_test_help_lists_configuration_and_run_commands() -> None:
    """The test command group exposes configuration and run operations."""
    result = runner.invoke(app, ["test", "--help"])

    assert result.exit_code == 0
    for command in (
        "create",
        "list",
        "show",
        "set-target",
        "set-benchmark",
        "metrics",
        "set-metrics",
        "import-yaml",
        "export-yaml",
        "validate",
        "start",
        "runs",
        "status",
        "cases",
        "attempts",
        "events",
        "results",
        "pause",
        "resume",
        "recover",
        "cancel",
    ):
        assert command in result.stdout


def test_test_configuration_commands_delegate_to_service_helpers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CRUD and target/benchmark selection commands print service results."""
    updates: list[tuple[str, dict[str, object]]] = []

    async def create_test(*, name: str, description: str | None) -> dict[str, str]:
        assert (name, description) == ("Demo", "A test")
        return {
            "test_definition_id": "test-1",
            "configuration_status": "INCOMPLETE",
        }

    async def update_test(
        test_id: str,
        changes: dict[str, object],
    ) -> dict[str, str | None]:
        updates.append((test_id, changes))
        return {
            "target_id": changes.get("target_id"),
            "benchmark_id": changes.get("benchmark_id"),
            "configuration_status": "READY",
        }

    monkeypatch.setattr(test_cli, "_create_test", create_test)
    monkeypatch.setattr(test_cli, "_update_test", update_test)

    created = runner.invoke(
        app,
        ["test", "create", "Demo", "--description", "A test"],
    )
    assert created.exit_code == 0
    assert "Created test test-1" in created.stdout
    assert "Status: INCOMPLETE" in created.stdout

    for command, expected in (
        (["set-target", "test-1", "target-1"], {"target_id": "target-1"}),
        (["clear-target", "test-1"], {"target_id": None}),
        (["set-benchmark", "test-1", "benchmark-1"], {"benchmark_id": "benchmark-1"}),
        (["clear-benchmark", "test-1"], {"benchmark_id": None}),
    ):
        result = runner.invoke(app, ["test", *command])
        assert result.exit_code == 0
        assert "Status: READY" in result.stdout
        assert updates[-1] == ("test-1", expected)


def test_test_metric_and_yaml_commands_delegate_to_service_helpers(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Metric selection and portable YAML commands preserve their arguments."""
    calls: dict[str, object] = {}

    async def show_metrics(test_id: str) -> dict[str, object]:
        calls["metrics_test_id"] = test_id
        return {
            "mode": "EXPLICIT",
            "metrics": [
                {
                    "metric_id": "answer.exact_match",
                    "version": "1",
                    "selected": True,
                    "applicable": True,
                },
                {
                    "metric_id": "retrieval.recall",
                    "version": "1",
                    "selected": False,
                    "applicable": False,
                    "unavailable_reason": "retrieval data missing",
                },
            ],
            "warnings": [],
            "judge_config": {},
            "retrieval_config": {},
        }

    async def set_metrics(
        test_id: str,
        metric_ids: list[str],
    ) -> dict[str, object]:
        calls["set_metrics"] = (test_id, metric_ids)
        return {"selected_metric_ids": metric_ids}

    async def select_all(test_id: str) -> dict[str, object]:
        calls["select_all"] = test_id
        return {"selected_metric_ids": ["answer.exact_match", "retrieval.recall"]}

    async def import_yaml(test_id: str, config: Path) -> dict[str, str]:
        calls["import_yaml"] = (test_id, config.read_text(encoding="utf-8"))
        return {"status": "imported"}

    async def export_yaml(test_id: str) -> str:
        calls["export_yaml"] = test_id
        return "metrics:\n  mode: EXPLICIT\n"

    monkeypatch.setattr(test_cli, "_show_metrics", show_metrics)
    monkeypatch.setattr(test_cli, "_set_metrics", set_metrics)
    monkeypatch.setattr(test_cli, "_select_all_metrics", select_all)
    monkeypatch.setattr(test_cli, "_import_yaml", import_yaml)
    monkeypatch.setattr(test_cli, "_export_yaml", export_yaml)

    metrics = runner.invoke(app, ["test", "metrics", "test-1"])
    assert metrics.exit_code == 0
    assert "Mode: EXPLICIT" in metrics.stdout
    assert "[x] answer.exact_match v1" in metrics.stdout
    assert "unavailable: retrieval data missing" in metrics.stdout

    selected = runner.invoke(
        app,
        ["test", "set-metrics", "test-1", "answer.exact_match", "retrieval.recall"],
    )
    assert selected.exit_code == 0
    assert calls["set_metrics"] == (
        "test-1",
        ["answer.exact_match", "retrieval.recall"],
    )

    all_metrics = runner.invoke(app, ["test", "select-all-metrics", "test-1"])
    assert all_metrics.exit_code == 0
    assert "Selected all applicable metrics (2)." in all_metrics.stdout

    config = tmp_path / "test.yaml"
    config.write_text("metrics:\n  mode: EXPLICIT\n", encoding="utf-8")
    imported = runner.invoke(app, ["test", "import-yaml", "test-1", str(config)])
    assert imported.exit_code == 0
    assert '"status": "imported"' in imported.stdout
    assert calls["import_yaml"] == ("test-1", config.read_text(encoding="utf-8"))

    output = tmp_path / "exported.yaml"
    exported = runner.invoke(
        app,
        ["test", "export-yaml", "test-1", "--output", str(output)],
    )
    assert exported.exit_code == 0
    assert output.read_text(encoding="utf-8") == "metrics:\n  mode: EXPLICIT\n"


def test_test_run_inspection_and_lifecycle_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Run creation, inspection, and lifecycle commands format service data."""

    async def validate(_test_id: str) -> dict[str, object]:
        return {
            "valid": True,
            "errors": [],
            "warnings": [],
            "resolved_metric_ids": ["answer.exact_match"],
        }

    async def start(_test_id: str) -> dict[str, object]:
        return {"run_id": "run-1", "status": "PENDING", "total_cases": 2}

    async def runs(_test_id: str) -> list[dict[str, object]]:
        return [
            {
                "run_id": "run-1",
                "status": "PENDING",
                "complete_cases": 0,
                "total_cases": 2,
            }
        ]

    async def show_run(_run_id: str) -> dict[str, object]:
        return {"run_id": "run-1", "status": "PENDING"}

    async def status(_run_id: str) -> dict[str, object]:
        return {
            "run_id": "run-1",
            "status": "RUNNING",
            "status_reason": None,
            "complete_cases": 1,
            "failed_cases": 0,
            "running_cases": 1,
            "pending_cases": 0,
            "total_cases": 2,
            "progress_percent": 50.0,
        }

    async def cases(_run_id: str) -> list[dict[str, object]]:
        return [
            {
                "case_execution_id": "exec-1",
                "status": "RUNNING",
                "case_id": "case-1",
                "attempt_count": 1,
            }
        ]

    async def attempts(
        _run_id: str, _case_execution_id: str
    ) -> list[dict[str, object]]:
        return [
            {
                "attempt_number": 1,
                "status": "RUNNING",
                "attempt_id": "attempt-1",
                "request_id": "request-1",
            }
        ]

    async def events(_run_id: str) -> list[dict[str, object]]:
        return [
            {
                "created_at": "2026-09-23T12:00:00Z",
                "event_type": "RUN_CREATED",
                "payload": {},
            }
        ]

    async def results(_run_id: str) -> dict[str, object]:
        return {"results": [], "aggregates": []}

    async def transition(_run_id: str) -> dict[str, str]:
        return {"status": "PAUSED"}

    monkeypatch.setattr(test_cli, "_validate_test", validate)
    monkeypatch.setattr(test_cli, "_start_run", start)
    monkeypatch.setattr(test_cli, "_list_test_runs", runs)
    monkeypatch.setattr(test_cli, "_show_run", show_run)
    monkeypatch.setattr(test_cli, "_run_status", status)
    monkeypatch.setattr(test_cli, "_list_run_cases", cases)
    monkeypatch.setattr(test_cli, "_list_case_attempts", attempts)
    monkeypatch.setattr(test_cli, "_list_run_events", events)
    monkeypatch.setattr(test_cli, "_show_results", results)
    monkeypatch.setattr(test_cli, "_pause_run", transition)
    monkeypatch.setattr(test_cli, "_resume_run", transition)
    monkeypatch.setattr(test_cli, "_recover_run", transition)
    monkeypatch.setattr(test_cli, "_cancel_run", transition)

    assert runner.invoke(app, ["test", "validate", "test-1"]).exit_code == 0
    started = runner.invoke(app, ["test", "start", "test-1"])
    assert started.exit_code == 0
    assert "Run created: run-1" in started.stdout
    assert "Cases: 2" in started.stdout
    assert "run-1  PENDING" in runner.invoke(app, ["test", "runs", "test-1"]).stdout
    assert '"run_id": "run-1"' in runner.invoke(app, ["test", "run", "run-1"]).stdout
    assert (
        "Progress: 1/2 (50.0%)"
        in runner.invoke(app, ["test", "status", "run-1"]).stdout
    )
    assert "exec-1  RUNNING" in runner.invoke(app, ["test", "cases", "run-1"]).stdout
    assert (
        "#1 RUNNING"
        in runner.invoke(app, ["test", "attempts", "run-1", "exec-1"]).stdout
    )
    assert "RUN_CREATED" in runner.invoke(app, ["test", "events", "run-1"]).stdout
    assert '"aggregates": []' in runner.invoke(app, ["test", "results", "run-1"]).stdout

    for command in ("pause", "resume", "recover", "cancel"):
        result = runner.invoke(
            app,
            ["test", command, "run-1", "--yes"]
            if command == "cancel"
            else ["test", command, "run-1"],
        )
        assert result.exit_code == 0
        assert "Run run-1: PAUSED" in result.stdout


def test_test_commands_convert_service_errors_to_cli_failures(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Service errors are reported consistently and return a nonzero exit code."""

    async def fail(*_args: object, **_kwargs: object) -> dict[str, str]:
        raise ValueError("invalid configuration")

    monkeypatch.setattr(test_cli, "_create_test", fail)
    result = runner.invoke(app, ["test", "create", "Demo"])

    assert result.exit_code == 1
    assert "create failed: invalid configuration" in result.output
