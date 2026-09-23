"""Persistence repository for tests, runs, execution, and metric results.

The repository deliberately owns persistence only.  Validation of metric
applicability, target/benchmark readiness, run-state transition policy, metric
registry resolution, and recovery semantics belong to the service/execution
layers.

Transactions remain caller-managed.
"""

from collections.abc import Mapping, Sequence
from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.test_models import (
    AggregateMetricResultRecord,
    AttemptRecord,
    CaseExecutionRecord,
    ErrorRecordDB,
    MetricResultRecord,
    RunConfigRecord,
    RunEventRecord,
    RunRecord,
    StageExecutionRecord,
    TestDefinitionRecord,
    TestMetricSelectionRecord,
)
from rag_eval.models import ErrorRecord, MetricResult
from rag_eval.models.metrics import AggregateMetricResult


class TestRepository:
    """Persistence operations for test configuration and evaluation execution."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind the repository to one caller-managed async session."""
        self._session = session

    # -------------------------------------------------------------------------
    # Test definitions
    # -------------------------------------------------------------------------

    async def create_test(
        self,
        record: TestDefinitionRecord,
    ) -> TestDefinitionRecord:
        """Persist a new test definition, including an incomplete one."""
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_test(
        self,
        test_definition_id: str,
    ) -> TestDefinitionRecord | None:
        """Return one test definition."""
        return await self._session.get(
            TestDefinitionRecord,
            test_definition_id,
        )

    async def list_tests(
        self,
    ) -> Sequence[TestDefinitionRecord]:
        """List tests deterministically by creation time and identity."""
        result = await self._session.scalars(
            select(TestDefinitionRecord).order_by(
                TestDefinitionRecord.created_at,
                TestDefinitionRecord.test_definition_id,
            )
        )
        return result.all()

    async def update_test(
        self,
        test_definition_id: str,
        *,
        name: str | None = None,
        description: str | None = None,
        target_id: str | None = None,
        benchmark_id: str | None = None,
        configuration_status: str | None = None,
        metric_selection_mode: str | None = None,
        judge_config: Mapping[str, Any] | None = None,
        retrieval_config: Mapping[str, Any] | None = None,
        execution_config: Mapping[str, Any] | None = None,
        seed: int | None = None,
        tags: Sequence[str] | None = None,
        metadata: Mapping[str, Any] | None = None,
        definition_hash: str | None = None,
        clear_target: bool = False,
        clear_benchmark: bool = False,
        clear_seed: bool = False,
        clear_definition_hash: bool = False,
    ) -> TestDefinitionRecord:
        """Update mutable test configuration.

        Explicit clear flags distinguish "leave unchanged" from assigning NULL
        for nullable scalar fields.
        """
        record = await self._require_test(test_definition_id)

        if name is not None:
            record.name = name
        if description is not None:
            record.description = description

        if clear_target:
            record.target_id = None
        elif target_id is not None:
            record.target_id = target_id

        if clear_benchmark:
            record.benchmark_id = None
        elif benchmark_id is not None:
            record.benchmark_id = benchmark_id

        if configuration_status is not None:
            record.configuration_status = configuration_status
        if metric_selection_mode is not None:
            record.metric_selection_mode = metric_selection_mode
        if judge_config is not None:
            record.judge_config = dict(judge_config)
        if retrieval_config is not None:
            record.retrieval_config = dict(retrieval_config)
        if execution_config is not None:
            record.execution_config = dict(execution_config)

        if clear_seed:
            record.seed = None
        elif seed is not None:
            record.seed = seed

        if tags is not None:
            record.tags = list(tags)
        if metadata is not None:
            record.metadata_json = dict(metadata)

        if clear_definition_hash:
            record.definition_hash = None
        elif definition_hash is not None:
            record.definition_hash = definition_hash

        await self._session.flush()
        return record

    async def delete_test(
        self,
        test_definition_id: str,
    ) -> None:
        """Delete a test definition.

        Existing runs retain their immutable RunConfig snapshots.  The run's
        test_definition_id foreign key uses SET NULL.
        """
        record = await self._require_test(test_definition_id)
        await self._session.delete(record)
        await self._session.flush()

    # -------------------------------------------------------------------------
    # Test metric selections
    # -------------------------------------------------------------------------

    async def list_test_metric_selections(
        self,
        test_definition_id: str,
        *,
        enabled_only: bool = False,
    ) -> Sequence[TestMetricSelectionRecord]:
        """List the explicitly stored metric selections for one test."""
        statement = select(TestMetricSelectionRecord).where(
            TestMetricSelectionRecord.test_definition_id
            == test_definition_id
        )

        if enabled_only:
            statement = statement.where(
                TestMetricSelectionRecord.enabled.is_(True)
            )

        result = await self._session.scalars(
            statement.order_by(TestMetricSelectionRecord.metric_id)
        )
        return result.all()

    async def replace_test_metric_selections(
        self,
        test_definition_id: str,
        selections: Sequence[TestMetricSelectionRecord],
    ) -> Sequence[TestMetricSelectionRecord]:
        """Replace a test's explicit metric selection atomically in-session.

        Registry validation and ignoring/warning about unknown or inapplicable
        metric IDs should happen before this method is called.
        """
        await self._require_test(test_definition_id)

        await self._session.execute(
            delete(TestMetricSelectionRecord).where(
                TestMetricSelectionRecord.test_definition_id
                == test_definition_id
            )
        )

        for selection in selections:
            if selection.test_definition_id != test_definition_id:
                raise ValueError(
                    "metric selection test_definition_id does not match "
                    f"'{test_definition_id}'"
                )
            self._session.add(selection)

        await self._session.flush()

        return await self.list_test_metric_selections(
            test_definition_id
        )

    async def clear_test_metric_selections(
        self,
        test_definition_id: str,
    ) -> None:
        """Remove all explicitly stored metric selections for a test."""
        await self._require_test(test_definition_id)

        await self._session.execute(
            delete(TestMetricSelectionRecord).where(
                TestMetricSelectionRecord.test_definition_id
                == test_definition_id
            )
        )
        await self._session.flush()

    # -------------------------------------------------------------------------
    # Runs / immutable snapshots
    # -------------------------------------------------------------------------

    async def create_run(
        self,
        run: RunRecord,
        canonical_config: Mapping[str, Any],
    ) -> RunRecord:
        """Persist a run and its immutable canonical configuration snapshot."""
        snapshot = RunConfigRecord(
            config_hash=run.config_hash,
            canonical_config=dict(canonical_config),
        )

        existing = await self._session.get(
            RunConfigRecord,
            run.config_hash,
        )

        if existing is None:
            self._session.add(snapshot)
        elif existing.canonical_config != dict(canonical_config):
            raise ValueError(
                "config_hash already exists with a different "
                "canonical configuration"
            )

        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(
        self,
        run_id: str,
    ) -> RunRecord | None:
        """Return one evaluation run."""
        return await self._session.get(
            RunRecord,
            run_id,
        )

    async def list_runs(
        self,
        *,
        test_definition_id: str | None = None,
        statuses: Sequence[str] | None = None,
    ) -> Sequence[RunRecord]:
        """List runs with optional test/status filtering."""
        statement = select(RunRecord)

        if test_definition_id is not None:
            statement = statement.where(
                RunRecord.test_definition_id == test_definition_id
            )

        if statuses:
            statement = statement.where(
                RunRecord.status.in_(list(statuses))
            )

        result = await self._session.scalars(
            statement.order_by(
                RunRecord.created_at.desc(),
                RunRecord.run_id,
            )
        )
        return result.all()

    async def get_run_config(
        self,
        run_id: str,
    ) -> RunConfigRecord | None:
        """Return the immutable canonical snapshot associated with a run."""
        run = await self._session.get(
            RunRecord,
            run_id,
        )

        if run is None:
            return None

        return await self._session.get(
            RunConfigRecord,
            run.config_hash,
        )

    async def update_run_lifecycle(
        self,
        run_id: str,
        *,
        status: str | None = None,
        status_reason: str | None = None,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        paused_at: datetime | None = None,
        interrupted_at: datetime | None = None,
        clear_status_reason: bool = False,
        clear_finished_at: bool = False,
        clear_paused_at: bool = False,
        clear_interrupted_at: bool = False,
    ) -> RunRecord:
        """Update mutable run lifecycle state.

        Transition legality is intentionally enforced by the service layer.
        """
        run = await self._require_run(run_id)

        if status is not None:
            run.status = status

        if clear_status_reason:
            run.status_reason = None
        elif status_reason is not None:
            run.status_reason = status_reason

        if started_at is not None:
            run.started_at = started_at

        if clear_finished_at:
            run.finished_at = None
        elif finished_at is not None:
            run.finished_at = finished_at

        if clear_paused_at:
            run.paused_at = None
        elif paused_at is not None:
            run.paused_at = paused_at

        if clear_interrupted_at:
            run.interrupted_at = None
        elif interrupted_at is not None:
            run.interrupted_at = interrupted_at

        await self._session.flush()
        return run

    async def append_run_event(
        self,
        event: RunEventRecord,
    ) -> RunEventRecord:
        """Append one immutable run lifecycle/audit event."""
        await self._require_run(event.run_id)
        self._session.add(event)
        await self._session.flush()
        return event

    async def list_run_events(
        self,
        run_id: str,
    ) -> Sequence[RunEventRecord]:
        """List lifecycle events for a run in creation order."""
        result = await self._session.scalars(
            select(RunEventRecord)
            .where(RunEventRecord.run_id == run_id)
            .order_by(
                RunEventRecord.created_at,
                RunEventRecord.run_event_id,
            )
        )
        return result.all()

    # -------------------------------------------------------------------------
    # Case execution
    # -------------------------------------------------------------------------

    async def create_case_execution(
        self,
        record: CaseExecutionRecord,
    ) -> CaseExecutionRecord:
        """Register one logical run/case execution."""
        await self._require_run(record.run_id)
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_case_execution(
        self,
        case_execution_id: str,
    ) -> CaseExecutionRecord | None:
        """Return one case execution."""
        return await self._session.get(
            CaseExecutionRecord,
            case_execution_id,
        )

    async def list_case_executions(
        self,
        run_id: str,
        *,
        statuses: Sequence[str] | None = None,
    ) -> Sequence[CaseExecutionRecord]:
        """List case executions, optionally restricted by lifecycle state."""
        statement = select(CaseExecutionRecord).where(
            CaseExecutionRecord.run_id == run_id
        )

        if statuses:
            statement = statement.where(
                CaseExecutionRecord.status.in_(list(statuses))
            )

        result = await self._session.scalars(
            statement.order_by(CaseExecutionRecord.case_execution_id)
        )
        return result.all()

    async def update_case_execution_status(
        self,
        case_execution_id: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        clear_finished_at: bool = False,
    ) -> CaseExecutionRecord:
        """Update one logical case execution lifecycle state."""
        record = await self._require_case_execution(
            case_execution_id
        )

        record.status = status

        if started_at is not None:
            record.started_at = started_at

        if clear_finished_at:
            record.finished_at = None
        elif finished_at is not None:
            record.finished_at = finished_at

        await self._session.flush()
        return record

    async def get_run_case_counts(
        self,
        run_id: str,
    ) -> dict[str, int]:
        """Return case counts grouped by status for lightweight progress APIs."""
        result = await self._session.execute(
            select(
                CaseExecutionRecord.status,
                func.count(CaseExecutionRecord.case_execution_id),
            )
            .where(CaseExecutionRecord.run_id == run_id)
            .group_by(CaseExecutionRecord.status)
        )

        return {
            str(status): int(count)
            for status, count in result.all()
        }

    # -------------------------------------------------------------------------
    # Attempts / recovery
    # -------------------------------------------------------------------------

    async def create_attempt(
        self,
        record: AttemptRecord,
    ) -> AttemptRecord:
        """Append a new execution attempt."""
        await self._require_case_execution(
            record.case_execution_id
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_attempt(
        self,
        attempt_id: str,
    ) -> AttemptRecord | None:
        """Return one attempt."""
        return await self._session.get(
            AttemptRecord,
            attempt_id,
        )

    async def list_attempts(
        self,
        case_execution_id: str,
    ) -> Sequence[AttemptRecord]:
        """List execution attempts in attempt-number order."""
        result = await self._session.scalars(
            select(AttemptRecord)
            .where(
                AttemptRecord.case_execution_id == case_execution_id
            )
            .order_by(AttemptRecord.attempt_number)
        )
        return result.all()

    async def get_latest_attempt(
        self,
        case_execution_id: str,
    ) -> AttemptRecord | None:
        """Return the most recent attempt for recovery/retry decisions."""
        return await self._session.scalar(
            select(AttemptRecord)
            .where(
                AttemptRecord.case_execution_id == case_execution_id
            )
            .order_by(AttemptRecord.attempt_number.desc())
            .limit(1)
        )

    async def update_attempt_status(
        self,
        attempt_id: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
        retryable: bool | None = None,
        error_summary: str | None = None,
        clear_finished_at: bool = False,
        clear_error_summary: bool = False,
    ) -> AttemptRecord:
        """Update lifecycle information for an existing attempt."""
        attempt = await self._require_attempt(attempt_id)

        attempt.status = status

        if started_at is not None:
            attempt.started_at = started_at

        if clear_finished_at:
            attempt.finished_at = None
        elif finished_at is not None:
            attempt.finished_at = finished_at

        if retryable is not None:
            attempt.retryable = retryable

        if clear_error_summary:
            attempt.error_summary = None
        elif error_summary is not None:
            attempt.error_summary = error_summary

        await self._session.flush()
        return attempt

    # -------------------------------------------------------------------------
    # Optional stage execution
    # -------------------------------------------------------------------------

    async def create_stage_execution(
        self,
        record: StageExecutionRecord,
    ) -> StageExecutionRecord:
        """Persist one optional target-operation stage execution."""
        await self._require_attempt(record.attempt_id)
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_stage_executions(
        self,
        attempt_id: str,
    ) -> Sequence[StageExecutionRecord]:
        """List stages belonging to one attempt."""
        result = await self._session.scalars(
            select(StageExecutionRecord)
            .where(StageExecutionRecord.attempt_id == attempt_id)
            .order_by(
                StageExecutionRecord.created_at,
                StageExecutionRecord.stage_execution_id,
            )
        )
        return result.all()

    async def update_stage_execution_status(
        self,
        stage_execution_id: str,
        status: str,
        *,
        started_at: datetime | None = None,
        finished_at: datetime | None = None,
    ) -> StageExecutionRecord:
        """Update lifecycle timing for one execution stage."""
        record = await self._session.get(
            StageExecutionRecord,
            stage_execution_id,
        )

        if record is None:
            raise KeyError(
                f"stage execution not found: {stage_execution_id}"
            )

        record.status = status

        if started_at is not None:
            record.started_at = started_at
        if finished_at is not None:
            record.finished_at = finished_at

        await self._session.flush()
        return record

    # -------------------------------------------------------------------------
    # Metric results
    # -------------------------------------------------------------------------

    async def persist_metric(
        self,
        metric: MetricResult,
        case_execution_id: str | None = None,
    ) -> MetricResultRecord:
        """Persist a canonical individual metric result."""
        if not metric.run_id:
            raise ValueError(
                "metric.run_id is required for durable metric persistence"
            )

        payload = metric.model_dump(mode="json")

        record = MetricResultRecord(
            metric_result_id=metric.metric_result_id,
            run_id=metric.run_id,
            case_execution_id=case_execution_id,
            case_id=metric.case_id,
            metric_id=metric.metric_id,
            metric_version=metric.metric_version,
            value=metric.value,
            status=metric.status.value,
            reason=metric.reason,
            details=metric.details,
            payload=payload,
        )

        self._session.add(record)
        await self._session.flush()
        return record

    async def list_metric_results(
        self,
        run_id: str,
    ) -> Sequence[MetricResultRecord]:
        """List all individual metric results for a run."""
        result = await self._session.scalars(
            select(MetricResultRecord)
            .where(MetricResultRecord.run_id == run_id)
            .order_by(
                MetricResultRecord.case_id,
                MetricResultRecord.metric_id,
            )
        )
        return result.all()

    async def persist_aggregate(
        self,
        aggregate: AggregateMetricResult,
    ) -> AggregateMetricResultRecord:
        """Persist a canonical run-level aggregate metric."""
        record = AggregateMetricResultRecord(
            aggregate_metric_result_id=(
                f"agr-{aggregate.run_id}-"
                f"{aggregate.metric_id}-"
                f"{aggregate.aggregation}-"
                f"{aggregate.metric_version}"
            ),
            run_id=aggregate.run_id,
            metric_id=aggregate.metric_id,
            metric_version=aggregate.metric_version,
            aggregation=aggregate.aggregation,
            value=aggregate.value,
            status=aggregate.status.value,
            reason=aggregate.reason,
            details={
                **aggregate.distribution,
                "sample_count": aggregate.sample_count,
                "available_count": aggregate.available_count,
                "failed_count": aggregate.failed_count,
            },
        )

        self._session.add(record)
        await self._session.flush()
        return record

    async def list_aggregates(
        self,
        run_id: str,
    ) -> Sequence[AggregateMetricResultRecord]:
        """List all aggregate metric results for a run."""
        result = await self._session.scalars(
            select(AggregateMetricResultRecord)
            .where(
                AggregateMetricResultRecord.run_id == run_id
            )
            .order_by(
                AggregateMetricResultRecord.metric_id,
                AggregateMetricResultRecord.aggregation,
            )
        )
        return result.all()

    # -------------------------------------------------------------------------
    # Errors
    # -------------------------------------------------------------------------

    async def persist_error(
        self,
        error: ErrorRecord,
        **relations: str | None,
    ) -> ErrorRecordDB:
        """Persist one normalized execution error."""
        record = ErrorRecordDB(
            error_id=error.error_id,
            run_id=relations.get("run_id"),
            case_execution_id=relations.get("case_execution_id"),
            attempt_id=relations.get("attempt_id"),
            category=error.category.value,
            code=error.code,
            message=error.message,
            stage=error.stage,
            retryable=error.retryable,
            retry_after_ms=error.retry_after_ms,
            http_status=error.http_status,
            provider=error.provider,
            raw_artifact_id=(
                error.raw_artifact.artifact_id
                if error.raw_artifact is not None
                else None
            ),
            details=error.details,
        )

        self._session.add(record)
        await self._session.flush()
        return record

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _require_test(
        self,
        test_definition_id: str,
    ) -> TestDefinitionRecord:
        record = await self._session.get(
            TestDefinitionRecord,
            test_definition_id,
        )
        if record is None:
            raise KeyError(
                f"test definition not found: {test_definition_id}"
            )
        return record

    async def _require_run(
        self,
        run_id: str,
    ) -> RunRecord:
        record = await self._session.get(
            RunRecord,
            run_id,
        )
        if record is None:
            raise KeyError(f"run not found: {run_id}")
        return record

    async def _require_case_execution(
        self,
        case_execution_id: str,
    ) -> CaseExecutionRecord:
        record = await self._session.get(
            CaseExecutionRecord,
            case_execution_id,
        )
        if record is None:
            raise KeyError(
                f"case execution not found: {case_execution_id}"
            )
        return record

    async def _require_attempt(
        self,
        attempt_id: str,
    ) -> AttemptRecord:
        record = await self._session.get(
            AttemptRecord,
            attempt_id,
        )
        if record is None:
            raise KeyError(f"attempt not found: {attempt_id}")
        return record
