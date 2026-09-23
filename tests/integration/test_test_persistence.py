"""PostgreSQL integration coverage for the refactored test/run repository."""

import asyncio
from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError

from rag_eval.config import Settings
from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.session import create_async_engine, create_session_factory
from rag_eval.db.test_models import (
    AttemptRecord,
    CaseExecutionRecord,
    RunEventRecord,
    RunRecord,
    TestDefinitionRecord,
    TestMetricSelectionRecord,
)
from rag_eval.db.test_repository import TestRepository
from rag_eval.models import (
    AggregateMetricResult,
    BenchmarkCase,
    BenchmarkManifest,
    CorpusMode,
    MetricResult,
    MetricStatus,
)

# These production classes begin with ``Test`` but are not pytest test classes.
for _production_class in (
    TestDefinitionRecord,
    TestMetricSelectionRecord,
    TestRepository,
):
    _production_class.__test__ = False


@pytest.mark.integration
def test_refactored_test_run_persistence_preserves_history() -> None:
    """Persist test-owned selections, snapshots, retries, and result records."""
    asyncio.run(_exercise_test_persistence())


async def _exercise_test_persistence() -> None:
    """Exercise relational constraints and immutable run configuration state."""
    engine = create_async_engine(Settings(_env_file=None))
    session_factory = create_session_factory(engine)
    suffix = uuid4().hex

    async with session_factory() as session:
        repository = TestRepository(session)
        benchmark_repository = BenchmarkRepository(session)
        async with session.begin():
            test_id = f"test-{suffix}"
            benchmark_id = f"benchmark-{suffix}"
            case_id = f"case-{suffix}"
            await repository.create_test(
                TestDefinitionRecord(
                    test_definition_id=test_id,
                    name="integration",
                    configuration_status="READY",
                    metric_selection_mode="EXPLICIT",
                    target_id=None,
                    benchmark_id=benchmark_id,
                    judge_config={},
                    retrieval_config={},
                    execution_config={},
                    tags=[],
                    metadata_json={},
                )
            )
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
            await repository.replace_test_metric_selections(
                test_id,
                [
                    TestMetricSelectionRecord(
                        test_metric_selection_id=f"selection-{suffix}",
                        test_definition_id=test_id,
                        metric_id="exact_match",
                        metric_version="1",
                        parameters={"normalize": True},
                        enabled=True,
                    )
                ],
            )

            run = RunRecord(
                run_id=f"run-{suffix}",
                name="integration",
                status="PENDING",
                config_hash="a" * 64,
                target_id=None,
                benchmark_id=benchmark_id,
                test_definition_id=test_id,
                status_reason="queued",
                tags=[],
                metadata_json={},
            )
            snapshot = {
                "test_definition_id": test_id,
                "test_definition_hash": None,
                "target": {"target_id": None, "config_version": None},
                "benchmark": {"benchmark_id": benchmark_id, "version": "1"},
                "metrics": {"resolved": [{"metric_id": "exact_match", "version": "1"}]},
            }
            await repository.create_run(run, snapshot)
            stored_snapshot = await repository.get_run_config(run.run_id)
            assert stored_snapshot is not None
            assert stored_snapshot.canonical_config == snapshot

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
                    status="COMPLETED",
                )
            )
            await repository.create_attempt(
                AttemptRecord(
                    attempt_id=f"attempt-2-{suffix}",
                    case_execution_id=case_execution.case_execution_id,
                    attempt_number=2,
                    request_id=f"request-2-{suffix}",
                    status="RETRYABLE_FAILURE",
                    retryable=True,
                    error_summary="timeout",
                )
            )
            await repository.append_run_event(
                RunEventRecord(
                    run_event_id=f"event-{suffix}",
                    run_id=run.run_id,
                    event_type="RUN_CREATED",
                    payload={"case_count": 1},
                )
            )
            await repository.persist_metric(
                MetricResult(
                    metric_result_id=f"metric-{suffix}",
                    run_id=run.run_id,
                    case_id=case_id,
                    metric_id="exact_match",
                    metric_version="1",
                    status=MetricStatus.COMPUTED,
                    value=1.0,
                ),
                case_execution.case_execution_id,
            )
            await repository.persist_aggregate(
                AggregateMetricResult(
                    run_id=run.run_id,
                    metric_id="exact_match",
                    metric_version="1",
                    aggregation="mean",
                    value=1.0,
                    status=MetricStatus.COMPUTED,
                    sample_count=1,
                    available_count=1,
                    failed_count=0,
                )
            )

        assert [
            attempt.attempt_number
            for attempt in await repository.list_attempts(
                case_execution.case_execution_id
            )
        ] == [1, 2]
        assert (
            await repository.get_latest_attempt(case_execution.case_execution_id)
        ).attempt_id == first.attempt_id
        assert [
            event.event_type for event in await repository.list_run_events(run.run_id)
        ] == ["RUN_CREATED"]
        assert len(await repository.list_metric_results(run.run_id)) == 1
        assert len(await repository.list_aggregates(run.run_id)) == 1

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
