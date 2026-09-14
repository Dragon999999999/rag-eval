"""Focused async repositories for the durable execution persistence boundary."""

import hashlib
import json
from collections.abc import Sequence

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
    TargetObservationRecord,
)
from rag_eval.models import ArtifactRef, ErrorRecord, MetricResult, TargetObservation


def _payload_hash(payload: dict[object, object]) -> str:
    """Hash canonical JSON payload content for durable integrity checks."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PersistenceRepository:
    """Explicit database operations; callers control short transaction scope."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to one caller-managed async session."""
        self._session = session

    async def create_run(
        self, run: RunRecord, canonical_config: dict[object, object]
    ) -> RunRecord:
        """Persist a run and immutable canonical configuration identity."""
        config = RunConfigRecord(
            config_hash=run.config_hash,
            canonical_config=canonical_config,
        )
        existing = await self._session.get(RunConfigRecord, run.config_hash)
        if existing is None:
            self._session.add(config)
        elif existing.canonical_config != canonical_config:
            raise ValueError(
                "config_hash already exists with different canonical configuration"
            )
        self._session.add(run)
        await self._session.flush()
        return run

    async def get_run(self, run_id: str) -> RunRecord | None:
        """Retrieve one run by durable identity."""
        return await self._session.get(RunRecord, run_id)

    async def update_run_status(self, run_id: str, status: str) -> RunRecord:
        """Update mutable runtime state without modifying configuration identity."""
        run = await self._session.get(RunRecord, run_id)
        if run is None:
            raise KeyError(f"run not found: {run_id}")
        run.status = status
        await self._session.flush()
        return run

    async def create_case_execution(
        self, record: CaseExecutionRecord
    ) -> CaseExecutionRecord:
        """Register one logical run/case execution."""
        self._session.add(record)
        await self._session.flush()
        return record

    async def list_case_executions(self, run_id: str) -> Sequence[CaseExecutionRecord]:
        """List a run's case executions in deterministic identity order."""
        result = await self._session.scalars(
            select(CaseExecutionRecord)
            .where(CaseExecutionRecord.run_id == run_id)
            .order_by(CaseExecutionRecord.case_execution_id)
        )
        return result.all()

    async def create_attempt(self, record: AttemptRecord) -> AttemptRecord:
        """Append a new attempt; callers must never reuse attempt identities."""
        self._session.add(record)
        await self._session.flush()
        return record

    async def update_attempt_status(
        self, attempt_id: str, status: str
    ) -> AttemptRecord:
        """Update the lifecycle state of an existing historical attempt."""
        attempt = await self._session.get(AttemptRecord, attempt_id)
        if attempt is None:
            raise KeyError(f"attempt not found: {attempt_id}")
        attempt.status = status
        await self._session.flush()
        return attempt

    async def list_attempts(self, case_execution_id: str) -> Sequence[AttemptRecord]:
        """List append-only attempts by their deterministic attempt number."""
        result = await self._session.scalars(
            select(AttemptRecord)
            .where(AttemptRecord.case_execution_id == case_execution_id)
            .order_by(AttemptRecord.attempt_number)
        )
        return result.all()

    async def persist_observation(
        self, observation: TargetObservation, case_execution_id: str, attempt_id: str
    ) -> TargetObservationRecord:
        """Validate and persist a normalized target observation JSONB payload."""
        payload = observation.model_dump(mode="json")
        record = TargetObservationRecord(
            observation_id=observation.observation_id,
            request_id=observation.request_id,
            case_execution_id=case_execution_id,
            attempt_id=attempt_id,
            normalization_version=observation.normalization_version,
            payload=payload,
            payload_hash=_payload_hash(payload),
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_observation(self, observation_id: str) -> TargetObservation | None:
        """Reload one persisted observation through canonical Pydantic validation."""
        record = await self._session.get(TargetObservationRecord, observation_id)
        return (
            None if record is None else TargetObservation.model_validate(record.payload)
        )

    async def persist_artifact(
        self, artifact: ArtifactRef, artifact_type: str
    ) -> ArtifactRecord:
        """Persist artifact metadata only; bytes remain in object storage."""
        record = ArtifactRecord(
            artifact_id=artifact.artifact_id,
            artifact_type=artifact_type,
            uri=artifact.uri,
            sha256=artifact.sha256,
            size_bytes=artifact.size_bytes,
            content_type=artifact.content_type,
            metadata_json=artifact.metadata,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def get_artifact(self, artifact_id: str) -> ArtifactRef | None:
        """Reload artifact metadata as a canonical reference."""
        record = await self._session.get(ArtifactRecord, artifact_id)
        if record is None:
            return None
        return ArtifactRef(
            artifact_id=record.artifact_id,
            uri=record.uri,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            content_type=record.content_type,
            created_at=record.created_at,
            metadata=record.metadata_json,
        )

    async def persist_metric(
        self, metric: MetricResult, case_execution_id: str | None = None
    ) -> MetricResultRecord:
        """Persist a canonical metric result, preserving null unavailable values."""
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

    async def persist_error(
        self, error: ErrorRecord, **relations: str | None
    ) -> ErrorRecordDB:
        """Persist one normalized structured error and its optional relationships."""
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
            raw_artifact_id=error.raw_artifact.artifact_id
            if error.raw_artifact
            else None,
            details=error.details,
        )
        self._session.add(record)
        await self._session.flush()
        return record

    async def persist_aggregate(
        self, record: AggregateMetricResultRecord
    ) -> AggregateMetricResultRecord:
        """Persist a precomputed aggregate without running aggregation logic."""
        self._session.add(record)
        await self._session.flush()
        return record
