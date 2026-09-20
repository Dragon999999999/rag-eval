"""Tests for the Stage 9 benchmark execution engine."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest

from rag_eval.artifacts import ArtifactService, create_artifact_store
from rag_eval.config import get_settings, load_experiment_config
from rag_eval.db import (
    PersistenceRepository,
    create_async_engine,
    create_session_factory,
)
from rag_eval.db.models import RunRecord
from rag_eval.execution import BenchmarkExecutor
from rag_eval.models.enums import RunStatus


@pytest.mark.integration
def test_execution_engine_persists_case_results(tmp_path: Path) -> None:
    """Verify the execution engine persists case results durably."""
    asyncio.run(_execute_test_benchmark(tmp_path))


async def _execute_test_benchmark(tmp_path: Path) -> None:
    """Execute a minimal test benchmark with the example target."""
    from rag_eval.adapters import PythonTargetAdapter
    from rag_eval.datasets import NativeBenchmarkDataset
    from rag_eval.example_target import ExampleTarget

    engine = create_async_engine(get_settings())
    session_factory = create_session_factory(engine)
    suffix = uuid4().hex

    try:
        async with session_factory() as session:
            repository = PersistenceRepository(session)

            run_id = f"test-run-{suffix}"
            benchmark_id = f"test-benchmark-{suffix}"
            case_id = f"test-case-{suffix}"

            # ------------------------------------------------------------
            # Create a minimal native benchmark dataset
            # ------------------------------------------------------------

            case_file = tmp_path / "cases.jsonl"
            case_file.write_text(
                (
                    f'{{"case_id":"{case_id}",'
                    f'"query":"What is the capital of France?"}}\n'
                ),
                encoding="utf-8",
            )

            manifest_file = tmp_path / "manifest.yaml"
            manifest_file.write_text(
                "\n".join(
                    [
                        f"benchmark_id: {benchmark_id}",
                        "name: test benchmark",
                        "version: '1'",
                        "case_count: 1",
                        "cases: cases.jsonl",
                    ]
                ),
                encoding="utf-8",
            )

            dataset = NativeBenchmarkDataset(manifest_file)
            dataset.validate()

            # ------------------------------------------------------------
            # Persist initial run and evaluator-owned benchmark truth
            # ------------------------------------------------------------

            run = RunRecord(
                run_id=run_id,
                name="test-execution",
                status=RunStatus.PENDING.value,
                config_hash="a" * 64,
            )

            await repository.create_run(
                run,
                {
                    "version": "1",
                    "run": {
                        "name": "test-execution",
                    },
                },
            )

            for case in dataset.iter_cases():
                await repository.persist_benchmark_case(
                    benchmark_id,
                    case,
                )

            # Commit setup before starting execution.
            await session.commit()

            # ------------------------------------------------------------
            # Create target adapter and artifact service
            # ------------------------------------------------------------

            adapter = PythonTargetAdapter(ExampleTarget())

            store = create_artifact_store(get_settings())
            artifact_service = ArtifactService(
                store,
                repository,
            )

            # ------------------------------------------------------------
            # Load execution configuration
            # ------------------------------------------------------------

            config = load_experiment_config(
                Path("examples/basic.yaml")
            )

            # ------------------------------------------------------------
            # Create executor
            # ------------------------------------------------------------

            executor = BenchmarkExecutor(
                config,
                adapter,
                artifact_service,
                repository,
                session,
            )

            # ------------------------------------------------------------
            # Execute benchmark
            # ------------------------------------------------------------

            async with session.begin():
                result = await executor.execute(
                    run.run_id,
                    dataset,
                )

            # ------------------------------------------------------------
            # Verify execution summary
            # ------------------------------------------------------------

            assert result.total_cases == 1

            # ------------------------------------------------------------
            # Verify case execution persistence
            # ------------------------------------------------------------

            case_executions = await repository.list_case_executions(
                run.run_id
            )

            assert len(case_executions) > 0

            # Exactly one benchmark case was supplied.
            assert len(case_executions) == 1

            # ------------------------------------------------------------
            # Verify attempt persistence
            # ------------------------------------------------------------

            for case_execution in case_executions:
                attempts = await repository.list_attempts(
                    case_execution.case_execution_id
                )

                assert len(attempts) >= 1

    finally:
        await engine.dispose()


def test_request_identity_generation() -> None:
    """Verify request identity generation produces stable IDs."""
    from rag_eval.execution import RequestIdentityGenerator
    from rag_eval.models import QueryRequest
    
    generator = RequestIdentityGenerator()
    
    request = QueryRequest(
        request_id="",
        query="Test query",
        corpus_id="test-corpus",
    )
    
    identity = generator.generate(request, "test-attempt-1")
    
    assert identity.request_id
    assert identity.idempotency_key == "test-attempt-1"
    assert identity.canonical_request_hash
    assert len(identity.canonical_request_hash) == 64  # SHA-256 hex


def test_observation_normalizer_preserves_target_data() -> None:
    """Verify observation normalizer preserves target response data."""
    from rag_eval.execution import ObservationNormalizer
    from rag_eval.execution.timing import ClientTiming
    from rag_eval.models import Answer, QueryResponse, RequestStatus
    
    normalizer = ObservationNormalizer()
    
    response = QueryResponse(
        request_id="test-request",
        status=RequestStatus.COMPLETED,
        answer=Answer(text="Test answer"),
    )
    
    timing = ClientTiming()
    timing.start()
    timing.end()
    
    from rag_eval.models.common import ArtifactRef
    
    artifact = ArtifactRef(
        artifact_id="test-artifact",
        uri="s3://bucket/test",
    )
    
    observation = normalizer.normalize(
        response,
        case_id="test-case",
        request_id="test-request",
        timing=timing,
        raw_response_artifact=artifact,
    )
    
    assert observation.case_id == "test-case"
    assert observation.request_id == "test-request"
    assert observation.answer is not None
    assert observation.answer.text == "Test answer"
    assert observation.raw_response_artifact is not None


def test_client_timing_capture() -> None:
    """Verify client timing captures duration correctly."""
    import time
    
    from rag_eval.execution.timing import ClientTiming
    
    timing = ClientTiming()
    
    assert not timing.has_timing
    assert timing.duration_ms == 0.0
    
    timing.start()
    assert timing.started_at is not None
    assert not timing.has_timing
    
    time.sleep(0.05)  # Sleep 50ms
    
    timing.end()
    assert timing.finished_at is not None
    assert timing.has_timing
    assert timing.duration_ms >= 50.0  # At least 50ms
