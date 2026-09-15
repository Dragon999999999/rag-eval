"""Tests for Stage 11 metric framework.

Tests verify:
- Metric registry with versioned identity
- Requirement detection (None vs empty distinction)
- Metric status semantics
- Failure isolation
- Repeat scoring idempotency
- Aggregation correctness
- Judge abstraction
- No TargetAdapter dependency
"""

import pytest
from uuid import uuid4

from rag_eval.metrics import (
    MetricRegistry,
    MetricContext,
    MetricExecutionEngine,
    ScoringConfig,
    compute_aggregations,
)
from rag_eval.metrics.base import MetricRequirement, MetricScope, MetricStatus


# Test metrics - minimal deterministic metrics for framework testing
class AlwaysOneMetric:
    """Test metric that always returns 1.0."""

    def __init__(self) -> None:
        from rag_eval.metrics.base import MetricDefinition, MetricResult

        self._definition = MetricDefinition(
            metric_id="test.always_one",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(),
            description="Test metric that always returns 1.0",
        )
        self._result_class = MetricResult

    @property
    def definition(self) -> "MetricDefinition":
        return self._definition

    async def compute(self, context: "MetricContext") -> "MetricResult":
        return self._result_class(
            metric_id=self._definition.metric_id,
            metric_version=self._definition.version,
            status=MetricStatus.COMPUTED,
            value=1.0,
            case_id=context.case.case_id,
            run_id=context.run_id,
        )


class RequiresAnswerMetric:
    """Test metric requiring target answer."""

    def __init__(self) -> None:
        from rag_eval.metrics.base import MetricDefinition, MetricResult

        self._definition = MetricDefinition(
            metric_id="test.requires_answer",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset({MetricRequirement.ANSWER}),
            description="Test metric requiring target answer",
        )
        self._result_class = MetricResult

    @property
    def definition(self) -> "MetricDefinition":
        return self._definition

    async def compute(self, context: "MetricContext") -> "MetricResult":
        if not context.has_answer():
            return self._result_class(
                metric_id=self._definition.metric_id,
                metric_version=self._definition.version,
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer not available",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )
        return self._result_class(
            metric_id=self._definition.metric_id,
            metric_version=self._definition.version,
            status=MetricStatus.COMPUTED,
            value=len(context.get_answer_text() or ""),
            case_id=context.case.case_id,
            run_id=context.run_id,
        )


class BrokenMetric:
    """Test metric that always fails."""

    def __init__(self) -> None:
        from rag_eval.metrics.base import MetricDefinition, MetricResult

        self._definition = MetricDefinition(
            metric_id="test.broken",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(),
            description="Test metric that always raises exception",
        )
        self._result_class = MetricResult

    @property
    def definition(self) -> "MetricDefinition":
        return self._definition

    async def compute(self, context: "MetricContext") -> "MetricResult":
        raise RuntimeError("This metric is designed to fail")
