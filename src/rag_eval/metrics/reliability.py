"""Reliability metrics for Stage 12.

Deterministic metrics measuring execution reliability from run history.
No LLM judges or external calls.

Metrics:
- success_rate: Fraction of cases with successful execution
- error_rate: Fraction of cases with errors
- availability: Fraction of cases with available output
"""

from dataclasses import dataclass, field

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext


@dataclass
class SuccessRateResult(MetricResult):
    """Result of success rate computation."""

    metric_id: str = field(init=False, default="reliability.success_rate")
    metric_version: str = field(init=False, default="1")


class SuccessRate:
    """Success Rate: Fraction of cases with successful target execution.

    Operates at RUN scope (aggregates across all cases).
    For individual cases, returns COMPUTED with value 1.0 if observation exists.

    Formula:
        success_rate = successful_cases / total_cases

    Where successful = observation exists and no error status.

    Requirements:
        - RUN_METADATA: Requires run-level context

    Note:
        This metric is typically computed at run-level aggregation.
        At case-level, it returns 1.0 if observation exists.
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="reliability.success_rate",
            version="1",
            scope=MetricScope.RUN,
            requirements=frozenset({MetricRequirement.RUN_METADATA}),
            description="Fraction of cases with successful target execution.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # At case level, check if observation exists
        has_observation = context.observation is not None

        # Check for error indicators in metadata
        run_metadata = context.run_metadata
        error_status = run_metadata.get("error_status")
        execution_status = run_metadata.get("execution_status")

        # Determine success
        if error_status is not None:
            success = error_status != "error"
        elif execution_status is not None:
            success = execution_status in ("success", "completed")
        else:
            # Default: observation exists = success
            success = has_observation

        return SuccessRateResult(
            status=MetricStatus.COMPUTED,
            value=1.0 if success else 0.0,
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "has_observation": has_observation,
                "error_status": error_status,
                "execution_status": execution_status,
                "success": success,
            },
        )


@dataclass
class ErrorRateResult(MetricResult):
    """Result of error rate computation."""

    metric_id: str = field(init=False, default="reliability.error_rate")
    metric_version: str = field(init=False, default="1")


class ErrorRate:
    """Error Rate: Fraction of cases with target execution errors.

    Operates at RUN scope (aggregates across all cases).
    For individual cases, returns 1.0 if error detected.

    Formula:
        error_rate = error_cases / total_cases

    Requirements:
        - RUN_METADATA: Requires run-level context

    Note:
        Complementary to success_rate.
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="reliability.error_rate",
            version="1",
            scope=MetricScope.RUN,
            requirements=frozenset({MetricRequirement.RUN_METADATA}),
            description="Fraction of cases with target execution errors.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # At case level, check for errors
        run_metadata = context.run_metadata
        error_status = run_metadata.get("error_status")
        execution_status = run_metadata.get("execution_status")
        error_message = run_metadata.get("error_message")

        # Determine if error
        has_error = False
        if error_status == "error":
            has_error = True
        elif execution_status == "failed":
            has_error = True
        elif error_message is not None:
            has_error = True

        return ErrorRateResult(
            status=MetricStatus.COMPUTED,
            value=1.0 if has_error else 0.0,
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "has_error": has_error,
                "error_status": error_status,
                "error_message": error_message,
            },
        )


@dataclass
class AvailabilityResult(MetricResult):
    """Result of availability computation."""

    metric_id: str = field(init=False, default="reliability.availability")
    metric_version: str = field(init=False, default="1")


class Availability:
    """Availability: Fraction of cases where target produced output.

    Measures whether the target responded (regardless of quality).
    Different from success_rate - availability doesn't judge correctness.

    Formula:
        availability = cases_with_response / total_cases

    Requirements:
        - RUN_METADATA: Requires run-level context

    Note:
        A case is "available" if observation exists.
        Quality is measured by other metrics.
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="reliability.availability",
            version="1",
            scope=MetricScope.RUN,
            requirements=frozenset({MetricRequirement.RUN_METADATA}),
            description="Fraction of cases where target produced output.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # At case level, availability = observation exists
        available = context.observation is not None

        return AvailabilityResult(
            status=MetricStatus.COMPUTED,
            value=1.0 if available else 0.0,
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "available": available,
                "has_observation": context.observation is not None,
            },
        )


@dataclass
class LatencyP50Result(MetricResult):
    """Result of P50 latency computation."""

    metric_id: str = field(init=False, default="reliability.latency_p50")
    metric_version: str = field(init=False, default="1")


class LatencyP50:
    """P50 Latency: Median latency across run.

    Operates at RUN scope.
    Extracts latency from run metadata aggregations.

    Formula:
        p50 = median(latencies)

    Requirements:
        - RUN_METADATA: Requires run-level metadata with latency data

    Note:
        This reads pre-computed aggregations from run metadata.
        Individual case-level computation returns UNAVAILABLE.
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="reliability.latency_p50",
            version="1",
            scope=MetricScope.RUN,
            requirements=frozenset({MetricRequirement.RUN_METADATA}),
            description="Median latency across run (P50).",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # This metric requires run-level aggregation
        # At case level, return unavailable
        run_metadata = context.run_metadata

        # Try to get pre-computed p50 from metadata
        latency_metrics = run_metadata.get("latency_metrics", {})
        p50 = latency_metrics.get("p50") or latency_metrics.get("median")

        if p50 is not None:
            return LatencyP50Result(
                status=MetricStatus.COMPUTED,
                value=round(p50, 3),
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"p50_ms": round(p50, 3), "source": "run_metadata"},
            )

        # No pre-computed value available at case level
        return LatencyP50Result(
            status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
            reason="P50 latency requires run-level aggregation",
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={"run_metadata_keys": list(run_metadata.keys())},
        )


@dataclass
class LatencyP99Result(MetricResult):
    """Result of P99 latency computation."""

    metric_id: str = field(init=False, default="reliability.latency_p99")
    metric_version: str = field(init=False, default="1")


class LatencyP99:
    """P99 Latency: 99th percentile latency across run.

    Operates at RUN scope.
    Extracts latency from run metadata aggregations.

    Formula:
        p99 = 99th percentile(latencies)

    Requirements:
        - RUN_METADATA: Requires run-level metadata with latency data

    Note:
        This reads pre-computed aggregations from run metadata.
        Individual case-level computation returns UNAVAILABLE.
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="reliability.latency_p99",
            version="1",
            scope=MetricScope.RUN,
            requirements=frozenset({MetricRequirement.RUN_METADATA}),
            description="99th percentile latency across run.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # This metric requires run-level aggregation
        run_metadata = context.run_metadata

        # Try to get pre-computed p99 from metadata
        latency_metrics = run_metadata.get("latency_metrics", {})
        p99 = latency_metrics.get("p99")

        if p99 is not None:
            return LatencyP99Result(
                status=MetricStatus.COMPUTED,
                value=round(p99, 3),
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"p99_ms": round(p99, 3), "source": "run_metadata"},
            )

        # No pre-computed value available at case level
        return LatencyP99Result(
            status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
            reason="P99 latency requires run-level aggregation",
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={"run_metadata_keys": list(run_metadata.keys())},
        )


# Export all reliability metrics
__all__ = [
    "SuccessRate",
    "ErrorRate",
    "Availability",
    "LatencyP50",
    "LatencyP99",
]
