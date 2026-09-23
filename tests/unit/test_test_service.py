"""Behavioral tests for test configuration and run orchestration."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any

import pytest

from rag_eval.db.test_models import (
    CaseExecutionRecord,
    RunConfigRecord,
    RunEventRecord,
    RunRecord,
    TestDefinitionRecord,
    TestMetricSelectionRecord,
)
from rag_eval.metrics.base import MetricDefinition, MetricScope
from rag_eval.metrics.registry import MetricRegistry
from rag_eval.models import BenchmarkCase
from rag_eval.services.test_service import (
    ALL_AVAILABLE,
    EXPLICIT,
    INCOMPLETE,
    READY,
    TestService,
)

# These production classes begin with ``Test`` but are not pytest test classes.
for _production_class in (
    TestDefinitionRecord,
    TestMetricSelectionRecord,
    TestService,
):
    _production_class.__test__ = False

NOW = datetime(2026, 9, 23, tzinfo=UTC)


class StubMetric:
    """Metric implementation carrying only a registry definition."""

    def __init__(self, metric_id: str, requirements: list[Any] | None = None) -> None:
        self._definition = MetricDefinition(
            metric_id=metric_id,
            version="1",
            scope=MetricScope.CASE,
            requirements=requirements or [],  # type: ignore[arg-type]
            description=f"{metric_id} description",
        )

    @property
    def definition(self) -> MetricDefinition:
        """Return the test definition."""
        return self._definition

    async def compute(self, context: Any) -> Any:
        """This stub is not executed by test configuration tests."""
        raise NotImplementedError


class MemoryTestRepository:
    """Stateful repository substitute for service-level tests."""

    def __init__(self) -> None:
        self.tests: dict[str, TestDefinitionRecord] = {}
        self.selections: dict[str, list[TestMetricSelectionRecord]] = {}
        self.runs: dict[str, RunRecord] = {}
        self.configs: dict[str, RunConfigRecord] = {}
        self.case_executions: dict[str, CaseExecutionRecord] = {}
        self.events: list[RunEventRecord] = []

    async def create_test(self, record: TestDefinitionRecord) -> TestDefinitionRecord:
        record.created_at = NOW
        record.updated_at = NOW
        self.tests[record.test_definition_id] = record
        return record

    async def get_test(self, test_id: str) -> TestDefinitionRecord | None:
        return self.tests.get(test_id)

    async def list_tests(self) -> list[TestDefinitionRecord]:
        return sorted(self.tests.values(), key=lambda item: item.test_definition_id)

    async def update_test(self, test_id: str, **changes: Any) -> TestDefinitionRecord:
        record = self.tests[test_id]
        if changes.pop("clear_target", False):
            record.target_id = None
        elif changes.get("target_id") is not None:
            record.target_id = changes["target_id"]
        if changes.pop("clear_benchmark", False):
            record.benchmark_id = None
        elif changes.get("benchmark_id") is not None:
            record.benchmark_id = changes["benchmark_id"]
        if changes.pop("clear_seed", False):
            record.seed = None
        elif changes.get("seed") is not None:
            record.seed = changes["seed"]
        if changes.pop("clear_definition_hash", False):
            record.definition_hash = None
        elif changes.get("definition_hash") is not None:
            record.definition_hash = changes["definition_hash"]

        for name in (
            "name",
            "description",
            "configuration_status",
            "metric_selection_mode",
            "judge_config",
            "retrieval_config",
            "execution_config",
            "tags",
            "metadata",
        ):
            if name not in changes:
                continue
            value = changes[name]
            if name == "metadata":
                record.metadata_json = dict(value)
            elif name in {"judge_config", "retrieval_config", "execution_config"}:
                setattr(record, name, dict(value))
            elif name == "tags":
                record.tags = list(value)
            else:
                setattr(record, name, value)
        return record

    async def delete_test(self, test_id: str) -> None:
        if test_id not in self.tests:
            raise KeyError(test_id)
        del self.tests[test_id]

    async def list_test_metric_selections(
        self, test_id: str, *, enabled_only: bool = False
    ) -> list[TestMetricSelectionRecord]:
        selections = sorted(
            self.selections.get(test_id, []), key=lambda item: item.metric_id
        )
        return [item for item in selections if not enabled_only or item.enabled]

    async def replace_test_metric_selections(
        self, test_id: str, selections: list[TestMetricSelectionRecord]
    ) -> list[TestMetricSelectionRecord]:
        self.selections[test_id] = list(selections)
        return await self.list_test_metric_selections(test_id)

    async def clear_test_metric_selections(self, test_id: str) -> None:
        self.selections[test_id] = []

    async def create_run(
        self, run: RunRecord, canonical_config: dict[str, Any]
    ) -> RunRecord:
        existing = self.configs.get(run.config_hash)
        if existing is not None and existing.canonical_config != canonical_config:
            raise ValueError(
                "config_hash already exists with a different canonical configuration"
            )
        if existing is None:
            self.configs[run.config_hash] = RunConfigRecord(
                config_hash=run.config_hash,
                canonical_config=dict(canonical_config),
                created_at=NOW,
            )
        run.created_at = NOW
        run.updated_at = NOW
        self.runs[run.run_id] = run
        return run

    async def get_run(self, run_id: str) -> RunRecord | None:
        return self.runs.get(run_id)

    async def list_runs(
        self, *, test_definition_id: str | None = None, statuses: Any = None
    ) -> list[RunRecord]:
        runs = list(self.runs.values())
        if test_definition_id is not None:
            runs = [
                item for item in runs if item.test_definition_id == test_definition_id
            ]
        if statuses:
            runs = [item for item in runs if item.status in statuses]
        return runs

    async def update_run_lifecycle(self, run_id: str, **changes: Any) -> RunRecord:
        run = self.runs[run_id]
        for clear_name, field_name in (
            ("clear_status_reason", "status_reason"),
            ("clear_finished_at", "finished_at"),
            ("clear_paused_at", "paused_at"),
            ("clear_interrupted_at", "interrupted_at"),
        ):
            if changes.pop(clear_name, False):
                setattr(run, field_name, None)
        for name, value in changes.items():
            if value is not None:
                setattr(run, name, value)
        return run

    async def append_run_event(self, event: RunEventRecord) -> RunEventRecord:
        event.created_at = NOW
        self.events.append(event)
        return event

    async def list_run_events(self, run_id: str) -> list[RunEventRecord]:
        return [event for event in self.events if event.run_id == run_id]

    async def create_case_execution(
        self, record: CaseExecutionRecord
    ) -> CaseExecutionRecord:
        record.created_at = NOW
        record.updated_at = NOW
        self.case_executions[record.case_execution_id] = record
        return record

    async def list_case_executions(
        self, run_id: str, *, statuses: Any = None
    ) -> list[CaseExecutionRecord]:
        cases = [
            item for item in self.case_executions.values() if item.run_id == run_id
        ]
        if statuses:
            cases = [item for item in cases if item.status in statuses]
        return cases

    async def get_case_execution(
        self, case_execution_id: str
    ) -> CaseExecutionRecord | None:
        return self.case_executions.get(case_execution_id)

    async def update_case_execution_status(
        self, case_execution_id: str, status: str, **changes: Any
    ) -> CaseExecutionRecord:
        case = self.case_executions[case_execution_id]
        case.status = status
        for name, value in changes.items():
            if not name.startswith("clear_") and value is not None:
                setattr(case, name, value)
        return case

    async def get_run_case_counts(self, run_id: str) -> dict[str, int]:
        counts: dict[str, int] = {}
        for case in await self.list_case_executions(run_id):
            counts[case.status] = counts.get(case.status, 0) + 1
        return counts

    async def list_attempts(self, case_execution_id: str) -> list[Any]:
        return []


class MemoryTargetRepository:
    """Target state and capability double."""

    def __init__(self, *, capabilities: Any = None) -> None:
        self.targets = {
            "target-1": SimpleNamespace(
                target_id="target-1",
                enabled=True,
                current_config_version=3,
                adapter_type="python",
            )
        }
        self.capability_values = {"target-1": capabilities or {"query": True}}

    async def get_target(self, target_id: str) -> Any:
        return self.targets.get(target_id)

    async def get_capabilities(self, target_id: str) -> Any:
        return self.capability_values.get(target_id)

    async def get_current_config_version(self, target_id: str) -> Any:
        target = self.targets.get(target_id)
        if target is None:
            return None
        return SimpleNamespace(version=target.current_config_version)


class MemoryBenchmarkRepository:
    """Benchmark and case double with configurable case content."""

    def __init__(self, cases: list[Any] | None = None) -> None:
        self.cases = cases or [BenchmarkCase(case_id="case-1", query="Question")]
        self.benchmark = SimpleNamespace(
            benchmark_id="benchmark-1",
            version="1",
            content_hash="benchmark-hash",
        )

    async def get_benchmark(self, benchmark_id: str) -> Any:
        return self.benchmark if benchmark_id == "benchmark-1" else None

    async def list_cases(self, benchmark_id: str) -> list[Any]:
        return list(self.cases) if benchmark_id == "benchmark-1" else []


def service_fixture(
    *,
    requirements: dict[str, list[Any]] | None = None,
    capabilities: Any = None,
    cases: list[Any] | None = None,
) -> tuple[
    TestService, MemoryTestRepository, MemoryTargetRepository, MemoryBenchmarkRepository
]:
    """Build a service and its in-memory domain collaborators."""
    repository = MemoryTestRepository()
    target_repository = MemoryTargetRepository(capabilities=capabilities)
    benchmark_repository = MemoryBenchmarkRepository(cases=cases)
    registry = MetricRegistry()
    for metric_id, metric_requirements in (
        requirements or {"metric.answer": []}
    ).items():
        registry.register(StubMetric(metric_id, metric_requirements))
    return (
        TestService(
            repository=repository,  # type: ignore[arg-type]
            target_repository=target_repository,  # type: ignore[arg-type]
            benchmark_repository=benchmark_repository,  # type: ignore[arg-type]
            metric_registry=registry,
        ),
        repository,
        target_repository,
        benchmark_repository,
    )


async def ready_test(service: TestService, repository: MemoryTestRepository) -> str:
    """Create and configure a valid explicit test."""
    created = await service.create_test(name="  Evaluation  ", metadata={"team": "qa"})
    test_id = created["test_definition_id"]
    await service.update_test(
        test_id, changes={"target_id": "target-1", "benchmark_id": "benchmark-1"}
    )
    await service.set_test_metrics(
        test_id,
        mode=EXPLICIT,
        selected_metrics=["metric.answer"],
        metric_parameters={"metric.answer": {"threshold": 0.8}},
        judge_config={"provider": "local"},
        retrieval_config={"top_k": 5},
    )
    assert repository.tests[test_id].configuration_status == READY
    return test_id


@pytest.mark.asyncio
async def test_create_and_crud_use_api_facing_field_names() -> None:
    """CRUD accepts only a name initially and exposes metadata, not ORM names."""
    service, repository, _, _ = service_fixture()
    created = await service.create_test(name="  My test  ", metadata={"owner": "qa"})
    assert created["name"] == "My test"
    assert created["metadata"] == {"owner": "qa"}
    assert created["configuration_status"] == INCOMPLETE
    assert created["metric_selection_mode"] == EXPLICIT
    assert created["definition_hash"] is None
    assert "metadata_json" not in created

    test_id = created["test_definition_id"]
    assert (await service.get_test(test_id))["name"] == "My test"
    assert len(await service.list_tests()) == 1
    updated = await service.update_test(
        test_id,
        changes={
            "execution_config": {"concurrency": 2},
            "seed": 9,
            "tags": ["nightly"],
            "metadata": {"owner": "platform"},
        },
    )
    assert updated["execution_config"] == {"concurrency": 2}
    assert updated["metadata"] == {"owner": "platform"}
    await service.delete_test(test_id)
    assert await service.get_test(test_id) is None
    assert repository.tests == {}

    with pytest.raises(ValueError, match="must not be empty"):
        await service.create_test(name="   ")


@pytest.mark.asyncio
async def test_metric_selection_modes_normalize_duplicates_and_preserve_configs() -> (
    None
):
    """Explicit and dynamic metric selection retain parameters and UI settings."""
    service, repository, _, _ = service_fixture()
    test_id = await ready_test(service, repository)
    explicit = await service.get_test_metrics(test_id)
    assert explicit["mode"] == EXPLICIT
    assert explicit["selected_metric_ids"] == ["metric.answer"]
    assert explicit["judge_config"] == {"provider": "local"}
    assert explicit["retrieval_config"] == {"top_k": 5}
    assert explicit["metrics"][0]["parameters"] == {"threshold": 0.8}

    result = await service.set_test_metrics(
        test_id,
        mode="explicit",
        selected_metrics=["metric.answer", "metric.answer"],
        metric_parameters={"metric.answer": {"threshold": 0.9}},
        judge_config={"provider": "remote"},
        retrieval_config={"top_k": 10},
    )
    assert result["selected_metric_ids"] == ["metric.answer"]
    assert len(repository.selections[test_id]) == 1
    assert repository.selections[test_id][0].parameters == {"threshold": 0.9}

    all_result = await service.select_all_applicable_metrics(test_id)
    assert all_result["mode"] == ALL_AVAILABLE
    assert all_result["selected_metric_ids"] == ["metric.answer"]
    assert repository.selections[test_id] == []
    assert repository.tests[test_id].configuration_status == READY


@pytest.mark.asyncio
async def test_metric_selection_rejects_invalid_or_inapplicable_requests() -> None:
    """Selection errors distinguish mode, registry, and applicability failures."""
    service, repository, _, _ = service_fixture(
        requirements={"metric.needs.retrieval": [{"capability": "retrieval"}]}
    )
    created = await service.create_test(name="Test")
    test_id = created["test_definition_id"]
    with pytest.raises(ValueError, match="mode"):
        await service.set_test_metrics(
            test_id,
            mode="UNKNOWN",
            selected_metrics=[],
            metric_parameters={},
            judge_config={},
            retrieval_config={},
        )
    with pytest.raises(ValueError, match="unknown metrics"):
        await service.set_test_metrics(
            test_id,
            mode=EXPLICIT,
            selected_metrics=["missing"],
            metric_parameters={},
            judge_config={},
            retrieval_config={},
        )
    with pytest.raises(ValueError, match="at least one"):
        await service.set_test_metrics(
            test_id,
            mode=EXPLICIT,
            selected_metrics=[],
            metric_parameters={},
            judge_config={},
            retrieval_config={},
        )
    await service.update_test(test_id, changes={"target_id": "target-1"})
    with pytest.raises(ValueError, match="not applicable"):
        await service.set_test_metrics(
            test_id,
            mode=EXPLICIT,
            selected_metrics=["metric.needs.retrieval"],
            metric_parameters={},
            judge_config={},
            retrieval_config={},
        )


@pytest.mark.asyncio
async def test_metric_applicability_checks_requirements_and_warnings() -> None:
    """Capability, benchmark-field, and deferred requirements are covered."""
    cases = [
        BenchmarkCase(case_id="case-1", query="Q", reference_answer="A"),
    ]
    service, repository, _, _ = service_fixture(
        requirements={
            "query": [{"capability": "query"}],
            "stages": [{"capability": "retrieval.stages"}],
            "reference": [{"benchmark_field": "reference_answer"}],
            "deferred": [{"future_requirement": "later"}],
        },
        capabilities={"query": True, "retrieval": {"stages": True}},
        cases=cases,
    )
    created = await service.create_test(name="Test")
    test_id = created["test_definition_id"]
    info = await service.get_test_metrics(test_id)
    by_id = {metric["metric_id"]: metric for metric in info["metrics"]}
    assert by_id["query"]["applicable"] is False
    assert "no target selected" in by_id["query"]["unavailable_reason"]
    assert any("deferred" in warning for warning in info["warnings"])

    await service.update_test(
        test_id, changes={"target_id": "target-1", "benchmark_id": "benchmark-1"}
    )
    info = await service.get_test_metrics(test_id)
    by_id = {metric["metric_id"]: metric for metric in info["metrics"]}
    assert by_id["stages"]["applicable"] is True
    assert by_id["reference"]["applicable"] is True
    assert by_id["deferred"]["applicable"] is True


@pytest.mark.asyncio
async def test_yaml_round_trip_conflicts_and_invalid_inputs() -> None:
    """Portable YAML handles all/explicit modes, warnings, conflicts, and shapes."""
    service, repository, _, _ = service_fixture()
    created = await service.create_test(name="Test")
    test_id = created["test_definition_id"]
    imported = await service.import_test_yaml(
        test_id,
        """
metrics: [metric.answer, unknown]
target_id: target-1
benchmark_id: benchmark-1
parameters:
  metric.answer:
    threshold: 0.7
judge:
  provider: local
retrieval:
  top_k: 4
""",
    )
    assert imported["selected_metrics"] == ["metric.answer"]
    assert imported["ignored_metrics"] == ["unknown"]
    assert repository.tests[test_id].target_id == "target-1"
    assert repository.tests[test_id].benchmark_id == "benchmark-1"
    exported = await service.export_test_yaml(test_id)
    assert "metrics:" in exported and "metric.answer" in exported
    assert "threshold" in exported and "provider" in exported and "top_k" in exported

    all_import = await service.import_test_yaml(test_id, "metrics: all\n")
    assert all_import["mode"] == ALL_AVAILABLE
    assert (await service.export_test_yaml(test_id)).splitlines()[0] == "metrics: all"

    conflict = await service.import_test_yaml(
        test_id, "metrics: all\ntarget_id: other-target\n"
    )
    assert conflict["target_conflict"] is True
    assert repository.tests[test_id].target_id == "target-1"

    with pytest.raises(ValueError, match="invalid YAML"):
        await service.import_test_yaml(test_id, "metrics: [")
    with pytest.raises(ValueError, match="root"):
        await service.import_test_yaml(test_id, "- metric.answer")
    with pytest.raises(ValueError, match="parameters"):
        await service.import_test_yaml(
            test_id, "metrics: [metric.answer]\nparameters: []"
        )

    empty = await service.import_test_yaml(test_id, "metrics: [missing]\n")
    assert empty["selected_metrics"] == []
    assert repository.tests[test_id].configuration_status == INCOMPLETE


@pytest.mark.asyncio
async def test_yaml_import_reports_known_but_inapplicable_metrics() -> None:
    """Known metric IDs remain distinguishable from metrics unavailable to a test."""
    service, repository, _, _ = service_fixture(
        requirements={"metric.citations": [{"capability": "citations"}]}
    )
    created = await service.create_test(name="Test")
    test_id = created["test_definition_id"]
    repository.tests[test_id].target_id = "target-1"
    repository.tests[test_id].benchmark_id = "benchmark-1"
    result = await service.import_test_yaml(test_id, "metrics: [metric.citations]\n")
    assert result["ignored_metrics"] == []
    assert result["unavailable_metrics"] == ["metric.citations"]
    assert repository.tests[test_id].configuration_status == INCOMPLETE


@pytest.mark.asyncio
async def test_validation_covers_missing_resources_and_ready_resolution() -> None:
    """Validation reports each missing prerequisite and resolves metric IDs stably."""
    service, repository, target_repository, benchmark_repository = service_fixture(
        requirements={"a": [], "b": []}
    )
    created = await service.create_test(name="Test")
    test_id = created["test_definition_id"]
    result = await service.validate_test(test_id)
    assert result["valid"] is False
    assert "No target selected." in result["errors"]
    assert "No benchmark selected." in result["errors"]

    repository.tests[test_id].target_id = "missing"
    repository.tests[test_id].benchmark_id = "missing"
    result = await service.validate_test(test_id)
    assert any("Target not found" in error for error in result["errors"])
    assert any("Benchmark not found" in error for error in result["errors"])

    target_repository.targets["target-1"].enabled = False
    await service.update_test(
        test_id, changes={"target_id": "target-1", "benchmark_id": "benchmark-1"}
    )
    result = await service.validate_test(test_id)
    assert any("disabled" in error for error in result["errors"])
    target_repository.targets["target-1"].enabled = True
    target_repository.targets["target-1"].current_config_version = None
    result = await service.validate_test(test_id)
    assert any("not configured" in error for error in result["errors"])
    target_repository.targets["target-1"].current_config_version = 3
    benchmark_repository.cases = []
    result = await service.validate_test(test_id)
    assert "Benchmark contains no cases." in result["errors"]
    benchmark_repository.cases = [BenchmarkCase(case_id="case-1", query="Q")]

    with pytest.raises(ValueError, match="at least one"):
        await service.set_test_metrics(
            test_id,
            mode=EXPLICIT,
            selected_metrics=[],
            metric_parameters={},
            judge_config={},
            retrieval_config={},
        )
    await service.set_test_metrics(
        test_id,
        mode=ALL_AVAILABLE,
        selected_metrics=[],
        metric_parameters={},
        judge_config={},
        retrieval_config={},
    )
    result = await service.validate_test(test_id)
    assert result["valid"] is True
    assert result["configuration_status"] == READY
    assert result["resolved_metric_ids"] == ["a", "b"]


@pytest.mark.asyncio
async def test_validation_rejects_stale_metrics_and_empty_all_mode() -> None:
    """Validation keeps stale explicit selections and empty dynamic sets incomplete."""
    service, repository, _, _ = service_fixture(
        requirements={
            "metric.answer": [],
            "metric.citations": [{"capability": "citations"}],
        }
    )
    created = await service.create_test(name="Test")
    test_id = created["test_definition_id"]
    repository.tests[test_id].target_id = "target-1"
    repository.tests[test_id].benchmark_id = "benchmark-1"
    repository.tests[test_id].metric_selection_mode = EXPLICIT
    repository.selections[test_id] = [
        TestMetricSelectionRecord(
            test_metric_selection_id="selection-1",
            test_definition_id=test_id,
            metric_id="removed.metric",
            enabled=True,
        )
    ]
    result = await service.validate_test(test_id)
    assert any("no longer registered" in error for error in result["errors"])

    repository.selections[test_id] = [
        TestMetricSelectionRecord(
            test_metric_selection_id="selection-2",
            test_definition_id=test_id,
            metric_id="metric.citations",
            enabled=True,
        )
    ]
    result = await service.validate_test(test_id)
    assert any("unavailable" in error for error in result["errors"])

    repository.tests[test_id].metric_selection_mode = ALL_AVAILABLE
    repository.selections[test_id] = []
    result = await service.validate_test(test_id)
    assert result["valid"] is True
    assert result["resolved_metric_ids"] == ["metric.answer"]

    empty_service, empty_repository, _, _ = service_fixture(
        requirements={"metric.citations": [{"capability": "citations"}]}
    )
    empty_test = await empty_service.create_test(name="Empty")
    empty_id = empty_test["test_definition_id"]
    empty_repository.tests[empty_id].target_id = "target-1"
    empty_repository.tests[empty_id].benchmark_id = "benchmark-1"
    empty_repository.tests[empty_id].metric_selection_mode = ALL_AVAILABLE
    empty_result = await empty_service.validate_test(empty_id)
    assert empty_result["valid"] is False
    assert any("No registered metrics" in error for error in empty_result["errors"])


@pytest.mark.asyncio
async def test_start_run_narrows_nullable_ids_and_persists_immutable_snapshot() -> None:
    """Run creation snapshots identity, target config version, metrics, and cases."""
    service, repository, _, _ = service_fixture()
    test_id = await ready_test(service, repository)
    run = await service.start_run(test_id)
    assert run["status"] == "PENDING"
    assert run["test_definition_id"] == test_id
    assert run["target_id"] == "target-1"
    assert run["benchmark_id"] == "benchmark-1"
    stored_run = next(iter(repository.runs.values()))
    snapshot = repository.configs[stored_run.config_hash].canonical_config
    assert snapshot["test_definition_id"] == test_id
    assert snapshot["test_definition_hash"] == repository.tests[test_id].definition_hash
    assert snapshot["target"] == {
        "target_id": "target-1",
        "config_version": 3,
        "adapter_type": "python",
    }
    assert snapshot["metrics"]["resolved"][0]["metric_id"] == "metric.answer"
    assert len(repository.case_executions) == 1
    assert [event.event_type for event in repository.events] == [
        "RUN_CREATED",
        "RUN_QUEUED",
    ]
