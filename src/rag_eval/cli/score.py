"""CLI commands for scoring and reporting."""

import asyncio
from pathlib import Path
from typing import Any

import typer

from rag_eval.cli.benchmark import app as benchmark_app
from rag_eval.db import create_async_engine, create_session_factory
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.metrics import get_stage12_catalog
from rag_eval.metrics.service import ScoringService
from rag_eval.reporting import ExportService, ReportGenerator, RunComparator

app = typer.Typer(help="Score runs and generate reports.")

metrics_app = typer.Typer(help="Manage metrics and metric configurations.")
test_app = typer.Typer(help="Manage test definitions.")
run_app = typer.Typer(help="Manage evaluation runs.")
report_app = typer.Typer(help="Generate reports and exports.")

app.add_typer(benchmark_app, name="benchmark")
app.add_typer(metrics_app, name="metrics")
app.add_typer(test_app, name="test")
app.add_typer(run_app, name="run")
app.add_typer(report_app, name="report")


@app.command()
def score(
    run_id: str = typer.Argument(..., help="Run identifier to score"),
) -> None:
    """Score a persisted run with all registered metrics.

    Loads benchmark cases and target observations from database,
    executes metrics, and persists results.

    Does NOT call the evaluated target.
    """
    try:
        result = asyncio.run(_score_run(run_id))
    except KeyError as exc:
        typer.echo(f"scoring failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc
    except Exception as exc:
        typer.echo(f"scoring failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Scored run {run_id}:")
    typer.echo(f"  Cases: {result.scored_cases}/{result.total_cases}")
    typer.echo(f"  Metrics computed: {result.total_metrics_computed}")
    typer.echo(f"  Metrics unavailable: {result.total_metrics_unavailable}")
    typer.echo(f"  Metrics failed: {result.total_metrics_failed}")
    typer.echo(f"  Aggregates persisted: {result.aggregates_persisted}")


@app.command()
def report(
    run_id: str = typer.Argument(..., help="Run identifier to report on"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
) -> None:
    """Generate human-readable report from persisted metrics."""
    try:
        report_text = asyncio.run(_generate_report(run_id))
    except KeyError as exc:
        typer.echo(f"report generation failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(report_text)
        typer.echo(f"Report written to {output}")
    else:
        typer.echo(report_text)


@app.command()
def compare(
    run_a: str = typer.Argument(..., help="First run identifier"),
    run_b: str = typer.Argument(..., help="Second run identifier"),
    output: Path | None = typer.Option(
        None, "--output", "-o", help="Output file (default: stdout)"
    ),
) -> None:
    """Compare two runs across common metrics."""
    try:
        comparison_text = asyncio.run(_compare_runs(run_a, run_b))
    except KeyError as exc:
        typer.echo(f"comparison failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    if output:
        with open(output, "w", encoding="utf-8") as f:
            f.write(comparison_text)
        typer.echo(f"Comparison written to {output}")
    else:
        typer.echo(comparison_text)


@app.command()
def export(
    run_id: str = typer.Argument(..., help="Run identifier to export"),
    output_dir: Path = typer.Option(
        Path("./exports"), "--output", "-o", help="Export directory"
    ),
) -> None:
    """Export run to portable Parquet files."""
    try:
        exported = asyncio.run(_export_run(run_id, output_dir))
    except KeyError as exc:
        typer.echo(f"export failed: {exc}", err=True)
        raise typer.Exit(code=1) from exc

    typer.echo(f"Exported run {run_id} to {exported.export_path}")
    typer.echo("Files:")
    for f in exported.files:
        typer.echo(f"  - {f}")


async def _score_run(run_id: str):
    """Score a run."""
    from rag_eval.config import get_settings

    engine = create_async_engine(get_settings())
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session, session.begin():
            repository = PersistenceRepository(session)

            # Get Stage 12 catalog
            registry = get_stage12_catalog()

            # Score run
            service = ScoringService(registry, repository)
            result = await service.score_run(run_id)

            return result
    finally:
        await engine.dispose()


async def _generate_report(run_id: str) -> str:
    """Generate report text."""
    from rag_eval.config import get_settings

    engine = create_async_engine(get_settings())
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            repository = PersistenceRepository(session)

            generator = ReportGenerator(repository)
            report = await generator.generate_report(run_id)

            return _format_report(report)
    finally:
        await engine.dispose()


async def _compare_runs(run_a: str, run_b: str) -> str:
    """Compare two runs."""
    from rag_eval.config import get_settings

    engine = create_async_engine(get_settings())
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            repository = PersistenceRepository(session)

            comparator = RunComparator(repository)
            result = await comparator.compare_runs(run_a, run_b)

            return _format_comparison(result)
    finally:
        await engine.dispose()


async def _export_run(run_id: str, output_dir: Path):
    """Export run to Parquet."""
    from rag_eval.config import get_settings

    engine = create_async_engine(get_settings())
    try:
        session_factory = create_session_factory(engine)
        async with session_factory() as session:
            repository = PersistenceRepository(session)

            exporter = ExportService(repository, output_dir)
            exported = await exporter.export_run(run_id)

            return exported
    finally:
        await engine.dispose()


def _format_report(report: Any) -> str:
    """Format report as human-readable text."""
    lines = [
        "=" * 60,
        f"Run Report: {report.run_id}",
        "=" * 60,
        "",
        f"Name: {report.run_name}",
        f"Status: {report.status}",
        f"Target: {report.target_id or 'N/A'}",
        f"Config Hash: {report.config_hash or 'N/A'}",
        "",
        "Timing:",
        f"  Started: {report.started_at or 'N/A'}",
        f"  Finished: {report.finished_at or 'N/A'}",
        f"  Duration: {report.duration_seconds:.1f}s" if report.duration_seconds else "  Duration: N/A",
        "",
        "Case Summary:",
        f"  Total:     {report.total_cases}",
        f"  Complete:  {report.complete_cases}",
        f"  Failed:    {report.failed_cases}",
        f"  Pending:   {report.pending_cases}",
        "",
    ]

    # Add metric sections
    sections = [
        ("Answer Metrics", report.answer_metrics),
        ("Retrieval Metrics", report.retrieval_metrics),
        ("Citation Metrics", report.citation_metrics),
        ("Performance Metrics", report.performance_metrics),
        ("Usage Metrics", report.usage_metrics),
        ("Cost Metrics", report.cost_metrics),
        ("Reliability Metrics", report.reliability_metrics),
    ]

    for section_name, metrics in sections:
        if metrics:
            lines.append(f"{section_name}:")
            for key, value in sorted(metrics.items()):
                lines.append(f"  {key}: {value}")
            lines.append("")

    if not any(m for _, m in sections):
        lines.append("No metrics available.")
        lines.append("")

    return "\n".join(lines)


def _format_comparison(result: Any) -> str:
    """Format comparison as human-readable text."""
    lines = [
        "=" * 60,
        "Run Comparison",
        "=" * 60,
        "",
        f"Run A: {result.run_a_id}",
        f"Run B: {result.run_b_id}",
        "",
    ]

    # Warnings
    if result.warnings:
        lines.append("Compatibility Warnings:")
        for warning in result.warnings:
            lines.append(f"  ⚠ {warning}")
        lines.append("")

    if not result.compatible:
        lines.append("⚠ Runs may not be directly comparable")
        lines.append("")

    # Summary
    lines.append("Summary:")
    lines.append(f"  Improved:     {result.improved_count}")
    lines.append(f"  Regressed:    {result.regressed_count}")
    lines.append(f"  Unchanged:    {result.unchanged_count}")
    lines.append(f"  Inconclusive: {result.inconclusive_count}")
    lines.append("")

    # Detailed comparisons
    lines.append("Metric Comparisons:")
    lines.append("-" * 60)

    for comp in result.comparisons:
        # Format values
        val_a = f"{comp.value_a:.4f}" if isinstance(comp.value_a, (int, float)) else str(comp.value_a)
        val_b = f"{comp.value_b:.4f}" if isinstance(comp.value_b, (int, float)) else str(comp.value_b)

        # Format delta
        if comp.absolute_delta is not None:
            delta_str = f"{comp.absolute_delta:+.4f}"
            if comp.relative_delta is not None:
                delta_str += f" ({comp.relative_delta:+.1f}%)"
        else:
            delta_str = "N/A"

        # Assessment indicator
        indicator = {
            "improved": "↑",
            "regressed": "↓",
            "unchanged": "=",
            "inconclusive": "?",
        }.get(comp.assessment, "?")

        lines.append(
            f"{indicator} {comp.metric_id}.{comp.aggregation}"
        )
        lines.append(f"    A: {val_a} → B: {val_b} | Δ: {delta_str}")

    return "\n".join(lines)
