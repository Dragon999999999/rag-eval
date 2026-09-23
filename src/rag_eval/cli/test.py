"""CLI commands for test configuration and evaluation-run lifecycle."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, NoReturn

import typer

from rag_eval.config import get_settings
from rag_eval.db import create_async_engine, create_session_factory
from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.db.test_repository import TestRepository
from rag_eval.metrics import get_stage12_catalog
from rag_eval.services.test_service import TestService

app = typer.Typer(
    help="Create, configure, validate, and run evaluation tests.",
    no_args_is_help=True,
)


# ============================================================================
# Service construction
# ============================================================================


@asynccontextmanager
async def _service_context() -> AsyncIterator[TestService]:
    """Create one transaction-scoped TestService for a CLI operation."""
    engine = create_async_engine(get_settings())

    try:
        session_factory = create_session_factory(engine)

        async with session_factory() as session:
            async with session.begin():
                service = TestService(
                    repository=TestRepository(session),
                    target_repository=TargetRepository(session),
                    benchmark_repository=BenchmarkRepository(session),
                    metric_registry=get_stage12_catalog(),
                )

                yield service
    finally:
        await engine.dispose()


def _run(coro: Any) -> Any:
    """Execute one asynchronous CLI operation."""
    return asyncio.run(coro)


def _echo_json(value: Any) -> None:
    """Print JSON-friendly service output."""
    typer.echo(
        json.dumps(
            value,
            indent=2,
            default=str,
            ensure_ascii=False,
        )
    )


def _handle_error(prefix: str, exc: Exception) -> NoReturn:
    """Print a consistent CLI error and terminate."""
    typer.echo(
        f"{prefix}: {exc}",
        err=True,
    )
    raise typer.Exit(code=1) from exc


# ============================================================================
# Test CRUD
# ============================================================================


@app.command("create")
def create_test(
    name: str = typer.Argument(
        ...,
        help="Human-readable test name.",
    ),
    description: str | None = typer.Option(
        None,
        "--description",
        "-d",
        help="Optional test description.",
    ),
) -> None:
    """Create an incomplete test. Only the name is required."""
    try:
        result = _run(
            _create_test(
                name=name,
                description=description,
            )
        )
    except (ValueError, KeyError) as exc:
        _handle_error("create failed", exc)

    typer.echo(
        f"Created test {result['test_definition_id']}"
    )
    typer.echo(
        f"Status: {result['configuration_status']}"
    )


async def _create_test(
    *,
    name: str,
    description: str | None,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.create_test(
            name=name,
            description=description,
        )


@app.command("list")
def list_tests() -> None:
    """List all test definitions."""
    try:
        tests = _run(_list_tests())
    except Exception as exc:
        _handle_error("list failed", exc)

    if not tests:
        typer.echo("No tests.")
        return

    for test in tests:
        target = test.get("target_id") or "-"
        benchmark = test.get("benchmark_id") or "-"

        typer.echo(
            f"{test['test_definition_id']}  "
            f"{test['configuration_status']:<10}  "
            f"{test['name']}"
        )
        typer.echo(
            f"  target={target} benchmark={benchmark}"
        )


async def _list_tests() -> list[dict[str, Any]]:
    async with _service_context() as service:
        return await service.list_tests()


@app.command("show")
def show_test(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
) -> None:
    """Show the current editable test configuration."""
    try:
        result = _run(_show_test(test_id))
    except KeyError as exc:
        _handle_error("show failed", exc)

    _echo_json(result)


async def _show_test(
    test_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        result = await service.get_test(test_id)

        if result is None:
            raise KeyError(
                f"test not found: {test_id}"
            )

        return result


@app.command("delete")
def delete_test(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation.",
    ),
) -> None:
    """Delete an editable test definition."""
    if not yes:
        confirmed = typer.confirm(
            f"Delete test {test_id}?"
        )
        if not confirmed:
            raise typer.Abort()

    try:
        _run(_delete_test(test_id))
    except KeyError as exc:
        _handle_error("delete failed", exc)

    typer.echo(f"Deleted test {test_id}")


async def _delete_test(
    test_id: str,
) -> None:
    async with _service_context() as service:
        await service.delete_test(test_id)


# ============================================================================
# Target / benchmark configuration
# ============================================================================


@app.command("set-target")
def set_target(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
    target_id: str = typer.Argument(
        ...,
        help="Registered target identifier.",
    ),
) -> None:
    """Select the single target used by a test."""
    try:
        result = _run(
            _update_test(
                test_id,
                {"target_id": target_id},
            )
        )
    except (KeyError, ValueError) as exc:
        _handle_error("set-target failed", exc)

    typer.echo(
        f"Target set to {result['target_id']}"
    )
    typer.echo(
        f"Status: {result['configuration_status']}"
    )


@app.command("clear-target")
def clear_target(
    test_id: str = typer.Argument(...),
) -> None:
    """Clear the selected target."""
    try:
        result = _run(
            _update_test(
                test_id,
                {"target_id": None},
            )
        )
    except (KeyError, ValueError) as exc:
        _handle_error("clear-target failed", exc)

    typer.echo("Target cleared.")
    typer.echo(
        f"Status: {result['configuration_status']}"
    )


@app.command("set-benchmark")
def set_benchmark(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
    benchmark_id: str = typer.Argument(
        ...,
        help="Benchmark identifier.",
    ),
) -> None:
    """Select the single benchmark used by a test."""
    try:
        result = _run(
            _update_test(
                test_id,
                {"benchmark_id": benchmark_id},
            )
        )
    except (KeyError, ValueError) as exc:
        _handle_error("set-benchmark failed", exc)

    typer.echo(
        f"Benchmark set to {result['benchmark_id']}"
    )
    typer.echo(
        f"Status: {result['configuration_status']}"
    )


@app.command("clear-benchmark")
def clear_benchmark(
    test_id: str = typer.Argument(...),
) -> None:
    """Clear the selected benchmark."""
    try:
        result = _run(
            _update_test(
                test_id,
                {"benchmark_id": None},
            )
        )
    except (KeyError, ValueError) as exc:
        _handle_error("clear-benchmark failed", exc)

    typer.echo("Benchmark cleared.")
    typer.echo(
        f"Status: {result['configuration_status']}"
    )


async def _update_test(
    test_id: str,
    changes: dict[str, Any],
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.update_test(
            test_id,
            changes=changes,
        )


# ============================================================================
# Metrics
# ============================================================================


@app.command("metrics")
def show_metrics(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
) -> None:
    """Show available, applicable, and selected metrics."""
    try:
        result = _run(_show_metrics(test_id))
    except KeyError as exc:
        _handle_error("metrics lookup failed", exc)

    typer.echo(
        f"Mode: {result['mode']}"
    )

    for metric in result["metrics"]:
        selected = (
            "[x]"
            if metric["selected"]
            else "[ ]"
        )

        state = (
            ""
            if metric["applicable"]
            else (
                "  unavailable: "
                + (
                    metric["unavailable_reason"]
                    or "not applicable"
                )
            )
        )

        typer.echo(
            f"{selected} "
            f"{metric['metric_id']} "
            f"v{metric['version']}{state}"
        )

    for warning in result.get("warnings", []):
        typer.echo(
            f"warning: {warning}",
            err=True,
        )


async def _show_metrics(
    test_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.get_test_metrics(
            test_id
        )


@app.command("set-metrics")
def set_metrics(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
    metric_ids: list[str] = typer.Argument(
        ...,
        help="Metric IDs to select.",
    ),
) -> None:
    """Replace explicit metric selection for a test."""
    try:
        result = _run(
            _set_metrics(
                test_id,
                metric_ids,
            )
        )
    except (KeyError, ValueError) as exc:
        _handle_error("set-metrics failed", exc)

    typer.echo("Selected metrics:")
    for metric_id in result[
        "selected_metric_ids"
    ]:
        typer.echo(f"  {metric_id}")


async def _set_metrics(
    test_id: str,
    metric_ids: list[str],
) -> dict[str, Any]:
    async with _service_context() as service:
        current = await service.get_test_metrics(
            test_id
        )

        return await service.set_test_metrics(
            test_id,
            mode="EXPLICIT",
            selected_metrics=metric_ids,
            metric_parameters={
                metric["metric_id"]: dict(
                    metric.get(
                        "parameters",
                        {},
                    )
                )
                for metric in current["metrics"]
                if metric["metric_id"] in metric_ids
            },
            judge_config=current[
                "judge_config"
            ],
            retrieval_config=current[
                "retrieval_config"
            ],
        )


@app.command("select-all-metrics")
def select_all_metrics(
    test_id: str = typer.Argument(...),
) -> None:
    """Select all metrics applicable to the current test."""
    try:
        result = _run(
            _select_all_metrics(test_id)
        )
    except (KeyError, ValueError) as exc:
        _handle_error(
            "select-all-metrics failed",
            exc,
        )

    typer.echo(
        "Selected all applicable metrics "
        f"({len(result['selected_metric_ids'])})."
    )


async def _select_all_metrics(
    test_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return (
            await service.select_all_applicable_metrics(
                test_id
            )
        )


@app.command("import-yaml")
def import_yaml(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
    config: Path = typer.Argument(
        ...,
        exists=True,
        readable=True,
        dir_okay=False,
        help="Portable test/metric YAML file.",
    ),
) -> None:
    """Import test metric configuration from YAML."""
    try:
        result = _run(
            _import_yaml(
                test_id,
                config,
            )
        )
    except (KeyError, ValueError, OSError) as exc:
        _handle_error("import failed", exc)

    _echo_json(result)


async def _import_yaml(
    test_id: str,
    config: Path,
) -> dict[str, Any]:
    text = config.read_text(
        encoding="utf-8"
    )

    async with _service_context() as service:
        return await service.import_test_yaml(
            test_id,
            text,
        )


@app.command("export-yaml")
def export_yaml(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
    output: Path | None = typer.Option(
        None,
        "--output",
        "-o",
        help="Write YAML to a file instead of stdout.",
    ),
) -> None:
    """Export the current test configuration as YAML."""
    try:
        text = _run(
            _export_yaml(test_id)
        )
    except KeyError as exc:
        _handle_error("export failed", exc)

    if output is None:
        typer.echo(text)
        return

    output.write_text(
        text,
        encoding="utf-8",
    )
    typer.echo(
        f"Wrote configuration to {output}"
    )


async def _export_yaml(
    test_id: str,
) -> str:
    async with _service_context() as service:
        return await service.export_test_yaml(
            test_id
        )


# ============================================================================
# Validation / starting runs
# ============================================================================


@app.command("validate")
def validate_test(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
) -> None:
    """Validate whether a test is currently runnable."""
    try:
        result = _run(
            _validate_test(test_id)
        )
    except KeyError as exc:
        _handle_error("validation failed", exc)

    if result["valid"]:
        typer.echo("Test is ready.")
    else:
        typer.echo(
            "Test is not ready.",
            err=True,
        )

    for error in result["errors"]:
        typer.echo(
            f"error: {error}",
            err=True,
        )

    for warning in result["warnings"]:
        typer.echo(
            f"warning: {warning}",
            err=True,
        )

    typer.echo(
        "Resolved metrics: "
        + (
            ", ".join(
                result["resolved_metric_ids"]
            )
            or "-"
        )
    )

    if not result["valid"]:
        raise typer.Exit(code=1)


async def _validate_test(
    test_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.validate_test(
            test_id
        )


@app.command("start")
def start_run(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
) -> None:
    """Create and queue a run from the current saved test configuration."""
    try:
        result = _run(
            _start_run(test_id)
        )
    except (KeyError, ValueError, RuntimeError) as exc:
        _handle_error("start failed", exc)

    typer.echo(
        f"Run created: {result['run_id']}"
    )
    typer.echo(
        f"Status: {result['status']}"
    )
    typer.echo(
        f"Cases: {result['total_cases']}"
    )


async def _start_run(
    test_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.start_run(
            test_id
        )


@app.command("runs")
def list_test_runs(
    test_id: str = typer.Argument(
        ...,
        help="Test definition identifier.",
    ),
) -> None:
    """List runs created from a test."""
    try:
        runs = _run(
            _list_test_runs(test_id)
        )
    except KeyError as exc:
        _handle_error("runs lookup failed", exc)

    if not runs:
        typer.echo("No runs.")
        return

    for run in runs:
        typer.echo(
            f"{run['run_id']}  "
            f"{run['status']:<12}  "
            f"{run['complete_cases'] or 0}/"
            f"{run['total_cases'] or 0}"
        )


async def _list_test_runs(
    test_id: str,
) -> list[dict[str, Any]]:
    async with _service_context() as service:
        return await service.list_test_runs(
            test_id
        )


# ============================================================================
# Run inspection
# ============================================================================


@app.command("run")
def show_run(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
) -> None:
    """Show one evaluation run."""
    try:
        result = _run(
            _show_run(run_id)
        )
    except KeyError as exc:
        _handle_error("run lookup failed", exc)

    _echo_json(result)


async def _show_run(
    run_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        result = await service.get_run(run_id)

        if result is None:
            raise KeyError(
                f"run not found: {run_id}"
            )

        return result


@app.command("status")
def run_status(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
) -> None:
    """Show concise run progress."""
    try:
        result = _run(
            _run_status(run_id)
        )
    except KeyError as exc:
        _handle_error("status lookup failed", exc)

    typer.echo(f"Run: {result['run_id']}")
    typer.echo(f"Status: {result['status']}")

    if result.get("status_reason"):
        typer.echo(
            f"Reason: {result['status_reason']}"
        )

    typer.echo(
        "Progress: "
        f"{result['complete_cases'] + result['failed_cases']}/"
        f"{result['total_cases']} "
        f"({result['progress_percent']:.1f}%)"
    )

    typer.echo(
        f"  complete: {result['complete_cases']}"
    )
    typer.echo(
        f"  failed:   {result['failed_cases']}"
    )
    typer.echo(
        f"  running:  {result['running_cases']}"
    )
    typer.echo(
        f"  pending:  {result['pending_cases']}"
    )


async def _run_status(
    run_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.get_run_status(
            run_id
        )


@app.command("cases")
def list_run_cases(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
) -> None:
    """List case executions belonging to a run."""
    try:
        cases = _run(
            _list_run_cases(run_id)
        )
    except KeyError as exc:
        _handle_error("cases lookup failed", exc)

    if not cases:
        typer.echo("No case executions.")
        return

    for case in cases:
        typer.echo(
            f"{case['case_execution_id']}  "
            f"{case['status']:<12}  "
            f"{case['case_id']}  "
            f"attempts={case.get('attempt_count', 0)}"
        )


async def _list_run_cases(
    run_id: str,
) -> list[dict[str, Any]]:
    async with _service_context() as service:
        return await service.list_run_cases(
            run_id
        )


@app.command("attempts")
def list_case_attempts(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
    case_execution_id: str = typer.Argument(
        ...,
        help="Case execution identifier.",
    ),
) -> None:
    """List attempts for one logical case execution."""
    try:
        attempts = _run(
            _list_case_attempts(
                run_id,
                case_execution_id,
            )
        )
    except KeyError as exc:
        _handle_error("attempt lookup failed", exc)

    if not attempts:
        typer.echo("No attempts.")
        return

    for attempt in attempts:
        typer.echo(
            f"#{attempt['attempt_number']} "
            f"{attempt['status']:<12} "
            f"{attempt['attempt_id']} "
            f"request={attempt['request_id']}"
        )

        if attempt.get("error_summary"):
            typer.echo(
                f"  error: "
                f"{attempt['error_summary']}"
            )


async def _list_case_attempts(
    run_id: str,
    case_execution_id: str,
) -> list[dict[str, Any]]:
    async with _service_context() as service:
        return await service.list_case_attempts(
            run_id,
            case_execution_id,
        )


@app.command("events")
def list_run_events(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
) -> None:
    """List append-only lifecycle events for a run."""
    try:
        events = _run(
            _list_run_events(run_id)
        )
    except KeyError as exc:
        _handle_error("event lookup failed", exc)

    if not events:
        typer.echo("No run events.")
        return

    for event in events:
        typer.echo(
            f"{event['created_at']}  "
            f"{event['event_type']}"
        )

        if event["payload"]:
            typer.echo(
                "  "
                + json.dumps(
                    event["payload"],
                    default=str,
                    ensure_ascii=False,
                )
            )


async def _list_run_events(
    run_id: str,
) -> list[dict[str, Any]]:
    async with _service_context() as service:
        return await service.list_run_events(
            run_id
        )


@app.command("results")
def show_results(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
) -> None:
    """Show persisted metric results and aggregates."""
    try:
        result = _run(
            _show_results(run_id)
        )
    except KeyError as exc:
        _handle_error("results lookup failed", exc)

    _echo_json(result)


async def _show_results(
    run_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.get_run_results(
            run_id
        )


# ============================================================================
# Run lifecycle controls
# ============================================================================


@app.command("pause")
def pause_run(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
) -> None:
    """Request a graceful pause."""
    try:
        result = _run(
            _pause_run(run_id)
        )
    except (KeyError, RuntimeError) as exc:
        _handle_error("pause failed", exc)

    typer.echo(
        f"Run {run_id}: {result['status']}"
    )


async def _pause_run(
    run_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.pause_run(
            run_id
        )


@app.command("resume")
def resume_run(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
) -> None:
    """Resume a deliberately paused run."""
    try:
        result = _run(
            _resume_run(run_id)
        )
    except (KeyError, RuntimeError) as exc:
        _handle_error("resume failed", exc)

    typer.echo(
        f"Run {run_id}: {result['status']}"
    )


async def _resume_run(
    run_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.resume_run(
            run_id
        )


@app.command("recover")
def recover_run(
    run_id: str = typer.Argument(
        ...,
        help="Interrupted run identifier.",
    ),
) -> None:
    """Prepare an interrupted run for recovery."""
    try:
        result = _run(
            _recover_run(run_id)
        )
    except (KeyError, RuntimeError) as exc:
        _handle_error("recover failed", exc)

    typer.echo(
        f"Run {run_id}: {result['status']}"
    )


async def _recover_run(
    run_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.recover_run(
            run_id
        )


@app.command("cancel")
def cancel_run(
    run_id: str = typer.Argument(
        ...,
        help="Run identifier.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Skip confirmation.",
    ),
) -> None:
    """Cancel a nonterminal run."""
    if not yes:
        confirmed = typer.confirm(
            f"Cancel run {run_id}?"
        )
        if not confirmed:
            raise typer.Abort()

    try:
        result = _run(
            _cancel_run(run_id)
        )
    except (KeyError, RuntimeError) as exc:
        _handle_error("cancel failed", exc)

    typer.echo(
        f"Run {run_id}: {result['status']}"
    )


async def _cancel_run(
    run_id: str,
) -> dict[str, Any]:
    async with _service_context() as service:
        return await service.cancel_run(
            run_id
        )