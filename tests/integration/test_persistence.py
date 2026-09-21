"""PostgreSQL integration coverage for the Stage 4 persistence boundary."""

import asyncio
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from rag_eval.config import Settings
from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.models import (
    AttemptRecord,
    CaseExecutionRecord,
    RunRecord,
)
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.session import create_async_engine, create_session_factory
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import (
    AggregateMetricResult,
    Answer,
    ArtifactRef,
    BenchmarkCase,
    BenchmarkManifest,
    CorpusMode,
    ErrorCategory,
    ErrorRecord,
    FinishReason,
    MetricResult,
    MetricStatus,
    TargetObservation,
)


@pytest.mark.integration
def test_persistence_flow_preserves_history_and_canonical_payloads() -> None:
    """Persist a run through metric output using the real PostgreSQL service."""
    asyncio.run(_exercise_persistence_flow())


async def _exercise_persistence_flow() -> None:
    """Exercise repository relations, uniqueness, and rollback behavior."""
    engine = create_async_engine(Settings(_env_file=None))
    session_factory = create_session_factory(engine)
    suffix = uuid4().hex

    async with session_factory() as session:
        repository = PersistenceRepository(session)
        benchmark_repository = BenchmarkRepository(session)
        target_repository = TargetRepository(session)
        async with session.begin():
            run = RunRecord(
                run_id=f"run-{suffix}",
                name="integration",
                status="PENDING",
                config_hash="a" * 64,
            )
            await repository.create_run(
                run, {"version": "1", "run": {"name": "integration"}}
            )
            benchmark_id = f"benchmark-{suffix}"
            case_id = f"case-{suffix}"
            await benchmark_repository.create_benchmark(
                BenchmarkManifest(
                    benchmark_id=benchmark_id,
                    name="integration benchmark",
                    version="1",
                    corpus_mode=CorpusMode.DOCUMENTS,
                )
            )
            await benchmark_repository.create_case(
                benchmark_id,
                BenchmarkCase(case_id=case_id, query="Question"),
            )
            case_execution = await repository.create_case_execution(
                CaseExecutionRecord(
                    case_execution_id=f"case-execution-{suffix}",
                    run_id=run.run_id,
                    case_id=case_id,
                    status="PENDING",
                )
            )
            first = await repository.create_attempt(
                AttemptRecord(
                    attempt_id=f"attempt-1-{suffix}",
                    case_execution_id=case_execution.case_execution_id,
                    attempt_number=1,
                    request_id=f"request-1-{suffix}",
                    status="RUNNING",
                )
            )
            await repository.create_attempt(
                AttemptRecord(
                    attempt_id=f"attempt-2-{suffix}",
                    case_execution_id=case_execution.case_execution_id,
                    attempt_number=2,
                    request_id=f"request-2-{suffix}",
                    status="RETRYABLE_FAILURE",
                )
            )
            await repository.persist_artifact(
                ArtifactRef(artifact_id=f"artifact-{suffix}", uri="s3://bucket/raw"),
                "RAW_TARGET_RESPONSE",
            )
            observation = TargetObservation(
                observation_id=f"observation-{suffix}",
                case_id=f"case-{suffix}",
                request_id=first.request_id,
                answer=Answer(text="Answer", finish_reason=FinishReason.STOP),
                created_at=datetime.now(UTC),
            )
            await target_repository.persist_observation(
                observation, case_execution.case_execution_id, first.attempt_id
            )
            await repository.persist_metric(
                MetricResult(
                    metric_result_id=f"metric-{suffix}",
                    run_id=run.run_id,
                    case_id=f"case-{suffix}",
                    metric_id="groundedness",
                    metric_version="1",
                    status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                    reason="No final context was observed.",
                ),
                case_execution.case_execution_id,
            )
            await repository.persist_error(
                ErrorRecord(
                    error_id=f"error-{suffix}",
                    category=ErrorCategory.TIMEOUT,
                    code="TIMEOUT",
                    message="Target timed out.",
                    retryable=True,
                ),
                run_id=run.run_id,
                attempt_id=first.attempt_id,
            )
            await repository.persist_aggregate(
                AggregateMetricResult(
                    run_id=run.run_id,
                    metric_id="groundedness",
                    metric_version="1",
                    aggregation="mean",
                    value=None,
                    status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                    reason="No cases had final context.",
                    sample_count=0,
                    available_count=0,
                    failed_count=0,
                )
            )

        attempts = await repository.list_attempts(case_execution.case_execution_id)
        reloaded = await target_repository.get_observation(observation.observation_id)
        assert [attempt.attempt_number for attempt in attempts] == [1, 2]
        assert reloaded == observation

        async with session.begin_nested():
            session.add(
                AttemptRecord(
                    attempt_id=f"attempt-duplicate-{suffix}",
                    case_execution_id=case_execution.case_execution_id,
                    attempt_number=2,
                    request_id=f"request-duplicate-{suffix}",
                    status="RUNNING",
                )
            )
            with pytest.raises(IntegrityError):
                await session.flush()

    await engine.dispose()
