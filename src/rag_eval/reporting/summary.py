"""Run report generation from persisted metrics.

Generates human-readable summaries from:
- Run metadata
- Case execution statistics
- Aggregated metric results
- Reliability data

Critical: Uses persisted data only, no target calls.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_eval.db.test_repository import TestRepository


@dataclass(frozen=True)
class RunReport:
    """Human-readable run report."""

    run_id: str
    run_name: str
    status: str
    target_id: str | None = None
    config_hash: str | None = None

    # Case statistics
    total_cases: int = 0
    complete_cases: int = 0
    failed_cases: int = 0
    pending_cases: int = 0

    # Metric summaries
    # Key: (metric_id, aggregation) -> value
    answer_metrics: dict[str, Any] = field(default_factory=dict)
    retrieval_metrics: dict[str, Any] = field(default_factory=dict)
    citation_metrics: dict[str, Any] = field(default_factory=dict)
    performance_metrics: dict[str, Any] = field(default_factory=dict)
    usage_metrics: dict[str, Any] = field(default_factory=dict)
    cost_metrics: dict[str, Any] = field(default_factory=dict)
    reliability_metrics: dict[str, Any] = field(default_factory=dict)

    # Timing
    started_at: str | None = None
    finished_at: str | None = None
    duration_seconds: float | None = None


class ReportGenerator:
    """Generate reports from persisted run data."""

    def __init__(self, repository: TestRepository) -> None:
        """Initialize report generator.

        Args:
            repository: Repository for data access.
        """
        self._repository = repository

    async def generate_report(self, run_id: str) -> RunReport:
        """Generate a complete report for a run.

        Args:
            run_id: Run identifier.

        Returns:
            Complete run report.
        """
        # Load run metadata
        run = await self._repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")

        # Load case executions
        case_executions = await self._repository.list_case_executions(run_id)

        # Compute case statistics
        total = len(case_executions)
        complete = sum(1 for c in case_executions if c.status == "COMPLETE")
        failed = sum(1 for c in case_executions if c.status == "FAILED")
        pending = sum(1 for c in case_executions if c.status == "PENDING")

        # Load aggregates
        aggregates = await self._repository.list_aggregates(run_id)

        # Organize by metric family
        answer_metrics = {}
        retrieval_metrics = {}
        citation_metrics = {}
        performance_metrics = {}
        usage_metrics = {}
        cost_metrics = {}
        reliability_metrics = {}

        for agg in aggregates:
            metric_id = agg.metric_id
            agg_name = agg.aggregation
            value = agg.value

            # Route to appropriate category
            if metric_id.startswith("answer."):
                answer_metrics[f"{metric_id}.{agg_name}"] = self._format_value(value, metric_id)
            elif metric_id.startswith("retrieval."):
                retrieval_metrics[f"{metric_id}.{agg_name}"] = self._format_value(value, metric_id)
            elif metric_id.startswith("citation."):
                citation_metrics[f"{metric_id}.{agg_name}"] = self._format_value(value, metric_id)
            elif metric_id.startswith("performance."):
                performance_metrics[f"{metric_id}.{agg_name}"] = self._format_value(value, metric_id)
            elif metric_id.startswith("usage."):
                usage_metrics[f"{metric_id}.{agg_name}"] = self._format_value(value, metric_id)
            elif metric_id.startswith("cost."):
                cost_metrics[f"{metric_id}.{agg_name}"] = self._format_value(value, metric_id)
            elif metric_id.startswith("reliability."):
                reliability_metrics[f"{metric_id}.{agg_name}"] = self._format_value(value, metric_id)

        # Compute duration
        duration = None
        if run.started_at and run.finished_at:
            from datetime import timezone

            started = run.started_at.replace(tzinfo=timezone.utc) if run.started_at.tzinfo is None else run.started_at
            finished = run.finished_at.replace(tzinfo=timezone.utc) if run.finished_at.tzinfo is None else run.finished_at
            duration = (finished - started).total_seconds()

        return RunReport(
            run_id=run.run_id,
            run_name=run.name,
            status=run.status,
            target_id=run.target_id,
            config_hash=run.config_hash,
            total_cases=total,
            complete_cases=complete,
            failed_cases=failed,
            pending_cases=pending,
            answer_metrics=answer_metrics,
            retrieval_metrics=retrieval_metrics,
            citation_metrics=citation_metrics,
            performance_metrics=performance_metrics,
            usage_metrics=usage_metrics,
            cost_metrics=cost_metrics,
            reliability_metrics=reliability_metrics,
            started_at=_format_timestamp(run.started_at) if run.started_at else None,
            finished_at=_format_timestamp(run.finished_at) if run.finished_at else None,
            duration_seconds=duration,
        )

    def _format_value(self, value: Any, metric_id: str) -> str:
        """Format metric value for display.

        Preserves distinction between:
        - 0 (computed zero)
        - None/unavailable
        - FAILED
        """
        if value is None:
            return "N/A"
        elif isinstance(value, float):
            # Format based on metric type
            if "latency" in metric_id:
                return f"{value:.1f}ms"
            elif "cost" in metric_id:
                return f"${value:.6f}"
            elif "tokens" in metric_id:
                return f"{int(value):,}"
            elif value < 0.01:
                return f"{value:.6f}"
            else:
                return f"{value:.4f}"
        elif isinstance(value, int):
            return f"{value:,}"
        else:
            return str(value)


def _format_timestamp(dt: Any) -> str | None:
    """Format datetime for display."""
    if dt is None:
        return None
    return dt.isoformat()
