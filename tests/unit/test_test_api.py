"""Tests for the refactored test/run API boundary and schemas."""

from datetime import UTC, datetime

import pytest
from fastapi import BackgroundTasks, HTTPException

from rag_eval.api import test as test_api
from rag_eval.api.test_schemas import (
    TestCreate,
    TestDetail,
    TestMetricSelectionUpdate,
    TestUpdate,
)
from rag_eval.services.test_service import RetryFailedCasesResult

# These Pydantic schemas are API models, not pytest test classes.
for _api_model in (TestCreate, TestDetail, TestMetricSelectionUpdate, TestUpdate):
    _api_model.__test__ = False

NOW = datetime(2026, 9, 23, tzinfo=UTC)


def test_test_schemas_use_embedded_metric_and_api_field_names() -> None:
    """Presentation schemas expose metadata and current test configuration."""
    create = TestCreate(name="test", metadata={"owner": "qa"})
    assert create.metadata == {"owner": "qa"}
    update = TestUpdate(target_id=None, benchmark_id=None, seed=None)
    assert update.model_dump(exclude_unset=True) == {
        "target_id": None,
        "benchmark_id": None,
        "seed": None,
    }
    selection = TestMetricSelectionUpdate(
        mode="EXPLICIT",
        selected_metrics=["metric.answer"],
        metric_parameters={"metric.answer": {"threshold": 0.8}},
        judge_config={"provider": "local"},
        retrieval_config={"top_k": 5},
    )
    assert selection.metric_parameters["metric.answer"] == {"threshold": 0.8}

    detail = TestDetail(
        test_definition_id="test-1",
        name="test",
        description=None,
        configuration_status="INCOMPLETE",
        target_id=None,
        benchmark_id=None,
        metric_selection_mode="EXPLICIT",
        judge_config={},
        retrieval_config={},
        execution_config={},
        seed=None,
        tags=[],
        metadata={"owner": "qa"},
        definition_hash=None,
        created_at=NOW,
        updated_at=NOW,
    )
    assert detail.metadata == {"owner": "qa"}
    assert detail.definition_hash is None


@pytest.mark.asyncio
async def test_create_test_endpoint_maps_service_validation_and_returns_detail() -> (
    None
):
    """Create accepts only a name and maps service errors to HTTP 400."""

    class Service:
        async def create_test(self, **kwargs: object) -> dict[str, object]:
            assert kwargs["name"] == "test"
            return {
                "test_definition_id": "test-1",
                "name": "test",
                "description": None,
                "configuration_status": "INCOMPLETE",
                "target_id": None,
                "benchmark_id": None,
                "metric_selection_mode": "EXPLICIT",
                "judge_config": {},
                "retrieval_config": {},
                "execution_config": {},
                "seed": None,
                "tags": [],
                "metadata": {"owner": "qa"},
                "definition_hash": None,
                "created_at": NOW,
                "updated_at": NOW,
            }

    detail = await test_api.create_test(
        TestCreate(name="test", metadata={"owner": "qa"}), Service()
    )
    assert detail.test_definition_id == "test-1"
    assert detail.metadata == {"owner": "qa"}

    class InvalidService:
        async def create_test(self, **kwargs: object) -> dict[str, object]:
            raise ValueError("test name must not be empty")

    with pytest.raises(HTTPException) as error:
        await test_api.create_test(TestCreate(name="test"), InvalidService())
    assert error.value.status_code == 400


@pytest.mark.asyncio
async def test_test_api_maps_missing_and_invalid_metric_requests() -> None:
    """Metric endpoints preserve not-found and validation status semantics."""

    class MissingService:
        async def get_test_metrics(self, test_id: str) -> dict[str, object]:
            raise KeyError(test_id)

    with pytest.raises(HTTPException) as missing:
        await test_api.get_test_metrics("missing", MissingService())
    assert missing.value.status_code == 404

    class InvalidService:
        async def set_test_metrics(
            self, *args: object, **kwargs: object
        ) -> dict[str, object]:
            raise ValueError("unknown metrics")

    request = TestMetricSelectionUpdate(selected_metrics=["unknown"])
    with pytest.raises(HTTPException) as invalid:
        await test_api.set_test_metrics("test-1", request, InvalidService())
    assert invalid.value.status_code == 422


@pytest.mark.asyncio
async def test_run_api_maps_not_ready_and_missing_runs() -> None:
    """Run endpoints expose domain failures without leaking implementation details."""

    class Service:
        async def start_run(self, test_id: str) -> dict[str, object]:
            raise ValueError("test is not ready")

        async def get_run(self, run_id: str) -> None:
            return None

    class Session:
        async def rollback(self) -> None:
            return None

    with pytest.raises(HTTPException) as invalid:
        await test_api.start_test_run("test-1", Service(), Session(), BackgroundTasks())
    assert invalid.value.status_code == 422

    with pytest.raises(HTTPException) as missing:
        await test_api.get_run("missing", Service())
    assert missing.value.status_code == 404


@pytest.mark.asyncio
async def test_start_run_queues_execution_after_run_creation() -> None:
    """A successful run request hands the committed run to execution work."""

    executed: list[str] = []

    class Service:
        async def start_run(self, test_id: str) -> dict[str, object]:
            assert test_id == "test-1"
            return {
                "run_id": "run-1",
                "name": "test",
                "status": "PENDING",
                "status_reason": None,
                "config_hash": "hash",
                "target_id": "target-1",
                "benchmark_id": "benchmark-1",
                "test_definition_id": "test-1",
                "started_at": None,
                "finished_at": None,
                "paused_at": None,
                "interrupted_at": None,
                "seed": None,
                "rag_eval_version": None,
                "tags": [],
                "metadata": {},
                "created_at": NOW,
                "updated_at": NOW,
                "total_cases": 1,
                "complete_cases": 0,
                "failed_cases": 0,
                "pending_cases": 1,
                "running_cases": 0,
            }

        async def execute_run(self, run_id: str) -> None:
            executed.append(run_id)

    background_tasks = BackgroundTasks()

    class Session:
        async def commit(self) -> None:
            return None

        async def rollback(self) -> None:
            return None

    result = await test_api.start_test_run(
        "test-1", Service(), Session(), background_tasks
    )

    assert result.run_id == "run-1"
    assert len(background_tasks.tasks) == 1
    await background_tasks()
    assert executed == ["run-1"]


@pytest.mark.asyncio
async def test_retry_failed_cases_commits_and_queues_reset_subset() -> None:
    """Retry commits before scheduling execution and preserves the case subset."""

    class Session:
        committed = False

        async def commit(self) -> None:
            self.committed = True

        async def rollback(self) -> None:
            raise AssertionError("rollback should not be needed")

    session = Session()
    executed: list[tuple[str, set[str], bool]] = []

    class Service:
        async def retry_failed_cases(self, run_id: str) -> RetryFailedCasesResult:
            assert run_id == "run-1"
            return RetryFailedCasesResult(
                run={
                    "run_id": "run-1",
                    "name": "test",
                    "status": "PENDING",
                    "status_reason": None,
                    "config_hash": "hash",
                    "target_id": "target-1",
                    "benchmark_id": "benchmark-1",
                    "test_definition_id": "test-1",
                    "started_at": None,
                    "finished_at": None,
                    "paused_at": None,
                    "interrupted_at": None,
                    "seed": None,
                    "rag_eval_version": None,
                    "tags": [],
                    "metadata": {},
                    "created_at": NOW,
                    "updated_at": NOW,
                    "total_cases": 2,
                    "complete_cases": 1,
                    "failed_cases": 0,
                    "pending_cases": 1,
                    "running_cases": 0,
                },
                case_execution_ids={"case-exec-failed"},
            )

        async def execute_run(
            self,
            run_id: str,
            *,
            case_execution_ids: set[str],
        ) -> None:
            executed.append((run_id, case_execution_ids, session.committed))

    background_tasks = BackgroundTasks()
    result = await test_api.retry_failed_cases(
        "run-1",
        Service(),
        session,
        background_tasks,
    )

    assert result.run_id == "run-1"
    await background_tasks()
    assert executed == [("run-1", {"case-exec-failed"}, True)]


@pytest.mark.asyncio
async def test_case_observation_endpoint_returns_detail() -> None:
    """The run API exposes a persisted observation for a case execution."""

    class Service:
        async def get_case_observation(
            self,
            run_id: str,
            case_execution_id: str,
            *,
            attempt_id: str | None = None,
        ) -> dict[str, object]:
            assert run_id == "run-1"
            assert case_execution_id == "case-exec-1"
            assert attempt_id is None
            return {
                "observation_id": "observation-1",
                "request_id": "request-1",
                "case_execution_id": "case-exec-1",
                "attempt_id": "attempt-1",
                "answer": {"text": "Generated answer"},
                "retrieval": None,
                "citations": [],
                "confidence": [],
                "trace": None,
                "usage": None,
                "errors": [],
                "warnings": [],
                "normalization_version": "1.0",
                "created_at": NOW,
            }

    result = await test_api.get_case_observation(
        "run-1",
        "case-exec-1",
        Service(),
    )

    assert result is not None
    assert result.answer == {"text": "Generated answer"}
