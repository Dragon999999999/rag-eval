"""Tests for the refactored test/run API boundary and schemas."""

from datetime import UTC, datetime

import pytest
from fastapi import HTTPException

from rag_eval.api import test as test_api
from rag_eval.api.test_schemas import (
    TestCreate,
    TestDetail,
    TestMetricSelectionUpdate,
    TestUpdate,
)

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

    with pytest.raises(HTTPException) as invalid:
        await test_api.start_test_run("test-1", Service())
    assert invalid.value.status_code == 422

    with pytest.raises(HTTPException) as missing:
        await test_api.get_run("missing", Service())
    assert missing.value.status_code == 404
