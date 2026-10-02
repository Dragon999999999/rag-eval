"""Tests for persisted run reporting calculations."""

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from rag_eval.reporting.summary import ReportGenerator

NOW = datetime(2026, 10, 2, 12, tzinfo=UTC)


class ReportRepository:
    """Minimal repository double for report duration tests."""

    async def get_run(self, run_id: str) -> SimpleNamespace:
        return SimpleNamespace(
            run_id=run_id,
            name="Evaluation",
            status="COMPLETE",
            target_id="target-1",
            config_hash="config-1",
            started_at=NOW,
            finished_at=NOW + timedelta(seconds=30),
        )

    async def list_case_executions(self, run_id: str) -> list[SimpleNamespace]:
        return [
            SimpleNamespace(
                run_id=run_id,
                case_execution_id="case-exec-1",
                status="COMPLETE",
            )
        ]

    async def list_attempts(self, case_execution_id: str) -> list[SimpleNamespace]:
        assert case_execution_id == "case-exec-1"
        return [
            SimpleNamespace(
                started_at=NOW,
                finished_at=NOW + timedelta(seconds=4),
            ),
            SimpleNamespace(
                started_at=NOW + timedelta(seconds=20),
                finished_at=NOW + timedelta(seconds=23),
            ),
        ]

    async def list_aggregates(self, run_id: str) -> list[SimpleNamespace]:
        return []


@pytest.mark.asyncio
async def test_report_duration_sums_attempts_instead_of_run_wall_time() -> None:
    """Retries count their own execution time without including idle gaps."""
    report = await ReportGenerator(ReportRepository()).generate_report("run-1")

    assert report.duration_seconds == 7.0
