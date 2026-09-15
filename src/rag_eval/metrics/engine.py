"""Metric execution engine for scoring runs and cases.

This engine:
1. Loads persisted BenchmarkCase and TargetObservation
2. Constructs MetricContext
3. Resolves metric requirements
4. Executes metrics independently
5. Persists MetricResult with proper status
6. Aggregates results at run level

Critical invariant: Never calls TargetAdapter.
"""

import logging
from dataclasses import dataclass
from typing import Any

from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import (
    BenchmarkCase,
    MetricResult as MetricResultModel,
    TargetObservation,
)
from rag_eval.models.enums import MetricStatus

from .base import Metric, MetricRequirement, MetricResult, MetricScope
from .context import MetricContext
from .registry import MetricRegistry

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ScoringConfig:
    """Configuration for metric scoring execution."""

    # Metric selection mode
    mode: str = "all_available"  # "all_available" or "explicit"

    # Explicitly selected metric IDs (used when mode="explicit")
    selected_metrics: list[str] = ()

    # Metric version overrides: {metric_id: version}
    metric_versions: dict[str, str] = ()

    # Whether to persist UNAVAILABLE results or skip them
    persist_unavailable: bool = True

    # Whether to persist FAILED results or skip them
    persist_failed: bool = True


class MetricExecutionEngine:
    """Execute metrics on persisted benchmark data.

    This engine orchestrates metric scoring without calling TargetAdapter.
    It operates solely on persisted BenchmarkCase and TargetObservation data.
    """

    def __init__(
        self,
        registry: MetricRegistry,
        repository: PersistenceRepository,
        config: ScoringConfig | None = None,
    ) -> None:
        """Initialize metric execution engine.

        Args:
            registry: Metric registry with available implementations.
            repository: Repository for persisting metric results.
            config: Scoring configuration (defaults to all_available mode).
        """
        self._registry = registry
        self._repository = repository
        self._config = config or ScoringConfig()

    async def score_case(
        self,
        case: BenchmarkCase,
        observation: TargetObservation | None,
        run_id: str,
        run_metadata: dict[str, Any] | None = None,
        judge: Any | None = None,
    ) -> list[MetricResult]:
        """Score one case with all applicable metrics.

        Args:
            case: Benchmark case with truth data.
            observation: Target observation (may be None if target failed).
            run_id: Run identifier for result persistence.
            run_metadata: Optional run-level metadata.
            judge: Optional judge adapter for semantic metrics.

        Returns:
            List of metric results (computed, unavailable, failed, etc.).
        """
        # Construct metric context
        context = MetricContext(
            case=case,
            observation=observation,
            run_id=run_id,
            run_metadata=run_metadata or {},
            judge=judge,
        )

        # Determine which metrics to execute
        metrics_to_execute = self._select_metrics()

        # Execute each metric independently
        results = []
        for metric in metrics_to_execute:
            result = await self._execute_metric_safe(metric, context)
            results.append(result)

            # Persist result
            await self._persist_result(result, case.case_id)

        return results

    def _select_metrics(self) -> list[Metric]:
        """Select metrics to execute based on configuration.

        Returns:
            List of metric instances to execute.
        """
        if self._config.mode == "explicit":
            # Execute only explicitly selected metrics
            metrics = []
            for metric_id in self._config.selected_metrics:
                version = self._config.metric_versions.get(metric_id, "1")
                metric = self._registry.get(metric_id, version)
                if metric:
                    metrics.append(metric)
                else:
                    logger.warning(
                        "Selected metric '%s' v%s not registered, skipping",
                        metric_id,
                        version,
                    )
            return metrics

        else:  # all_available
            # Execute all registered metrics
            return list(self._registry._metrics.values())

    async def _execute_metric_safe(
        self, metric: Metric, context: MetricContext
    ) -> MetricResult:
        """Execute one metric with exception isolation.

        Args:
            metric: Metric instance to execute.
            context: Metric context with data.

        Returns:
            Metric result (may be FAILED if metric raises).
        """
        try:
            # Check requirements first
            requirements_met, reason = self._check_requirements(metric, context)

            if not requirements_met:
                return MetricResult(
                    metric_id=metric.definition.metric_id,
                    metric_version=metric.definition.version,
                    status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                    reason=reason,
                    case_id=context.case.case_id,
                    run_id=context.run_id,
                )

            # Check NOT_APPLICABLE
            if not self._is_applicable(metric, context):
                return MetricResult(
                    metric_id=metric.definition.metric_id,
                    metric_version=metric.definition.version,
                    status=MetricStatus.NOT_APPLICABLE,
                    reason="Metric not applicable for this case",
                    case_id=context.case.case_id,
                    run_id=context.run_id,
                )

            # Execute metric
            result = await metric.compute(context)

            # Ensure result has case/run IDs
            return MetricResult(
                metric_id=result.metric_id,
                metric_version=result.metric_version,
                status=result.status,
                value=result.value,
                reason=result.reason,
                details=result.details,
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        except Exception as exc:
            logger.exception(
                "Metric %s v%s failed: %s",
                metric.definition.metric_id,
                metric.definition.version,
                exc,
            )

            return MetricResult(
                metric_id=metric.definition.metric_id,
                metric_version=metric.definition.version,
                status=MetricStatus.FAILED,
                reason=f"Metric execution failed: {exc}",
                details={"exception_type": type(exc).__name__},
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

    def _check_requirements(
        self, metric: Metric, context: MetricContext
    ) -> tuple[bool, str | None]:
        """Check if metric requirements are satisfied.

        Args:
            metric: Metric to check requirements for.
            context: Context with available data.

        Returns:
            (satisfied, reason) tuple.
        """
        missing = []

        for req in metric.definition.requirements:
            if not self._requirement_satisfied(req, context):
                missing.append(req.name)

        if missing:
            return False, f"Missing requirements: {', '.join(missing)}"
        return True, None

    def _requirement_satisfied(
        self, requirement: MetricRequirement, context: MetricContext
    ) -> bool:
        """Check if one requirement is satisfied.

        Uses explicit presence checks, not truthiness.
        """
        if requirement == MetricRequirement.QUERY:
            return bool(context.case.query)

        elif requirement == MetricRequirement.HISTORY:
            return len(context.case.history) > 0

        elif requirement == MetricRequirement.REFERENCE_ANSWER:
            # Explicit None check, not truthiness
            return context.has_reference_answer()

        elif requirement == MetricRequirement.GOLD_EVIDENCE:
            return context.has_gold_evidence()

        elif requirement == MetricRequirement.ANSWERABILITY:
            return context.case.answerability is not None

        elif requirement == MetricRequirement.ANSWER:
            # Explicit presence check
            return context.has_answer()

        elif requirement == MetricRequirement.RETRIEVAL:
            # Explicit presence check - retrieval=None differs from zero items
            return context.has_retrieval()

        elif requirement == MetricRequirement.FINAL_CONTEXT:
            return context.get_final_context() is not None

        elif requirement == MetricRequirement.CITATIONS:
            return context.has_citations()

        elif requirement == MetricRequirement.CONFIDENCE:
            return context.has_confidence()

        elif requirement == MetricRequirement.TRACE:
            return context.has_trace()

        elif requirement == MetricRequirement.USAGE:
            return context.has_usage()

        elif requirement == MetricRequirement.JUDGE:
            return context.judge is not None

        elif requirement == MetricRequirement.RUN_METADATA:
            return bool(context.run_metadata)

        return False

    def _is_applicable(self, metric: Metric, context: MetricContext) -> bool:
        """Check if metric is applicable (beyond requirements).

        Some metrics may have requirements satisfied but still be
        logically not applicable (e.g., answerability-specific metrics
        for unanswerable questions).

        Default implementation returns True. Metrics can override.
        """
        return True

    async def _persist_result(self, result: MetricResult, case_id: str) -> None:
        """Persist metric result to database.

        Args:
            result: Metric result to persist.
            case_id: Case identifier for foreign key.
        """
        # Skip unavailable if configured
        if (
            result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT
            and not self._config.persist_unavailable
        ):
            return

        # Skip failed if configured
        if result.status == MetricStatus.FAILED and not self._config.persist_failed:
            return

        # Convert to canonical model
        canonical_result = MetricResultModel(
            metric_result_id=f"mr-{result.metric_id}-{case_id}-{result.metric_version}",
            metric_id=result.metric_id,
            metric_version=result.metric_version,
            status=result.status,
            value=result.value,
            run_id=result.run_id,
            case_id=case_id,
            reason=result.reason,
            details=result.details,
        )

        try:
            await self._repository.persist_metric(canonical_result)
        except Exception as exc:
            logger.error(
                "Failed to persist metric result %s: %s",
                result.metric_id,
                exc,
            )
            raise
