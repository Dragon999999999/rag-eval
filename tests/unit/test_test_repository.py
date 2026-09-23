"""Unit coverage for the test/run persistence boundary.

The repository is intentionally tested with a small in-memory async session
double.  This keeps the deterministic repository behavior covered without
requiring PostgreSQL for the ordinary unit suite; database-specific constraint
coverage remains in ``tests/integration/test_test_persistence.py``.
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.inspection import inspect

from rag_eval.db.test_models import (
    AttemptRecord,
    CaseExecutionRecord,
    RunConfigRecord,
    RunEventRecord,
    RunRecord,
    TestDefinitionRecord,
    TestMetricSelectionRecord,
)
from rag_eval.db.test_repository import TestRepository
from rag_eval.models import AggregateMetricResult, MetricResult, MetricStatus

# These production classes begin with ``Test`` but are not pytest test classes.
for _production_class in (
    TestDefinitionRecord,
    TestMetricSelectionRecord,
    TestRepository,
):
    _production_class.__test__ = False


class MemoryResult:
    """Minimal SQLAlchemy result facade used by ``MemoryAsyncSession``."""

    def __init__(self, rows: list[Any]) -> None:
        self._rows = rows

    def all(self) -> list[Any]:
        return list(self._rows)


class MemoryAsyncSession:
    """Small async session double implementing repository query semantics."""

    def __init__(self) -> None:
        self.records: dict[type[Any], dict[Any, Any]] = {}
        self.models_by_table = {
            model.__tablename__: model
            for model in (
                TestDefinitionRecord,
                TestMetricSelectionRecord,
                RunConfigRecord,
                RunRecord,
                RunEventRecord,
                CaseExecutionRecord,
                AttemptRecord,
            )
        }

    def add(self, record: Any) -> None:
        model = type(record)
        self._apply_defaults(record)
        primary_key = inspect(model).primary_key[0].key
        self.records.setdefault(model, {})[getattr(record, primary_key)] = record

    async def delete(self, record: Any) -> None:
        model = type(record)
        primary_key = inspect(model).primary_key[0].key
        self.records.get(model, {}).pop(getattr(record, primary_key), None)

    async def get(self, model: type[Any], key: Any) -> Any | None:
        return self.records.get(model, {}).get(key)

    async def flush(self) -> None:
        self._check_constraints()

    async def scalars(self, statement: Any) -> MemoryResult:
        model = statement.column_descriptions[0]["entity"]
        rows = list(self.records.get(model, {}).values())
        rows = [row for row in rows if self._matches(row, statement)]

        for order in reversed(statement._order_by_clauses):
            key = getattr(order, "key", None)
            if key is None:
                key = getattr(getattr(order, "element", None), "key", None)
            modifier = getattr(order, "modifier", None)
            descending = getattr(modifier, "__name__", "") == "desc_op"
            if key is not None:
                rows.sort(
                    key=lambda row: getattr(row, key),
                    reverse=descending,
                )
        return MemoryResult(rows)

    async def scalar(self, statement: Any) -> Any | None:
        rows = await self.scalars(statement)
        return rows.all()[0] if rows.all() else None

    async def execute(self, statement: Any) -> MemoryResult:
        if statement.is_delete:
            model = self.models_by_table[statement.table.name]
            rows = list(self.records.get(model, {}).values())
            for row in rows:
                if self._matches(row, statement):
                    primary_key = inspect(model).primary_key[0].key
                    self.records[model].pop(getattr(row, primary_key), None)
            return MemoryResult([])

        model = statement.column_descriptions[0].get("entity")
        if model is None:
            model = self.models_by_table[statement.froms[0].name]
        rows = [row for row in self.records.get(model, {}).values()]
        rows = [row for row in rows if self._matches(row, statement)]
        grouped: dict[str, int] = {}
        for row in rows:
            grouped[row.status] = grouped.get(row.status, 0) + 1
        return MemoryResult([(status, count) for status, count in grouped.items()])

    def _apply_defaults(self, record: Any) -> None:
        now = datetime.now(UTC)
        for column in inspect(type(record)).columns:
            if getattr(record, column.key, None) is not None:
                continue
            if column.key in {"created_at", "updated_at"}:
                setattr(record, column.key, now)
            elif column.default is not None:
                default = column.default.arg
                if callable(default):
                    try:
                        default = default()
                    except TypeError:
                        default = default(None)
                setattr(record, column.key, default)

    def _check_constraints(self) -> None:
        for model, rows in self.records.items():
            table = inspect(model).local_table
            for constraint in table.constraints:
                if constraint.__class__.__name__ != "UniqueConstraint":
                    continue
                columns = constraint.columns
                keys = [column.key for column in columns]
                seen: set[tuple[Any, ...]] = set()
                for row in rows.values():
                    value = tuple(getattr(row, key) for key in keys)
                    if any(item is None for item in value):
                        continue
                    if value in seen:
                        raise IntegrityError(
                            "duplicate unique value",
                            value,
                            ValueError("duplicate unique value"),
                        )
                    seen.add(value)

    @staticmethod
    def _matches(row: Any, statement: Any) -> bool:
        return all(
            MemoryAsyncSession._matches_expression(row, expression)
            for expression in statement._where_criteria
        )

    @staticmethod
    def _matches_expression(row: Any, expression: Any) -> bool:
        if expression.__class__.__name__ == "BooleanClauseList":
            return all(
                MemoryAsyncSession._matches_expression(row, clause)
                for clause in expression.clauses
            )

        left = getattr(expression.left, "key", None)
        right = getattr(expression.right, "value", None)
        value = getattr(row, left, None)
        operator_name = getattr(expression.operator, "__name__", "")
        if operator_name == "eq":
            return value == right
        if operator_name == "is_":
            expected = (
                right if right is not None else str(expression.right).lower() == "true"
            )
            return value is expected or value == expected
        if operator_name in {"in_op", "not_in_op"}:
            values = getattr(expression.right, "value", None) or []
            return value in values
        return True


def definition_record(
    test_id: str = "test-1", name: str = "Test"
) -> TestDefinitionRecord:
    """Build a test definition with explicit values for database defaults."""
    return TestDefinitionRecord(
        test_definition_id=test_id,
        name=name,
        configuration_status="INCOMPLETE",
        metric_selection_mode="EXPLICIT",
        judge_config={},
        retrieval_config={},
        execution_config={},
        tags=[],
        metadata_json={},
    )


def run_record(run_id: str, config_hash: str = "hash-1") -> RunRecord:
    """Build a pending run record for repository tests."""
    return RunRecord(
        run_id=run_id,
        name=run_id,
        status="PENDING",
        config_hash=config_hash,
        target_id="target-1",
        benchmark_id="benchmark-1",
        test_definition_id="test-1",
        tags=[],
        metadata_json={},
    )


@pytest.fixture
def repository() -> TestRepository:
    """Return a repository backed by the deterministic session double."""
    return TestRepository(MemoryAsyncSession())


@pytest.mark.asyncio
async def test_test_definition_crud_and_nullable_updates(
    repository: TestRepository,
) -> None:
    """Test records support incomplete creation and explicit nullable clears."""
    created = await repository.create_test(
        TestDefinitionRecord(test_definition_id="test-1", name="Test")
    )
    assert created.configuration_status == "INCOMPLETE"
    assert created.metric_selection_mode == "EXPLICIT"
    assert created.target_id is None
    assert created.benchmark_id is None
    assert created.definition_hash is None

    await repository.update_test(
        "test-1",
        target_id="target-1",
        benchmark_id="benchmark-1",
        seed=42,
        execution_config={"concurrency": 2},
        tags=["nightly"],
        metadata={"owner": "qa"},
    )
    record = await repository.get_test("test-1")
    assert record is not None
    assert (record.target_id, record.benchmark_id, record.seed) == (
        "target-1",
        "benchmark-1",
        42,
    )
    assert record.execution_config == {"concurrency": 2}
    assert record.tags == ["nightly"]
    assert record.metadata_json == {"owner": "qa"}

    await repository.update_test(
        "test-1",
        clear_target=True,
        clear_benchmark=True,
        clear_seed=True,
    )
    record = await repository.get_test("test-1")
    assert record is not None
    assert record.target_id is None
    assert record.benchmark_id is None
    assert record.seed is None


@pytest.mark.asyncio
async def test_test_listing_is_deterministic_and_delete_removes_record(
    repository: TestRepository,
) -> None:
    """Test listing uses stable identity ordering and deletion is explicit."""
    await repository.create_test(definition_record("test-b", "B"))
    await repository.create_test(definition_record("test-a", "A"))
    records = await repository.list_tests()
    assert [record.test_definition_id for record in records] == ["test-b", "test-a"]
    assert [record.test_definition_id for record in await repository.list_tests()] == [
        "test-b",
        "test-a",
    ]

    await repository.delete_test("test-a")
    assert await repository.get_test("test-a") is None


@pytest.mark.asyncio
async def test_metric_selection_replacement_clear_enabled_filter_and_parameters(
    repository: TestRepository,
) -> None:
    """Selection replacement preserves configuration and removes old rows."""
    await repository.create_test(definition_record())
    first = TestMetricSelectionRecord(
        test_metric_selection_id="selection-1",
        test_definition_id="test-1",
        metric_id="metric-a",
        metric_version="2",
        parameters={"k": 3},
        enabled=True,
    )
    disabled = TestMetricSelectionRecord(
        test_metric_selection_id="selection-2",
        test_definition_id="test-1",
        metric_id="metric-old",
        metric_version="1",
        parameters={},
        enabled=False,
    )
    await repository.replace_test_metric_selections("test-1", [first, disabled])
    assert [
        row.metric_id for row in await repository.list_test_metric_selections("test-1")
    ] == [
        "metric-a",
        "metric-old",
    ]
    enabled = await repository.list_test_metric_selections("test-1", enabled_only=True)
    assert [row.metric_id for row in enabled] == ["metric-a"]
    assert enabled[0].parameters == {"k": 3}
    assert enabled[0].metric_version == "2"

    replacement = TestMetricSelectionRecord(
        test_metric_selection_id="selection-3",
        test_definition_id="test-1",
        metric_id="metric-b",
        metric_version="7",
        parameters={"threshold": 0.5},
        enabled=True,
    )
    await repository.replace_test_metric_selections("test-1", [replacement])
    assert [
        row.metric_id for row in await repository.list_test_metric_selections("test-1")
    ] == ["metric-b"]
    await repository.clear_test_metric_selections("test-1")
    assert await repository.list_test_metric_selections("test-1") == []


@pytest.mark.asyncio
async def test_duplicate_metric_selection_is_rejected(
    repository: TestRepository,
) -> None:
    """The test/metric uniqueness constraint prevents duplicate selections."""
    await repository.create_test(definition_record())
    selection = TestMetricSelectionRecord(
        test_metric_selection_id="selection-1",
        test_definition_id="test-1",
        metric_id="metric-a",
    )
    duplicate = TestMetricSelectionRecord(
        test_metric_selection_id="selection-2",
        test_definition_id="test-1",
        metric_id="metric-a",
    )
    await repository.replace_test_metric_selections("test-1", [selection])
    with pytest.raises(IntegrityError):
        await repository.replace_test_metric_selections(
            "test-1", [selection, duplicate]
        )


@pytest.mark.asyncio
async def test_run_config_deduplication_rejects_hash_collision(
    repository: TestRepository,
) -> None:
    """A hash may be reused only when its canonical snapshot is identical."""
    first = await repository.create_run(run_record("run-1"), {"a": 1})
    second = await repository.create_run(run_record("run-2"), {"a": 1})
    assert first.run_id == "run-1"
    assert second.run_id == "run-2"
    snapshot = await repository.get_run_config("run-2")
    assert snapshot is not None
    assert snapshot.canonical_config == {"a": 1}

    with pytest.raises(ValueError, match="different"):
        await repository.create_run(run_record("run-3"), {"a": 2})


@pytest.mark.asyncio
async def test_run_lifecycle_events_filters_and_case_counts(
    repository: TestRepository,
) -> None:
    """Run lifecycle fields, filters, events, and progress counts persist."""
    await repository.create_run(run_record("run-1"), {"version": 1})
    await repository.create_run(run_record("run-2", "hash-2"), {"version": 2})
    await repository.update_run_lifecycle(
        "run-1",
        status="PAUSED",
        status_reason="operator requested",
        paused_at=datetime(2026, 1, 1, tzinfo=UTC),
        interrupted_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    run = await repository.get_run("run-1")
    assert run is not None
    assert run.status_reason == "operator requested"
    assert run.paused_at is not None
    assert run.interrupted_at is not None

    await repository.append_run_event(
        RunEventRecord(
            run_event_id="event-1",
            run_id="run-1",
            event_type="CREATED",
            payload={},
        )
    )
    await repository.append_run_event(
        RunEventRecord(
            run_event_id="event-2",
            run_id="run-1",
            event_type="QUEUED",
            payload={"priority": 1},
        )
    )
    assert [
        event.event_type for event in await repository.list_run_events("run-1")
    ] == [
        "CREATED",
        "QUEUED",
    ]
    assert [run.run_id for run in await repository.list_runs(statuses=["PAUSED"])] == [
        "run-1"
    ]
    assert [
        run.run_id for run in await repository.list_runs(test_definition_id="test-1")
    ] == [
        "run-2",
        "run-1",
    ]

    for case_id, status in (("case-1", "PENDING"), ("case-2", "COMPLETED")):
        await repository.create_case_execution(
            CaseExecutionRecord(
                case_execution_id=f"execution-{case_id}",
                run_id="run-1",
                case_id=case_id,
                status=status,
            )
        )
    assert await repository.get_run_case_counts("run-1") == {
        "PENDING": 1,
        "COMPLETED": 1,
    }


@pytest.mark.asyncio
async def test_case_executions_and_attempts_are_ordered_and_append_only(
    repository: TestRepository,
) -> None:
    """Logical cases are unique while their retry attempts remain historical."""
    await repository.create_run(run_record("run-1"), {})
    await repository.create_case_execution(
        CaseExecutionRecord(
            case_execution_id="execution-1",
            run_id="run-1",
            case_id="case-1",
            status="PENDING",
        )
    )
    with pytest.raises(IntegrityError):
        await repository.create_case_execution(
            CaseExecutionRecord(
                case_execution_id="execution-2",
                run_id="run-1",
                case_id="case-1",
                status="PENDING",
            )
        )
    repository._session.records[CaseExecutionRecord].pop("execution-2")  # type: ignore[attr-defined]

    await repository.update_case_execution_status("execution-1", "RUNNING")
    attempt_one = await repository.create_attempt(
        AttemptRecord(
            attempt_id="attempt-1",
            case_execution_id="execution-1",
            attempt_number=1,
            request_id="request-1",
            status="COMPLETED",
        )
    )
    await repository.create_attempt(
        AttemptRecord(
            attempt_id="attempt-2",
            case_execution_id="execution-1",
            attempt_number=2,
            request_id="request-2",
            status="RETRYABLE_FAILURE",
            retryable=True,
            error_summary="timeout",
        )
    )
    assert attempt_one.status == "COMPLETED"
    attempts = await repository.list_attempts("execution-1")
    assert [attempt.attempt_number for attempt in attempts] == [1, 2]
    assert (
        await repository.get_latest_attempt("execution-1")
    ).attempt_id == "attempt-2"
    assert attempts[1].retryable is True
    assert attempts[1].error_summary == "timeout"


@pytest.mark.asyncio
async def test_metric_and_aggregate_persistence_requires_real_run_id(
    repository: TestRepository,
) -> None:
    """Metric persistence never substitutes an empty run identifier."""
    await repository.create_run(run_record("run-1"), {})
    metric = MetricResult(
        metric_result_id="metric-result-1",
        metric_id="metric-a",
        metric_version="1",
        run_id="run-1",
        case_id="case-1",
        status=MetricStatus.COMPUTED,
        value=1.0,
    )
    persisted = await repository.persist_metric(metric)
    assert persisted.run_id == "run-1"
    with pytest.raises(ValueError, match="run_id is required"):
        await repository.persist_metric(metric.model_copy(update={"run_id": None}))
    with pytest.raises(ValueError, match="run_id is required"):
        await repository.persist_metric(metric.model_copy(update={"run_id": ""}))

    aggregate = await repository.persist_aggregate(
        AggregateMetricResult(
            run_id="run-1",
            metric_id="metric-a",
            metric_version="1",
            aggregation="mean",
            value=1.0,
            status=MetricStatus.COMPUTED,
            sample_count=1,
            available_count=1,
            failed_count=0,
        )
    )
    assert aggregate.run_id == "run-1"
    assert [row.metric_id for row in await repository.list_metric_results("run-1")] == [
        "metric-a"
    ]
    assert [row.metric_id for row in await repository.list_aggregates("run-1")] == [
        "metric-a"
    ]
