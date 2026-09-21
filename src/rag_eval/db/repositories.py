"""Focused async repositories for durable application persistence."""

from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.models import (
    AggregateMetricResultRecord,
    ArtifactRecord,
    AttemptRecord,
    CaseExecutionRecord,
    ErrorRecordDB,
    MetricResultRecord,
    RunConfigRecord,
    RunRecord,
)
from rag_eval.models import (
    ArtifactRef,
    ErrorRecord,
    MetricResult,
)
from rag_eval.models.metrics import AggregateMetricResult


class PersistenceRepository:
    """Explicit database operations with caller-managed transaction scope."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to one caller-managed async session."""
        self._session = session


    # -------------------------------------------------------------------------
    # Runs
    # -------------------------------------------------------------------------

    async def create_run(
        self,
        run: RunRecord,
        canonical_config: Mapping[str, Any],
    ) -> RunRecord:
        """Persist a run and immutable canonical configuration identity."""
        config = RunConfigRecord(
            config_hash=run.config_hash,
            canonical_config=dict(canonical_config),
        )

        existing = await self._session.get(
            RunConfigRecord,
            run.config_hash,
        )

        if existing is None:
            self._session.add(config)
        elif existing.canonical_config != canonical_config:
            raise ValueError(
                "config_hash already exists with different "
                "canonical configuration"
            )

        self._session.add(run)
        await self._session.flush()

        return run

    async def get_run(
        self,
        run_id: str,
    ) -> RunRecord | None:
        """Retrieve one run by durable identity."""
        return await self._session.get(
            RunRecord,
            run_id,
        )

    async def update_run_status(
        self,
        run_id: str,
        status: str,
    ) -> RunRecord:
        """Update mutable runtime state without modifying configuration."""
        run = await self._session.get(
            RunRecord,
            run_id,
        )

        if run is None:
            raise KeyError(f"run not found: {run_id}")

        run.status = status

        await self._session.flush()
        return run

    async def get_run_config(
        self,
        run_id: str,
    ) -> RunConfigRecord | None:
        """Get canonical configuration associated with one run."""
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

    # -------------------------------------------------------------------------
    # Case execution / attempts
    # -------------------------------------------------------------------------

    async def create_case_execution(
        self,
        record: CaseExecutionRecord,
    ) -> CaseExecutionRecord:
        """Register one logical run/case execution."""
        self._session.add(record)
        await self._session.flush()

        return record

    async def list_case_executions(
        self,
        run_id: str,
    ) -> Sequence[CaseExecutionRecord]:
        """List case executions in deterministic identity order."""
        result = await self._session.scalars(
            select(CaseExecutionRecord)
            .where(CaseExecutionRecord.run_id == run_id)
            .order_by(CaseExecutionRecord.case_execution_id)
        )

        return result.all()

    async def create_attempt(
        self,
        record: AttemptRecord,
    ) -> AttemptRecord:
        """Append a new execution attempt."""
        self._session.add(record)
        await self._session.flush()

        return record

    async def update_attempt_status(
        self,
        attempt_id: str,
        status: str,
    ) -> AttemptRecord:
        """Update the lifecycle state of an existing attempt."""
        attempt = await self._session.get(
            AttemptRecord,
            attempt_id,
        )

        if attempt is None:
            raise KeyError(f"attempt not found: {attempt_id}")

        attempt.status = status

        await self._session.flush()
        return attempt

    async def list_attempts(
        self,
        case_execution_id: str,
    ) -> Sequence[AttemptRecord]:
        """List execution attempts by deterministic attempt number."""
        result = await self._session.scalars(
            select(AttemptRecord)
            .where(
                AttemptRecord.case_execution_id == case_execution_id
            )
            .order_by(AttemptRecord.attempt_number)
        )

        return result.all()


    # -------------------------------------------------------------------------
    # Artifacts
    # -------------------------------------------------------------------------

    async def persist_artifact(
        self,
        artifact: ArtifactRef,
        artifact_type: str,
    ) -> ArtifactRecord:
        """Persist artifact metadata without duplicating stored bytes."""
        record = await self._session.get(
            ArtifactRecord,
            artifact.artifact_id,
        )

        values = {
            "artifact_type": artifact_type,
            "uri": artifact.uri,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "content_type": artifact.content_type,
            "metadata_json": artifact.metadata,
        }

        if record is None:
            record = ArtifactRecord(
                artifact_id=artifact.artifact_id,
                **values,
            )
            self._session.add(record)
        else:
            for name, value in values.items():
                setattr(record, name, value)

        await self._session.flush()
        return record

    async def get_artifact(
        self,
        artifact_id: str,
    ) -> ArtifactRef | None:
        """Reload artifact metadata as a canonical reference."""
        record = await self._session.get(
            ArtifactRecord,
            artifact_id,
        )

        if record is None:
            return None

        return ArtifactRef(
            artifact_id=record.artifact_id,
            uri=record.uri,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            content_type=record.content_type,
            created_at=record.created_at,
            metadata=dict(record.metadata_json or {}),
        )

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    async def persist_metric(
        self,
        metric: MetricResult,
        case_execution_id: str | None = None,
    ) -> MetricResultRecord:
        """Persist a canonical metric result."""
        payload = metric.model_dump(mode="json")

        record = MetricResultRecord(
            metric_result_id=metric.metric_result_id,
            run_id=metric.run_id or "",
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
        """Persist one normalized structured error."""
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