"""Creation and execution of repeatable offline metric scoring passes."""

from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.db.test_models import MetricRunRecord
from rag_eval.db.test_repository import TestRepository
from rag_eval.judges import create_judge_adapter
from rag_eval.metrics.engine import ScoringConfig
from rag_eval.metrics.registry import MetricRegistry
from rag_eval.metrics.service import ScoringResult, ScoringService


class MetricRunService:
    """Manage scoring passes without re-executing the evaluated target."""

    def __init__(
        self,
        *,
        repository: TestRepository,
        target_repository: TargetRepository,
        benchmark_repository: BenchmarkRepository,
        metric_registry: MetricRegistry,
    ) -> None:
        self._repository = repository
        self._target_repository = target_repository
        self._benchmark_repository = benchmark_repository
        self._metric_registry = metric_registry

    async def create(
        self,
        run_id: str,
        *,
        name: str,
        config: dict[str, Any],
    ) -> MetricRunRecord:
        """Create a pending immutable scoring-pass snapshot."""
        run = await self._repository.get_run(run_id)
        if run is None:
            raise KeyError(f"run not found: {run_id}")
        record = MetricRunRecord(
            metric_run_id=f"mr-{uuid4()}",
            run_id=run_id,
            name=name,
            status="PENDING",
            config_snapshot=self._normalize_snapshot(config),
        )
        return await self._repository.create_metric_run(record)

    async def execute(self, metric_run_id: str) -> ScoringResult:
        """Score one pending pass from persisted observations and aggregate it."""
        metric_run = await self._repository.get_metric_run(metric_run_id)
        if metric_run is None:
            raise KeyError(f"metric run not found: {metric_run_id}")
        if metric_run.status == "COMPLETED":
            raise ValueError(f"metric run already completed: {metric_run_id}")

        await self._repository.update_metric_run(
            metric_run_id,
            status="RUNNING",
            started_at=datetime.now(UTC),
        )
        await self._repository.delete_aggregates(
            metric_run.run_id,
            metric_run_id=metric_run_id,
        )
        snapshot = dict(metric_run.config_snapshot)
        try:
            scoring = ScoringService(
                registry=self._metric_registry,
                test_repository=self._repository,
                target_repository=self._target_repository,
                benchmark_repository=self._benchmark_repository,
                config=ScoringConfig(
                    mode=str(snapshot.get("mode", "all_available")).lower(),
                    selected_metrics=list(snapshot.get("selected_metrics", [])),
                    metric_versions=dict(snapshot.get("metric_versions", {})),
                    metric_run_id=metric_run_id,
                ),
            )
            judge = create_judge_adapter(snapshot.get("judge"))
            result = await scoring.score_run(
                metric_run.run_id,
                run_metadata={"metric_run": snapshot},
                judge=judge,
            )
            await self._repository.update_metric_run(
                metric_run_id,
                status="COMPLETED",
                finished_at=datetime.now(UTC),
            )
            return result
        except Exception as exc:
            await self._repository.update_metric_run(
                metric_run_id,
                status="FAILED",
                status_reason=str(exc),
                finished_at=datetime.now(UTC),
            )
            raise

    async def list(self, run_id: str) -> list[MetricRunRecord]:
        """List scoring passes attached to one evaluation."""
        if await self._repository.get_run(run_id) is None:
            raise KeyError(f"run not found: {run_id}")
        return list(await self._repository.list_metric_runs(run_id))

    @staticmethod
    def _normalize_snapshot(config: dict[str, Any]) -> dict[str, Any]:
        """Normalize API/YAML metric selection into an immutable snapshot."""
        metrics = config.get("metrics")
        source = metrics if isinstance(metrics, dict) else config
        mode = str(source.get("mode", "all_available")).lower()
        selected_raw = source.get("selected", source.get("selected_metrics", []))
        selected: list[str] = []
        versions: dict[str, str] = {}
        for item in selected_raw or []:
            if isinstance(item, str):
                selected.append(item)
            elif isinstance(item, dict) and item.get("id"):
                metric_id = str(item["id"])
                selected.append(metric_id)
                if item.get("version") is not None:
                    versions[metric_id] = str(item["version"])
        versions.update(
            {
                str(key): str(value)
                for key, value in dict(source.get("metric_versions", {})).items()
            }
        )
        return {
            "mode": mode,
            "selected_metrics": selected,
            "metric_versions": versions,
            "judge": dict(source.get("judge") or config.get("judge") or {}),
            "retrieval": dict(source.get("retrieval") or config.get("retrieval") or {}),
        }
