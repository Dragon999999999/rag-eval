"""Application service for editable tests and evaluation-run lifecycle.

The service connects:

- TestRepository persistence
- TargetRepository target state/capabilities
- BenchmarkRepository benchmark/case state
- MetricRegistry metric definitions

It deliberately does not execute benchmark cases inline.  ``start_run`` creates
a durable immutable run snapshot and PENDING case executions.  A run executor /
worker should consume that persisted state, use CorpusPreparationService when
needed, invoke the target, persist observations, and compute metrics.

Metric definitions remain registry-backed.  Metric selections belong to the
test definition and are resolved to concrete metric versions when a run starts.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import yaml

from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.db.test_models import (
    CaseExecutionRecord,
    RunEventRecord,
    RunRecord,
    TestDefinitionRecord,
    TestMetricSelectionRecord,
)
from rag_eval.db.test_repository import TestRepository
from rag_eval.metrics.registry import MetricRegistry


EXPLICIT = "EXPLICIT"
ALL_AVAILABLE = "ALL_AVAILABLE"

INCOMPLETE = "INCOMPLETE"
READY = "READY"

RUN_CREATED = "CREATED"
RUN_PENDING = "PENDING"
RUN_RUNNING = "RUNNING"
RUN_PAUSING = "PAUSING"
RUN_PAUSED = "PAUSED"
RUN_INTERRUPTED = "INTERRUPTED"
RUN_COMPLETED = "COMPLETED"
RUN_FAILED = "FAILED"
RUN_CANCELLED = "CANCELLED"

TERMINAL_RUN_STATES = {
    RUN_COMPLETED,
    RUN_FAILED,
    RUN_CANCELLED,
}


class TestService:
    """Coordinate editable test configuration and durable evaluation runs."""

    def __init__(
        self,
        *,
        repository: TestRepository,
        target_repository: TargetRepository,
        benchmark_repository: BenchmarkRepository,
        metric_registry: MetricRegistry,
    ) -> None:
        """Bind persistence and registries required by the test domain."""
        self._repository = repository
        self._target_repository = target_repository
        self._benchmark_repository = benchmark_repository
        self._metric_registry = metric_registry

    # ------------------------------------------------------------------
    # Test CRUD
    # ------------------------------------------------------------------

    async def create_test(
        self,
        *,
        name: str,
        description: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Create an intentionally incomplete editable test."""
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError("test name must not be empty")

        record = TestDefinitionRecord(
            test_definition_id=f"test-{uuid4()}",
            name=normalized_name,
            description=description,
            target_id=None,
            benchmark_id=None,
            configuration_status=INCOMPLETE,
            metric_selection_mode=EXPLICIT,
            judge_config={},
            retrieval_config={},
            execution_config={},
            seed=None,
            tags=[],
            metadata_json=dict(metadata or {}),
            definition_hash=None,
        )

        created = await self._repository.create_test(record)
        return self._test_dict(created)

    async def list_tests(self) -> list[dict[str, Any]]:
        """List editable tests."""
        records = await self._repository.list_tests()
        return [self._test_dict(record) for record in records]

    async def get_test(
        self,
        test_id: str,
    ) -> dict[str, Any] | None:
        """Return one editable test."""
        record = await self._repository.get_test(test_id)
        if record is None:
            return None
        return self._test_dict(record)

    async def update_test(
        self,
        test_id: str,
        *,
        changes: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Apply a partial test update and recompute readiness/hash."""
        record = await self._repository.get_test(test_id)
        if record is None:
            raise KeyError(f"test not found: {test_id}")

        allowed = {
            "name",
            "description",
            "target_id",
            "benchmark_id",
            "execution_config",
            "seed",
            "tags",
            "metadata",
        }
        unknown = set(changes) - allowed
        if unknown:
            raise ValueError(
                "unsupported test fields: "
                + ", ".join(sorted(unknown))
            )

        target_id = changes.get("target_id", record.target_id)
        benchmark_id = changes.get(
            "benchmark_id",
            record.benchmark_id,
        )

        if target_id is not None:
            await self._require_target(str(target_id))

        if benchmark_id is not None:
            await self._require_benchmark(str(benchmark_id))

        kwargs: dict[str, Any] = {}

        if "name" in changes:
            value = changes["name"]
            if value is None or not str(value).strip():
                raise ValueError("test name must not be empty")
            kwargs["name"] = str(value).strip()

        if "description" in changes:
            # Repository currently uses None to mean "unchanged" for
            # description.  Preserve empty-string clearing as the supported
            # explicit clear representation.
            kwargs["description"] = changes["description"]

        if "target_id" in changes:
            if changes["target_id"] is None:
                kwargs["clear_target"] = True
            else:
                kwargs["target_id"] = str(changes["target_id"])

        if "benchmark_id" in changes:
            if changes["benchmark_id"] is None:
                kwargs["clear_benchmark"] = True
            else:
                kwargs["benchmark_id"] = str(
                    changes["benchmark_id"]
                )

        if "execution_config" in changes:
            kwargs["execution_config"] = dict(
                changes["execution_config"] or {}
            )

        if "seed" in changes:
            if changes["seed"] is None:
                kwargs["clear_seed"] = True
            else:
                kwargs["seed"] = int(changes["seed"])

        if "tags" in changes:
            kwargs["tags"] = list(changes["tags"] or [])

        if "metadata" in changes:
            kwargs["metadata"] = dict(
                changes["metadata"] or {}
            )

        await self._repository.update_test(
            test_id,
            **kwargs,
        )

        updated = await self._refresh_test_state(test_id)
        return self._test_dict(updated)

    async def delete_test(
        self,
        test_id: str,
    ) -> None:
        """Delete an editable test definition."""
        await self._repository.delete_test(test_id)

    # ------------------------------------------------------------------
    # Metric selection
    # ------------------------------------------------------------------

    async def get_test_metrics(
        self,
        test_id: str,
    ) -> dict[str, Any]:
        """Return registered metrics annotated for one test."""
        test = await self._require_test(test_id)
        selections = await self._repository.list_test_metric_selections(
            test_id
        )

        selected_by_id = {
            item.metric_id: item
            for item in selections
            if item.enabled
        }

        definitions = self._metric_definitions()
        applicability, warnings = await self._metric_applicability(
            test,
            definitions,
        )

        if test.metric_selection_mode == ALL_AVAILABLE:
            selected_ids = [
                metric_id
                for metric_id, result in applicability.items()
                if result["applicable"]
            ]
        else:
            selected_ids = sorted(selected_by_id)

        metric_rows: list[dict[str, Any]] = []
        applicable_ids: list[str] = []

        for definition in definitions:
            metric_id = self._metric_id(definition)
            result = applicability[metric_id]

            if result["applicable"]:
                applicable_ids.append(metric_id)

            selection = selected_by_id.get(metric_id)

            metric_rows.append(
                {
                    **self._definition_dict(definition),
                    "applicable": result["applicable"],
                    "selected": metric_id in selected_ids,
                    "unavailable_reason": result["reason"],
                    "parameters": (
                        dict(selection.parameters or {})
                        if selection is not None
                        else {}
                    ),
                }
            )

        return {
            "test_definition_id": test_id,
            "mode": test.metric_selection_mode,
            "metrics": metric_rows,
            "selected_metric_ids": sorted(selected_ids),
            "applicable_metric_ids": sorted(applicable_ids),
            "judge_config": dict(test.judge_config or {}),
            "retrieval_config": dict(
                test.retrieval_config or {}
            ),
            "warnings": warnings,
        }

    async def set_test_metrics(
        self,
        test_id: str,
        *,
        mode: str,
        selected_metrics: Sequence[str],
        metric_parameters: Mapping[
            str,
            Mapping[str, Any],
        ],
        judge_config: Mapping[str, Any],
        retrieval_config: Mapping[str, Any],
    ) -> dict[str, Any]:
        """Replace metric configuration for one test."""
        test = await self._require_test(test_id)

        normalized_mode = mode.upper()
        if normalized_mode not in {
            EXPLICIT,
            ALL_AVAILABLE,
        }:
            raise ValueError(
                "mode must be EXPLICIT or ALL_AVAILABLE"
            )

        definitions = self._metric_definitions()
        definitions_by_id = {
            self._metric_id(definition): definition
            for definition in definitions
        }

        requested = self._unique_strings(
            selected_metrics
        )

        unknown = [
            metric_id
            for metric_id in requested
            if metric_id not in definitions_by_id
        ]
        if unknown:
            raise ValueError(
                "unknown metrics: "
                + ", ".join(sorted(unknown))
            )

        applicability, _ = await self._metric_applicability(
            test,
            definitions,
        )

        inapplicable = [
            metric_id
            for metric_id in requested
            if not applicability[metric_id]["applicable"]
        ]
        if inapplicable:
            details = ", ".join(
                f"{metric_id}: "
                f"{applicability[metric_id]['reason']}"
                for metric_id in inapplicable
            )
            raise ValueError(
                "selected metrics are not applicable: "
                + details
            )

        if normalized_mode == EXPLICIT and not requested:
            raise ValueError(
                "EXPLICIT mode requires at least one metric"
            )

        selection_records: list[
            TestMetricSelectionRecord
        ] = []

        if normalized_mode == EXPLICIT:
            for metric_id in requested:
                definition = definitions_by_id[metric_id]
                selection_records.append(
                    TestMetricSelectionRecord(
                        test_metric_selection_id=(
                            f"tms-{uuid4()}"
                        ),
                        test_definition_id=test_id,
                        metric_id=metric_id,
                        metric_version=self._metric_version(
                            definition
                        ),
                        parameters=dict(
                            metric_parameters.get(
                                metric_id,
                                {},
                            )
                        ),
                        enabled=True,
                    )
                )

        await self._repository.replace_test_metric_selections(
            test_id,
            selection_records,
        )

        await self._repository.update_test(
            test_id,
            metric_selection_mode=normalized_mode,
            judge_config=dict(judge_config),
            retrieval_config=dict(retrieval_config),
            clear_definition_hash=True,
            configuration_status=INCOMPLETE,
        )

        await self._refresh_test_state(test_id)
        return await self.get_test_metrics(test_id)

    async def select_all_applicable_metrics(
        self,
        test_id: str,
    ) -> dict[str, Any]:
        """Switch a test to dynamically resolved ALL_AVAILABLE mode."""
        test = await self._require_test(test_id)

        await self._repository.clear_test_metric_selections(
            test_id
        )

        await self._repository.update_test(
            test_id,
            metric_selection_mode=ALL_AVAILABLE,
            judge_config=dict(test.judge_config or {}),
            retrieval_config=dict(
                test.retrieval_config or {}
            ),
            clear_definition_hash=True,
            configuration_status=INCOMPLETE,
        )

        await self._refresh_test_state(test_id)
        return await self.get_test_metrics(test_id)

    # ------------------------------------------------------------------
    # YAML import/export
    # ------------------------------------------------------------------

    async def import_test_yaml(
        self,
        test_id: str,
        yaml_text: str,
    ) -> dict[str, Any]:
        """Import portable YAML without preserving the source file.

        Unknown and inapplicable metrics are ignored with warnings.  Imported
        target/benchmark IDs fill currently unset values.  Conflicting IDs are
        reported to the frontend rather than replacing existing values.
        """
        test = await self._require_test(test_id)

        try:
            loaded = yaml.safe_load(yaml_text)
        except yaml.YAMLError as exc:
            raise ValueError(
                f"invalid YAML: {exc}"
            ) from exc

        if loaded is None:
            loaded = {}

        if not isinstance(loaded, dict):
            raise ValueError(
                "test YAML root must be a mapping"
            )

        detected_target_id = self._optional_string(
            loaded.get("target_id", loaded.get("target"))
        )
        detected_benchmark_id = self._optional_string(
            loaded.get(
                "benchmark_id",
                loaded.get("benchmark"),
            )
        )

        target_conflict = bool(
            detected_target_id
            and test.target_id
            and detected_target_id != test.target_id
        )
        benchmark_conflict = bool(
            detected_benchmark_id
            and test.benchmark_id
            and detected_benchmark_id
            != test.benchmark_id
        )

        warnings: list[str] = []
        update_changes: dict[str, Any] = {}

        if detected_target_id:
            target = await self._target_repository.get_target(
                detected_target_id
            )
            if target is None:
                warnings.append(
                    "YAML target_id "
                    f"'{detected_target_id}' does not exist "
                    "and was not applied."
                )
            elif test.target_id is None:
                update_changes["target_id"] = (
                    detected_target_id
                )
            elif target_conflict:
                warnings.append(
                    "YAML contains a different target; "
                    "current target was kept pending confirmation."
                )

        if detected_benchmark_id:
            benchmark = (
                await self._benchmark_repository.get_benchmark(
                    detected_benchmark_id
                )
            )
            if benchmark is None:
                warnings.append(
                    "YAML benchmark_id "
                    f"'{detected_benchmark_id}' does not exist "
                    "and was not applied."
                )
            elif test.benchmark_id is None:
                update_changes["benchmark_id"] = (
                    detected_benchmark_id
                )
            elif benchmark_conflict:
                warnings.append(
                    "YAML contains a different benchmark; "
                    "current benchmark was kept pending confirmation."
                )

        if update_changes:
            await self.update_test(
                test_id,
                changes=update_changes,
            )
            test = await self._require_test(test_id)

        mode, requested_metrics = self._parse_yaml_metrics(
            loaded.get("metrics")
        )

        raw_parameters = loaded.get(
            "parameters",
            loaded.get("metric_parameters", {}),
        )
        if not isinstance(raw_parameters, dict):
            raise ValueError(
                "parameters must be a mapping"
            )

        judge_config = loaded.get(
            "judge",
            loaded.get("judge_config", {}),
        )
        if not isinstance(judge_config, dict):
            raise ValueError(
                "judge configuration must be a mapping"
            )

        retrieval_config = loaded.get(
            "retrieval",
            loaded.get("retrieval_config", {}),
        )
        if not isinstance(retrieval_config, dict):
            raise ValueError(
                "retrieval configuration must be a mapping"
            )

        definitions = self._metric_definitions()
        definitions_by_id = {
            self._metric_id(definition): definition
            for definition in definitions
        }

        ignored: list[str] = []
        unavailable: list[str] = []

        if mode == ALL_AVAILABLE:
            recognized: list[str] = []
        else:
            recognized = []
            for metric_id in requested_metrics:
                if metric_id not in definitions_by_id:
                    ignored.append(metric_id)
                    warnings.append(
                        f"Unknown metric '{metric_id}' was ignored."
                    )
                else:
                    recognized.append(metric_id)

            applicability, _ = await self._metric_applicability(
                test,
                definitions,
            )

            applicable_recognized: list[str] = []
            for metric_id in recognized:
                if applicability[metric_id]["applicable"]:
                    applicable_recognized.append(metric_id)
                else:
                    unavailable.append(metric_id)
                    warnings.append(
                        f"Metric '{metric_id}' is unavailable: "
                        f"{applicability[metric_id]['reason']}"
                    )

            recognized = applicable_recognized

        if mode == EXPLICIT and not recognized:
            # Preserve a valid incomplete configuration instead of failing the
            # entire import because every requested metric was unknown or
            # unavailable.
            await self._repository.clear_test_metric_selections(
                test_id
            )
            await self._repository.update_test(
                test_id,
                metric_selection_mode=EXPLICIT,
                judge_config=dict(judge_config),
                retrieval_config=dict(retrieval_config),
                clear_definition_hash=True,
                configuration_status=INCOMPLETE,
            )
            await self._refresh_test_state(test_id)
        else:
            await self.set_test_metrics(
                test_id,
                mode=mode,
                selected_metrics=recognized,
                metric_parameters={
                    key: value
                    for key, value in raw_parameters.items()
                    if isinstance(value, dict)
                },
                judge_config=judge_config,
                retrieval_config=retrieval_config,
            )

        return {
            "applied": True,
            "mode": mode,
            "selected_metrics": (
                recognized
                if mode == EXPLICIT
                else (
                    await self.get_test_metrics(test_id)
                )["selected_metric_ids"]
            ),
            "ignored_metrics": ignored,
            "unavailable_metrics": unavailable,
            "detected_target_id": detected_target_id,
            "detected_benchmark_id": detected_benchmark_id,
            "target_conflict": target_conflict,
            "benchmark_conflict": benchmark_conflict,
            "warnings": warnings,
        }

    async def export_test_yaml(
        self,
        test_id: str,
    ) -> str:
        """Serialize the current portable test configuration to YAML."""
        test = await self._require_test(test_id)
        selections = (
            await self._repository.list_test_metric_selections(
                test_id,
                enabled_only=True,
            )
        )

        if test.metric_selection_mode == ALL_AVAILABLE:
            metrics_value: str | list[str] = "all"
        else:
            metrics_value = [
                item.metric_id
                for item in selections
            ]

        parameters = {
            item.metric_id: dict(item.parameters or {})
            for item in selections
            if item.parameters
        }

        payload: dict[str, Any] = {
            "metrics": metrics_value,
        }

        if test.target_id is not None:
            payload["target_id"] = test.target_id

        if test.benchmark_id is not None:
            payload["benchmark_id"] = test.benchmark_id

        if parameters:
            payload["parameters"] = parameters

        if test.judge_config:
            payload["judge"] = dict(test.judge_config)

        if test.retrieval_config:
            payload["retrieval"] = dict(
                test.retrieval_config
            )

        return yaml.safe_dump(
            payload,
            sort_keys=False,
            allow_unicode=True,
        )

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    async def validate_test(
        self,
        test_id: str,
    ) -> dict[str, Any]:
        """Validate whether the editable test can start a run."""
        test = await self._require_test(test_id)

        errors: list[str] = []
        warnings: list[str] = []

        target_valid = False
        benchmark_valid = False

        if test.target_id is None:
            errors.append("No target selected.")
        else:
            target = await self._target_repository.get_target(
                test.target_id
            )
            if target is None:
                errors.append(
                    f"Target not found: {test.target_id}"
                )
            elif not getattr(target, "enabled", True):
                errors.append(
                    f"Target is disabled: {test.target_id}"
                )
            elif getattr(
                target,
                "current_config_version",
                None,
            ) is None:
                errors.append(
                    f"Target is not configured: {test.target_id}"
                )
            else:
                target_valid = True

        if test.benchmark_id is None:
            errors.append("No benchmark selected.")
        else:
            benchmark = (
                await self._benchmark_repository.get_benchmark(
                    test.benchmark_id
                )
            )
            if benchmark is None:
                errors.append(
                    f"Benchmark not found: {test.benchmark_id}"
                )
            else:
                case_records = (
                    await self._benchmark_repository.list_cases(
                        test.benchmark_id
                    )
                )
                if not case_records:
                    errors.append(
                        "Benchmark contains no cases."
                    )
                else:
                    benchmark_valid = True

        resolved_metrics: list[str] = []
        metrics_valid = False

        definitions = self._metric_definitions()
        definitions_by_id = {
            self._metric_id(definition): definition
            for definition in definitions
        }

        applicability, applicability_warnings = (
            await self._metric_applicability(
                test,
                definitions,
            )
        )
        warnings.extend(applicability_warnings)

        if test.metric_selection_mode == ALL_AVAILABLE:
            resolved_metrics = sorted(
                metric_id
                for metric_id, result
                in applicability.items()
                if result["applicable"]
            )
            if resolved_metrics:
                metrics_valid = True
            else:
                errors.append(
                    "No registered metrics are applicable "
                    "to this test."
                )

        elif test.metric_selection_mode == EXPLICIT:
            selections = (
                await self._repository.list_test_metric_selections(
                    test_id,
                    enabled_only=True,
                )
            )

            if not selections:
                errors.append("No metrics selected.")
            else:
                for selection in selections:
                    metric_id = selection.metric_id
                    if metric_id not in definitions_by_id:
                        errors.append(
                            f"Selected metric is no longer "
                            f"registered: {metric_id}"
                        )
                        continue

                    result = applicability[metric_id]
                    if not result["applicable"]:
                        errors.append(
                            f"Metric '{metric_id}' is unavailable: "
                            f"{result['reason']}"
                        )
                        continue

                    resolved_metrics.append(metric_id)

                metrics_valid = (
                    bool(resolved_metrics)
                    and not any(
                        error.startswith(
                            "Selected metric"
                        )
                        or error.startswith("Metric '")
                        for error in errors
                    )
                )
        else:
            errors.append(
                "Unknown metric selection mode: "
                f"{test.metric_selection_mode}"
            )

        valid = (
            target_valid
            and benchmark_valid
            and metrics_valid
            and not errors
        )

        return {
            "valid": valid,
            "configuration_status": (
                READY if valid else INCOMPLETE
            ),
            "target_valid": target_valid,
            "benchmark_valid": benchmark_valid,
            "metrics_valid": metrics_valid,
            "resolved_metric_ids": sorted(
                resolved_metrics
            ),
            "errors": errors,
            "warnings": warnings,
        }

    # ------------------------------------------------------------------
    # Run creation / listing
    # ------------------------------------------------------------------

    async def start_run(
        self,
        test_id: str,
    ) -> dict[str, Any]:
        """Create a durable PENDING run from the current test snapshot."""
        test = await self._require_test(test_id)
        validation = await self.validate_test(test_id)

        if not validation["valid"]:
            raise ValueError(
                "test is not ready: "
                + "; ".join(validation["errors"])
            )

        target_id = test.target_id
        benchmark_id = test.benchmark_id

        if target_id is None:
            raise ValueError("test has no target configured")

        if benchmark_id is None:
            raise ValueError("test has no benchmark configured")

        benchmark = (
            await self._benchmark_repository.get_benchmark(
                benchmark_id
            )
        )
        if benchmark is None:
            raise KeyError(
                f"benchmark not found: {benchmark_id}"
            )

        target = await self._target_repository.get_target(
            target_id
        )
        if target is None:
            raise KeyError(
                f"target not found: {target_id}"
            )

        cases = await self._benchmark_repository.list_cases(
            benchmark_id
        )

        snapshot = await self._build_run_snapshot(
            test,
            target_id=target_id,
            benchmark_id=benchmark_id,
            target=target,
            benchmark=benchmark,
            resolved_metric_ids=validation[
                "resolved_metric_ids"
            ],
        )
        config_hash = self._hash_payload(snapshot)

        run_id = f"run-{uuid4()}"
        run = RunRecord(
            run_id=run_id,
            name=test.name,
            status=RUN_PENDING,
            status_reason=None,
            config_hash=config_hash,
            target_id=test.target_id,
            benchmark_id=test.benchmark_id,
            test_definition_id=test.test_definition_id,
            started_at=None,
            finished_at=None,
            paused_at=None,
            interrupted_at=None,
            seed=test.seed,
            rag_eval_version=None,
            tags=list(test.tags or []),
            metadata_json={
                **dict(test.metadata_json or {}),
                "test_definition_hash": (
                    test.definition_hash
                ),
            },
        )

        await self._repository.create_run(
            run,
            snapshot,
        )

        for case in cases:
            case_id = str(
                getattr(case, "case_id")
            )
            await self._repository.create_case_execution(
                CaseExecutionRecord(
                    case_execution_id=f"case-exec-{uuid4()}",
                    run_id=run_id,
                    case_id=case_id,
                    status=RUN_PENDING,
                    started_at=None,
                    finished_at=None,
                    metadata_json={},
                )
            )

        await self._append_event(
            run_id,
            "RUN_CREATED",
            {
                "test_definition_id": test_id,
                "case_count": len(cases),
                "config_hash": config_hash,
            },
        )

        await self._append_event(
            run_id,
            "RUN_QUEUED",
            {},
        )

        return await self._run_detail(run_id)

    async def list_test_runs(
        self,
        test_id: str,
    ) -> list[dict[str, Any]]:
        """List historical runs for a test."""
        await self._require_test(test_id)
        runs = await self._repository.list_runs(
            test_definition_id=test_id
        )

        return [
            await self._run_detail(record.run_id)
            for record in runs
        ]

    async def get_run(
        self,
        run_id: str,
    ) -> dict[str, Any] | None:
        """Return one run."""
        run = await self._repository.get_run(run_id)
        if run is None:
            return None
        return await self._run_detail(run_id)

    async def get_run_status(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Return lightweight status/progress for polling."""
        run = await self._require_run(run_id)
        counts = await self._repository.get_run_case_counts(
            run_id
        )

        total = sum(counts.values())
        complete = counts.get(RUN_COMPLETED, 0)
        failed = counts.get(RUN_FAILED, 0)
        running = counts.get(RUN_RUNNING, 0)
        pending = (
            counts.get(RUN_PENDING, 0)
            + counts.get(RUN_CREATED, 0)
        )

        done = complete + failed
        progress = (
            (done / total) * 100.0
            if total
            else 0.0
        )

        elapsed_seconds: float | None = None
        if run.started_at is not None:
            end = run.finished_at or datetime.now(UTC)
            elapsed_seconds = max(
                0.0,
                (end - run.started_at).total_seconds(),
            )

        return {
            "run_id": run.run_id,
            "status": run.status,
            "status_reason": run.status_reason,
            "total_cases": total,
            "complete_cases": complete,
            "failed_cases": failed,
            "pending_cases": pending,
            "running_cases": running,
            "progress_percent": progress,
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "paused_at": run.paused_at,
            "interrupted_at": run.interrupted_at,
            "elapsed_seconds": elapsed_seconds,
        }

    # ------------------------------------------------------------------
    # Run lifecycle
    # ------------------------------------------------------------------

    async def pause_run(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Request graceful pause of a pending/running run."""
        run = await self._require_run(run_id)

        if run.status == RUN_PAUSED:
            return await self._run_detail(run_id)

        if run.status in TERMINAL_RUN_STATES:
            raise RuntimeError(
                f"cannot pause run in state {run.status}"
            )

        now = datetime.now(UTC)

        if run.status in {RUN_CREATED, RUN_PENDING}:
            new_status = RUN_PAUSED
            paused_at = now
            event = "RUN_PAUSED"
        elif run.status == RUN_RUNNING:
            new_status = RUN_PAUSING
            paused_at = None
            event = "RUN_PAUSE_REQUESTED"
        elif run.status == RUN_PAUSING:
            return await self._run_detail(run_id)
        elif run.status == RUN_INTERRUPTED:
            raise RuntimeError(
                "interrupted runs must be recovered, not paused"
            )
        else:
            raise RuntimeError(
                f"cannot pause run in state {run.status}"
            )

        await self._repository.update_run_lifecycle(
            run_id,
            status=new_status,
            paused_at=paused_at,
        )
        await self._append_event(
            run_id,
            event,
            {},
        )

        return await self._run_detail(run_id)

    async def resume_run(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Resume a deliberately paused run."""
        run = await self._require_run(run_id)

        if run.status != RUN_PAUSED:
            raise RuntimeError(
                "only PAUSED runs can be resumed"
            )

        await self._repository.update_run_lifecycle(
            run_id,
            status=RUN_PENDING,
            clear_paused_at=True,
            clear_status_reason=True,
        )

        await self._append_event(
            run_id,
            "RUN_RESUMED",
            {},
        )

        return await self._run_detail(run_id)

    async def recover_run(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Prepare an interrupted run for worker-side recovery.

        Completed case executions are untouched.  RUNNING case executions are
        marked INTERRUPTED so the executor can inspect their latest attempts and
        perform request recovery or append a retry attempt.
        """
        run = await self._require_run(run_id)

        if run.status != RUN_INTERRUPTED:
            raise RuntimeError(
                "only INTERRUPTED runs can be recovered"
            )

        cases = await self._repository.list_case_executions(
            run_id
        )

        recovered_cases = 0

        for case in cases:
            if case.status == RUN_RUNNING:
                await self._repository.update_case_execution_status(
                    case.case_execution_id,
                    RUN_INTERRUPTED,
                )
                recovered_cases += 1

        await self._repository.update_run_lifecycle(
            run_id,
            status=RUN_PENDING,
            clear_interrupted_at=True,
            clear_status_reason=True,
        )

        await self._append_event(
            run_id,
            "RUN_RECOVERY_REQUESTED",
            {
                "interrupted_case_count": recovered_cases,
            },
        )

        return await self._run_detail(run_id)

    async def cancel_run(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Permanently cancel a nonterminal run."""
        run = await self._require_run(run_id)

        if run.status == RUN_CANCELLED:
            return await self._run_detail(run_id)

        if run.status == RUN_COMPLETED:
            raise RuntimeError(
                "completed runs cannot be cancelled"
            )

        now = datetime.now(UTC)

        await self._repository.update_run_lifecycle(
            run_id,
            status=RUN_CANCELLED,
            finished_at=now,
            clear_paused_at=True,
            clear_interrupted_at=True,
        )

        cases = await self._repository.list_case_executions(
            run_id
        )
        for case in cases:
            if case.status not in {
                RUN_COMPLETED,
                RUN_FAILED,
                RUN_CANCELLED,
            }:
                await self._repository.update_case_execution_status(
                    case.case_execution_id,
                    RUN_CANCELLED,
                    finished_at=now,
                )

        await self._append_event(
            run_id,
            "RUN_CANCELLED",
            {},
        )

        return await self._run_detail(run_id)

    async def list_run_events(
        self,
        run_id: str,
    ) -> list[dict[str, Any]]:
        """List append-only lifecycle events."""
        await self._require_run(run_id)
        events = await self._repository.list_run_events(
            run_id
        )
        return [
            {
                "run_event_id": event.run_event_id,
                "run_id": event.run_id,
                "event_type": event.event_type,
                "payload": dict(event.payload or {}),
                "created_at": event.created_at,
            }
            for event in events
        ]

    # ------------------------------------------------------------------
    # Run execution details/results
    # ------------------------------------------------------------------

    async def list_run_cases(
        self,
        run_id: str,
    ) -> list[dict[str, Any]]:
        """List persisted logical case executions."""
        await self._require_run(run_id)
        cases = await self._repository.list_case_executions(
            run_id
        )

        result: list[dict[str, Any]] = []
        for case in cases:
            attempts = await self._repository.list_attempts(
                case.case_execution_id
            )

            result.append(
                {
                    "case_execution_id": case.case_execution_id,
                    "run_id": case.run_id,
                    "case_id": case.case_id,
                    "status": case.status,
                    "started_at": case.started_at,
                    "finished_at": case.finished_at,
                    "metadata": dict(
                        case.metadata_json or {}
                    ),
                    # Benchmark detail enrichment can be added here once the
                    # BenchmarkRepository exposes get_case(case_id).
                    "query": None,
                    "reference_answer": None,
                    "answerability": None,
                    "tags": [],
                    "attempt_count": len(attempts),
                }
            )

        return result

    async def list_case_attempts(
        self,
        run_id: str,
        case_execution_id: str,
    ) -> list[dict[str, Any]]:
        """List attempts and verify that the case belongs to the run."""
        await self._require_run(run_id)

        case = await self._repository.get_case_execution(
            case_execution_id
        )
        if case is None or case.run_id != run_id:
            raise KeyError(
                f"case execution not found in run: "
                f"{case_execution_id}"
            )

        attempts = await self._repository.list_attempts(
            case_execution_id
        )

        return [
            {
                "attempt_id": attempt.attempt_id,
                "case_execution_id": (
                    attempt.case_execution_id
                ),
                "attempt_number": attempt.attempt_number,
                "request_id": attempt.request_id,
                "idempotency_key": attempt.idempotency_key,
                "canonical_request_hash": (
                    attempt.canonical_request_hash
                ),
                "status": attempt.status,
                "started_at": attempt.started_at,
                "finished_at": attempt.finished_at,
                "retryable": attempt.retryable,
                "error_summary": attempt.error_summary,
                "metadata": dict(
                    attempt.metadata_json or {}
                ),
            }
            for attempt in attempts
        ]

    async def get_run_results(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        """Return individual and aggregate metric results."""
        await self._require_run(run_id)

        metrics = await self._repository.list_metric_results(
            run_id
        )
        aggregates = await self._repository.list_aggregates(
            run_id
        )

        return {
            "run_id": run_id,
            "metrics": [
                {
                    "metric_result_id": item.metric_result_id,
                    "run_id": item.run_id,
                    "case_execution_id": (
                        item.case_execution_id
                    ),
                    "case_id": item.case_id,
                    "metric_id": item.metric_id,
                    "metric_version": item.metric_version,
                    "value": item.value,
                    "status": item.status,
                    "reason": item.reason,
                    "details": dict(item.details or {}),
                    "payload": dict(item.payload or {}),
                    "created_at": item.created_at,
                }
                for item in metrics
            ],
            "aggregates": [
                {
                    "aggregate_metric_result_id": (
                        item.aggregate_metric_result_id
                    ),
                    "run_id": item.run_id,
                    "metric_id": item.metric_id,
                    "metric_version": item.metric_version,
                    "aggregation": item.aggregation,
                    "value": item.value,
                    "status": item.status,
                    "reason": item.reason,
                    "details": dict(item.details or {}),
                    "created_at": item.created_at,
                }
                for item in aggregates
            ],
        }

    # ------------------------------------------------------------------
    # Internal test-state helpers
    # ------------------------------------------------------------------

    async def _refresh_test_state(
        self,
        test_id: str,
    ) -> TestDefinitionRecord:
        """Recompute readiness and current editable definition hash."""
        test = await self._require_test(test_id)
        validation = await self.validate_test(test_id)

        if validation["valid"]:
            payload = await self._editable_test_payload(
                test,
                validation["resolved_metric_ids"],
            )
            definition_hash = self._hash_payload(payload)

            return await self._repository.update_test(
                test_id,
                configuration_status=READY,
                definition_hash=definition_hash,
            )

        return await self._repository.update_test(
            test_id,
            configuration_status=INCOMPLETE,
            clear_definition_hash=True,
        )

    async def _editable_test_payload(
        self,
        test: TestDefinitionRecord,
        resolved_metric_ids: Sequence[str],
    ) -> dict[str, Any]:
        """Build deterministic current editable configuration payload."""
        selections = (
            await self._repository.list_test_metric_selections(
                test.test_definition_id,
                enabled_only=True,
            )
        )

        parameters = {
            item.metric_id: dict(item.parameters or {})
            for item in selections
        }

        return {
            "target_id": test.target_id,
            "benchmark_id": test.benchmark_id,
            "metric_selection_mode": (
                test.metric_selection_mode
            ),
            "resolved_metric_ids": sorted(
                resolved_metric_ids
            ),
            "metric_parameters": parameters,
            "judge_config": dict(
                test.judge_config or {}
            ),
            "retrieval_config": dict(
                test.retrieval_config or {}
            ),
            "execution_config": dict(
                test.execution_config or {}
            ),
            "seed": test.seed,
        }

    async def _build_run_snapshot(
        self,
        test: TestDefinitionRecord,
        *,
        target_id: str,
        benchmark_id: str,
        target: Any,
        benchmark: Any,
        resolved_metric_ids: Sequence[str],
    ) -> dict[str, Any]:
        """Resolve mutable test configuration to an immutable run snapshot."""
        selections = (
            await self._repository.list_test_metric_selections(
                test.test_definition_id,
                enabled_only=True,
            )
        )
        selected_by_id = {
            item.metric_id: item
            for item in selections
        }

        definitions = {
            self._metric_id(definition): definition
            for definition in self._metric_definitions()
        }

        resolved_metrics: list[dict[str, Any]] = []
        for metric_id in sorted(resolved_metric_ids):
            definition = definitions[metric_id]
            selection = selected_by_id.get(metric_id)

            resolved_metrics.append(
                {
                    "metric_id": metric_id,
                    "version": self._metric_version(
                        definition
                    ),
                    "parameters": (
                        dict(selection.parameters or {})
                        if selection is not None
                        else {}
                    ),
                }
            )

        current_target_config = (
            await self._target_repository.get_current_config_version(
                target_id
            )
        )

        target_snapshot = {
            "target_id": target_id,
            "config_version": (
                getattr(
                    current_target_config,
                    "version",
                    None,
                )
                if current_target_config is not None
                else getattr(
                    target,
                    "current_config_version",
                    None,
                )
            ),
            "adapter_type": getattr(
                target,
                "adapter_type",
                None,
            ),
        }

        benchmark_snapshot = {
            "benchmark_id": benchmark_id,
            "version": getattr(
                benchmark,
                "version",
                None,
            ),
            "content_hash": getattr(
                benchmark,
                "content_hash",
                None,
            ),
        }

        return {
            "schema_version": "1.0",
            "test_definition_id": (
                test.test_definition_id
            ),
            "test_definition_hash": test.definition_hash,
            "target": target_snapshot,
            "benchmark": benchmark_snapshot,
            "metrics": {
                "mode": test.metric_selection_mode,
                "resolved": resolved_metrics,
                "judge_config": dict(
                    test.judge_config or {}
                ),
                "retrieval_config": dict(
                    test.retrieval_config or {}
                ),
            },
            "execution_config": dict(
                test.execution_config or {}
            ),
            "seed": test.seed,
        }

    # ------------------------------------------------------------------
    # Metric registry / applicability
    # ------------------------------------------------------------------

    def _metric_definitions(self) -> list[Any]:
        """Return all registered metric definitions."""
        return self._metric_registry.list_metrics()

    async def _metric_applicability(
        self,
        test: TestDefinitionRecord,
        definitions: Sequence[Any],
    ) -> tuple[
        dict[str, dict[str, Any]],
        list[str],
    ]:
        """Evaluate common metric requirements against current test state.

        Requirement payloads are intentionally interpreted conservatively.
        Recognized forms include:

        {"capability": "citations"}
        {"target_capability": "retrieval"}
        {"benchmark_field": "reference_answer"}

        Unknown requirement shapes are not rejected; they generate a warning so
        individual metric implementations can perform final availability checks
        during execution.
        """
        warnings: list[str] = []

        capabilities: Any | None = None
        if test.target_id is not None:
            try:
                capabilities = (
                    await self._target_repository.get_capabilities(
                        test.target_id
                    )
                )
            except (KeyError, ValueError):
                capabilities = None

        benchmark: Any | None = None
        cases: Sequence[Any] = []
        if test.benchmark_id is not None:
            benchmark = (
                await self._benchmark_repository.get_benchmark(
                    test.benchmark_id
                )
            )
            if benchmark is not None:
                cases = (
                    await self._benchmark_repository.list_cases(
                        test.benchmark_id
                    )
                )

        results: dict[str, dict[str, Any]] = {}

        for definition in definitions:
            metric_id = self._metric_id(definition)
            requirements = self._metric_requirements(
                definition
            )

            applicable = True
            reasons: list[str] = []

            for requirement in requirements:
                if not isinstance(requirement, dict):
                    warnings.append(
                        f"Metric '{metric_id}' has an unsupported "
                        "non-object requirement declaration."
                    )
                    continue

                capability_name = requirement.get(
                    "capability",
                    requirement.get(
                        "target_capability"
                    ),
                )
                if isinstance(capability_name, str):
                    if test.target_id is None:
                        applicable = False
                        reasons.append("no target selected")
                    elif capabilities is None:
                        applicable = False
                        reasons.append(
                            "target capabilities are unavailable"
                        )
                    elif not self._capability_enabled(
                        capabilities,
                        capability_name,
                    ):
                        applicable = False
                        reasons.append(
                            "target does not expose "
                            f"{capability_name}"
                        )
                    continue

                benchmark_field = requirement.get(
                    "benchmark_field"
                )
                if isinstance(benchmark_field, str):
                    if benchmark is None:
                        applicable = False
                        reasons.append(
                            "no benchmark selected"
                        )
                    elif not self._benchmark_field_available(
                        cases,
                        benchmark_field,
                    ):
                        applicable = False
                        reasons.append(
                            "benchmark does not provide "
                            f"{benchmark_field}"
                        )
                    continue

                if requirement:
                    warnings.append(
                        f"Metric '{metric_id}' has a requirement "
                        "that is deferred to runtime validation."
                    )

            results[metric_id] = {
                "applicable": applicable,
                "reason": (
                    "; ".join(reasons)
                    if reasons
                    else None
                ),
            }

        return results, warnings

    @staticmethod
    def _capability_enabled(
        capabilities: Any,
        name: str,
    ) -> bool:
        """Read simple or dotted capability names."""
        current = capabilities

        for part in name.split("."):
            if isinstance(current, dict):
                if part not in current:
                    return False
                current = current[part]
            else:
                if not hasattr(current, part):
                    return False
                current = getattr(current, part)

        return bool(current)

    @staticmethod
    def _benchmark_field_available(
        cases: Sequence[Any],
        field_name: str,
    ) -> bool:
        """Return whether at least one benchmark case exposes a field."""
        for case in cases:
            if isinstance(case, dict):
                value = case.get(field_name)
            else:
                value = getattr(
                    case,
                    field_name,
                    None,
                )

            if value not in (None, "", [], {}):
                return True

        return False

    # ------------------------------------------------------------------
    # Formatting / utility helpers
    # ------------------------------------------------------------------

    async def _run_detail(
        self,
        run_id: str,
    ) -> dict[str, Any]:
        run = await self._require_run(run_id)
        counts = await self._repository.get_run_case_counts(
            run_id
        )

        return {
            "run_id": run.run_id,
            "name": run.name,
            "status": run.status,
            "status_reason": run.status_reason,
            "config_hash": run.config_hash,
            "target_id": run.target_id,
            "benchmark_id": run.benchmark_id,
            "test_definition_id": (
                run.test_definition_id
            ),
            "started_at": run.started_at,
            "finished_at": run.finished_at,
            "paused_at": run.paused_at,
            "interrupted_at": run.interrupted_at,
            "seed": run.seed,
            "rag_eval_version": run.rag_eval_version,
            "tags": list(run.tags or []),
            "metadata": dict(
                run.metadata_json or {}
            ),
            "created_at": run.created_at,
            "updated_at": run.updated_at,
            "total_cases": sum(counts.values()),
            "complete_cases": counts.get(
                RUN_COMPLETED,
                0,
            ),
            "failed_cases": counts.get(
                RUN_FAILED,
                0,
            ),
            "pending_cases": (
                counts.get(RUN_PENDING, 0)
                + counts.get(RUN_CREATED, 0)
            ),
            "running_cases": counts.get(
                RUN_RUNNING,
                0,
            ),
        }

    @staticmethod
    def _test_dict(
        record: TestDefinitionRecord,
    ) -> dict[str, Any]:
        return {
            "test_definition_id": (
                record.test_definition_id
            ),
            "name": record.name,
            "description": record.description,
            "configuration_status": (
                record.configuration_status
            ),
            "target_id": record.target_id,
            "benchmark_id": record.benchmark_id,
            "metric_selection_mode": (
                record.metric_selection_mode
            ),
            "judge_config": dict(
                record.judge_config or {}
            ),
            "retrieval_config": dict(
                record.retrieval_config or {}
            ),
            "execution_config": dict(
                record.execution_config or {}
            ),
            "seed": record.seed,
            "tags": list(record.tags or []),
            "metadata": dict(
                record.metadata_json or {}
            ),
            "definition_hash": record.definition_hash,
            "created_at": record.created_at,
            "updated_at": record.updated_at,
        }

    async def _append_event(
        self,
        run_id: str,
        event_type: str,
        payload: Mapping[str, Any],
    ) -> RunEventRecord:
        return await self._repository.append_run_event(
            RunEventRecord(
                run_event_id=f"evt-{uuid4()}",
                run_id=run_id,
                event_type=event_type,
                payload=dict(payload),
            )
        )

    async def _require_test(
        self,
        test_id: str,
    ) -> TestDefinitionRecord:
        record = await self._repository.get_test(test_id)
        if record is None:
            raise KeyError(f"test not found: {test_id}")
        return record

    async def _require_run(
        self,
        run_id: str,
    ) -> RunRecord:
        record = await self._repository.get_run(run_id)
        if record is None:
            raise KeyError(f"run not found: {run_id}")
        return record

    async def _require_target(
        self,
        target_id: str,
    ) -> Any:
        record = await self._target_repository.get_target(
            target_id
        )
        if record is None:
            raise ValueError(
                f"target not found: {target_id}"
            )
        return record

    async def _require_benchmark(
        self,
        benchmark_id: str,
    ) -> Any:
        record = (
            await self._benchmark_repository.get_benchmark(
                benchmark_id
            )
        )
        if record is None:
            raise ValueError(
                f"benchmark not found: {benchmark_id}"
            )
        return record

    @staticmethod
    def _hash_payload(
        payload: Mapping[str, Any],
    ) -> str:
        encoded = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")

        return hashlib.sha256(encoded).hexdigest()

    @staticmethod
    def _unique_strings(
        values: Sequence[str],
    ) -> list[str]:
        seen: set[str] = set()
        result: list[str] = []

        for raw in values:
            value = str(raw).strip()
            if not value or value in seen:
                continue
            seen.add(value)
            result.append(value)

        return result

    @staticmethod
    def _optional_string(
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        result = str(value).strip()
        return result or None

    @classmethod
    def _parse_yaml_metrics(
        cls,
        value: Any,
    ) -> tuple[str, list[str]]:
        if isinstance(value, str):
            if value.strip().lower() == "all":
                return ALL_AVAILABLE, []
            return EXPLICIT, [value.strip()]

        if value is None:
            return EXPLICIT, []

        if isinstance(value, list):
            return EXPLICIT, cls._unique_strings(
                [str(item) for item in value]
            )

        raise ValueError(
            "metrics must be 'all' or a list of metric IDs"
        )

    @staticmethod
    def _metric_id(
        definition: Any,
    ) -> str:
        if isinstance(definition, dict):
            return str(definition["metric_id"])
        return str(definition.metric_id)

    @staticmethod
    def _metric_version(
        definition: Any,
    ) -> str:
        if isinstance(definition, dict):
            return str(
                definition.get("version", "1")
            )
        return str(
            getattr(definition, "version", "1")
        )

    @staticmethod
    def _metric_requirements(
        definition: Any,
    ) -> list[Any]:
        if isinstance(definition, dict):
            value = definition.get(
                "requirements",
                [],
            )
        else:
            value = getattr(
                definition,
                "requirements",
                [],
            )

        return list(value or [])

    @classmethod
    def _definition_dict(
        cls,
        definition: Any,
    ) -> dict[str, Any]:
        if isinstance(definition, dict):
            return {
                "metric_id": cls._metric_id(
                    definition
                ),
                "version": cls._metric_version(
                    definition
                ),
                "scope": str(
                    definition.get("scope", "case")
                ),
                "requirements": list(
                    definition.get(
                        "requirements",
                        [],
                    )
                    or []
                ),
                "description": str(
                    definition.get(
                        "description",
                        "",
                    )
                ),
            }

        return {
            "metric_id": cls._metric_id(definition),
            "version": cls._metric_version(
                definition
            ),
            "scope": str(
                getattr(definition, "scope", "case")
            ),
            "requirements": list(
                getattr(
                    definition,
                    "requirements",
                    [],
                )
                or []
            ),
            "description": str(
                getattr(
                    definition,
                    "description",
                    "",
                )
            ),
        }