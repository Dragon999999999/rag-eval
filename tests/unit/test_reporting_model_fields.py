"""Reporting reads fields actually persisted by the SQLAlchemy models."""

from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import cast

import pyarrow.parquet as pq
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.models import (
    AggregateMetricResultRecord,
    CaseExecutionRecord,
    ErrorRecordDB,
)
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import AggregateMetricResult, MetricStatus
from rag_eval.reporting.compare import RunComparator
from rag_eval.reporting.export import ExportService


def _aggregate(run_id: str, details: dict[str, int]) -> AggregateMetricResultRecord:
    """Create an aggregate with coverage stored in its JSON details."""
    return AggregateMetricResultRecord(
        aggregate_metric_result_id=f"aggregate-{run_id}",
        run_id=run_id,
        metric_id="answer.exact_match",
        metric_version="1",
        aggregation="mean",
        value=0.5,
        status="COMPUTED",
        details=details,
    )


@pytest.mark.anyio
async def test_aggregate_persistence_retains_coverage_counts() -> None:
    """The repository stores the canonical counts consumed by reporting."""

    class Session:
        """Record the aggregate added by the repository."""

        def __init__(self) -> None:
            self.record: AggregateMetricResultRecord | None = None

        def add(self, record: AggregateMetricResultRecord) -> None:
            self.record = record

        async def flush(self) -> None:
            pass

    session = Session()
    aggregate = AggregateMetricResult(
        run_id="run",
        metric_id="answer.exact_match",
        metric_version="1",
        aggregation="mean",
        value=0.5,
        status=MetricStatus.COMPUTED,
        sample_count=5,
        available_count=4,
        failed_count=1,
    )
    record = await PersistenceRepository(
        cast(AsyncSession, session)
    ).persist_aggregate(aggregate)
    assert record.details["sample_count"] == 5
    assert record.details["available_count"] == 4
    assert record.details["failed_count"] == 1


@pytest.mark.anyio
async def test_comparison_reads_coverage_from_persisted_details() -> None:
    """Comparison uses available coverage and leaves unknown totals unset."""

    class Repository:
        """Return two persisted runs and their aggregate records."""

        async def get_run(self, run_id: str) -> object:
            return SimpleNamespace(run_id=run_id)

        async def get_run_config(self, run_id: str) -> None:
            return None

        async def list_aggregates(
            self, run_id: str
        ) -> list[AggregateMetricResultRecord]:
            details = (
                {"available_count": 4, "sample_count": 5}
                if run_id == "a"
                else {"computed_count": 3}
            )
            return [_aggregate(run_id, details)]

    comparison = await RunComparator(
        cast(PersistenceRepository, Repository())
    ).compare_runs("a", "b")
    metric = comparison.comparisons[0]
    assert (metric.available_a, metric.total_a) == (4, 5)
    assert (metric.available_b, metric.total_b) == (3, None)


def test_export_summary_accepts_repository_sequences(tmp_path: Path) -> None:
    """Summary consumes a sequence and exports persisted aggregate coverage."""
    service = ExportService(
        cast(PersistenceRepository, SimpleNamespace()),
        tmp_path
    )
    case_executions = cast(
        Sequence[CaseExecutionRecord],
        (SimpleNamespace(status="COMPLETE"),),
    )

    summary = service._create_summary(
        SimpleNamespace(run_id="run", name="run", status="COMPLETE", target_id=None),
        case_executions,
        (_aggregate("run", {"available_count": 2, "sample_count": 3}),),
    )
    assert summary["case_counts"]["complete"] == 1
    assert summary["metrics"]["answer.exact_match.mean"]["sample_count"] == 3


@pytest.mark.anyio
async def test_error_export_uses_created_at_and_provider_payload(
    tmp_path: Path,
) -> None:
    """Error export reads the ORM timestamp and structured provider code."""
    created_at = datetime(2026, 9, 20, tzinfo=UTC)
    error = ErrorRecordDB(
        error_id="error-1",
        run_id="run",
        case_execution_id="execution-1",
        category="RATE_LIMIT",
        code="RATE_LIMITED",
        message="Slow down",
        retryable=True,
        provider={"code": "provider-rate-limit"},
    )
    error.created_at = created_at

    class Session:
        """Return one persisted error without a database connection."""

        async def execute(self, statement: object) -> object:
            return SimpleNamespace(scalars=lambda: SimpleNamespace(all=lambda: [error]))

    class Repository:
        """Expose only the records needed by error export."""

        _session = Session()

        async def list_case_executions(self, run_id: str) -> list[object]:
            return [SimpleNamespace(case_execution_id="execution-1", case_id="case-1")]

    path = tmp_path / "errors.parquet"
    assert await ExportService(
        cast(PersistenceRepository, Repository()),
        tmp_path,
    )._export_errors("run", path)
    row = pq.read_table(path).to_pylist()[0]
    assert row["case_id"] == "case-1"
    assert row["provider_code"] == "provider-rate-limit"
    assert row["timestamp"] == created_at.isoformat()
