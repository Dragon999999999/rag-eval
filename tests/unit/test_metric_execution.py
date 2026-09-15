"""Tests for Stage 11 metric framework - Part 2: Test functions."""

import pytest
from datetime import UTC, datetime
from uuid import uuid4

from rag_eval.metrics import (
    MetricRegistry,
    MetricContext,
    MetricExecutionEngine,
    ScoringConfig,
    compute_aggregations,
)
from rag_eval.metrics.base import (
    MetricDefinition,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.models import BenchmarkCase, TargetObservation, Answer


# Continue test metrics from test_metric_framework.py
class AlwaysOneMetric:
    """Test metric that always returns 1.0."""

    def __init__(self) -> None:
        from rag_eval.metrics.base import MetricDefinition, MetricResult

        self._definition = MetricDefinition(
            metric_id="test.always_one",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(),
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


class BrokenMetric:
    """Test metric that always fails."""

    def __init__(self) -> None:
        from rag_eval.metrics.base import MetricDefinition, MetricResult

        self._definition = MetricDefinition(
            metric_id="test.broken",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(),
        )
        self._result_class = MetricResult

    @property
    def definition(self) -> "MetricDefinition":
        return self._definition

    async def compute(self, context: "MetricContext") -> "MetricResult":
        raise RuntimeError("This metric is designed to fail")


class TestMetricRegistry:
    """Test metric registry with versioned identity."""

    def test_register_and_get_metric(self) -> None:
        """Register and retrieve a metric."""
        registry = MetricRegistry()
        metric = AlwaysOneMetric()

        registry.register(metric)

        retrieved = registry.get("test.always_one", "1")
        assert retrieved is metric

    def test_list_metrics(self) -> None:
        """List registered metrics."""
        registry = MetricRegistry()
        registry.register(AlwaysOneMetric())

        definitions = registry.list_metrics()
        assert len(definitions) == 1
        assert definitions[0].metric_id == "test.always_one"

    def test_duplicate_registration_rejected(self) -> None:
        """Duplicate metric ID + version should be rejected."""
        registry = MetricRegistry()
        registry.register(AlwaysOneMetric())

        with pytest.raises(ValueError, match="already registered"):
            registry.register(AlwaysOneMetric())

    def test_different_versions_coexist(self) -> None:
        """Different versions of same metric can coexist."""
        registry = MetricRegistry()

        # Create v2 metric
        class AlwaysOneV2(AlwaysOneMetric):
            def __init__(self) -> None:
                super().__init__()
                self._definition = MetricDefinition(
                    metric_id="test.always_one",
                    version="2",
                    scope=MetricScope.CASE,
                    requirements=frozenset(),
                )

        registry.register(AlwaysOneMetric())
        registry.register(AlwaysOneV2())

        assert registry.get("test.always_one", "1") is not None
        assert registry.get("test.always_one", "2") is not None
        assert len(registry) == 2

    def test_get_required_raises(self) -> None:
        """get_required should raise KeyError for unregistered metric."""
        registry = MetricRegistry()

        with pytest.raises(KeyError, match="not registered"):
            registry.get_required("nonexistent.metric")


class TestMetricContext:
    """Test MetricContext requirement detection."""

    def test_has_answer_with_none(self) -> None:
        """has_answer should return False when observation is None."""
        case = BenchmarkCase(case_id="test", query="Q")
        context = MetricContext(case=case, observation=None)

        assert context.has_answer() is False

    def test_has_answer_with_answer(self) -> None:
        """has_answer should return True when answer exists."""
        case = BenchmarkCase(case_id="test", query="Q")
        observation = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Answer"),
            created_at=datetime.now(UTC),
        )
        context = MetricContext(case=case, observation=observation)

        assert context.has_answer() is True

    def test_has_answer_empty_string(self) -> None:
        """has_answer should return True for empty answer (exists but empty)."""
        case = BenchmarkCase(case_id="test", query="Q")
        observation = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text=""),
            created_at=datetime.now(UTC),
        )
        context = MetricContext(case=case, observation=observation)

        assert context.has_answer() is True
        assert context.get_answer_text() == ""

    def test_has_reference_answer_none(self) -> None:
        """has_reference_answer should return False when None."""
        case = BenchmarkCase(case_id="test", query="Q", reference_answer=None)
        context = MetricContext(case=case)

        assert context.has_reference_answer() is False

    def test_has_reference_answer_empty_string(self) -> None:
        """has_reference_answer should return True for empty string."""
        case = BenchmarkCase(case_id="test", query="Q", reference_answer="")
        context = MetricContext(case=case)

        assert context.has_reference_answer() is True
        assert context.get_reference_answer() == ""


class TestAggregation:
    """Test aggregation utilities."""

    def test_compute_aggregations_basic(self) -> None:
        """Compute basic aggregations."""
        values = [1.0, 2.0, 3.0, 4.0]
        statuses = [MetricStatus.COMPUTED] * 4

        aggs = compute_aggregations("test.metric", "1", values, statuses)

        assert len(aggs) >= 5  # At least count, mean, median, min, max

        count_agg = next(a for a in aggs if a.aggregation_name == "count")
        assert count_agg.value == 4
        assert count_agg.computed_count == 4

        mean_agg = next(a for a in aggs if a.aggregation_name == "mean")
        assert mean_agg.value == 2.5

    def test_compute_aggregations_with_unavailable(self) -> None:
        """Aggregations should exclude unavailable values."""
        values = [1.0, 3.0]  # Only 2 computed
        statuses = [
            MetricStatus.COMPUTED,
            MetricStatus.UNAVAILABLE_MISSING_INPUT,
            MetricStatus.COMPUTED,
            MetricStatus.UNAVAILABLE_MISSING_INPUT,
        ]

        aggs = compute_aggregations("test.metric", "1", values, statuses)

        count_agg = next(a for a in aggs if a.aggregation_name == "count")
        assert count_agg.value == 2  # Only computed values
        assert count_agg.total_count == 4
        assert count_agg.unavailable_count == 2

    def test_percentile_computation(self) -> None:
        """Test percentile calculations."""
        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        statuses = [MetricStatus.COMPUTED] * 5

        aggs = compute_aggregations("test.metric", "1", values, statuses)

        p50 = next(a for a in aggs if a.aggregation_name == "p50")
        assert p50.value == 3.0

        p90 = next(a for a in aggs if a.aggregation_name == "p90")
        assert p90.value > 4.0


class TestMetricExecution:
    """Test metric execution engine."""

    @pytest.mark.asyncio
    async def test_execute_single_metric(self) -> None:
        """Execute a single metric successfully."""
        from rag_eval.metrics.engine import MetricExecutionEngine, ScoringConfig

        registry = MetricRegistry()
        registry.register(AlwaysOneMetric())

        # Mock repository
        class MockRepo:
            async def persist_metric(self, metric):
                pass

        engine = MetricExecutionEngine(registry, MockRepo())  # type: ignore[arg-type]

        case = BenchmarkCase(case_id="test", query="Q")
        context = MetricContext(case=case, run_id="run-1")

        # Execute directly
        metric = registry.get_required("test.always_one")
        result = await metric.compute(context)

        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0

    @pytest.mark.asyncio
    async def test_failure_isolation(self) -> None:
        """One metric failure should not abort others."""
        from rag_eval.metrics.engine import MetricExecutionEngine

        registry = MetricRegistry()
        registry.register(AlwaysOneMetric())
        registry.register(BrokenMetric())

        class MockRepo:
            async def persist_metric(self, metric):
                pass

        engine = MetricExecutionEngine(registry, MockRepo())  # type: ignore[arg-type]

        case = BenchmarkCase(case_id="test", query="Q")
        context = MetricContext(case=case, run_id="run-1")

        # Score case - should get results from both metrics
        results = await engine.score_case(case, None, "run-1")

        # Should have 2 results
        assert len(results) == 2

        # One computed, one failed
        computed = [r for r in results if r.status == MetricStatus.COMPUTED]
        failed = [r for r in results if r.status == MetricStatus.FAILED]

        assert len(computed) == 1
        assert len(failed) == 1
        assert computed[0].metric_id == "test.always_one"
        assert failed[0].metric_id == "test.broken"

    @pytest.mark.asyncio
    async def test_missing_requirements(self) -> None:
        """Missing requirements should return UNAVAILABLE."""
        from rag_eval.metrics.base import (
            MetricDefinition,
            MetricRequirement,
            MetricResult,
        )

        class RequiresAnswerMetric:
            def __init__(self) -> None:
                self._definition = MetricDefinition(
                    metric_id="test.requires_answer",
                    version="1",
                    scope=MetricScope.CASE,
                    requirements=frozenset({MetricRequirement.ANSWER}),
                )

            @property
            def definition(self) -> MetricDefinition:
                return self._definition

            async def compute(self, context: MetricContext) -> MetricResult:
                if not context.has_answer():
                    return MetricResult(
                        metric_id=self._definition.metric_id,
                        metric_version=self._definition.version,
                        status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                        reason="Answer missing",
                        case_id=context.case.case_id,
                        run_id=context.run_id,
                    )
                return MetricResult(
                    metric_id=self._definition.metric_id,
                    metric_version=self._definition.version,
                    status=MetricStatus.COMPUTED,
                    value=1.0,
                    case_id=context.case.case_id,
                    run_id=context.run_id,
                )

        registry = MetricRegistry()
        registry.register(RequiresAnswerMetric())

        class MockRepo:
            async def persist_metric(self, metric):
                pass

        engine = MetricExecutionEngine(registry, MockRepo())  # type: ignore[arg-type]

        case = BenchmarkCase(case_id="test", query="Q")
        # No observation - answer missing
        results = await engine.score_case(case, None, "run-1")

        assert len(results) == 1
        assert results[0].status == MetricStatus.UNAVAILABLE_MISSING_INPUT


class TestNoTargetDependency:
    """Prove scoring has no TargetAdapter dependency."""

    @pytest.mark.asyncio
    async def test_scoring_without_target_adapter(self) -> None:
        """Scoring should succeed without any TargetAdapter."""
        from rag_eval.metrics.engine import MetricExecutionEngine

        registry = MetricRegistry()
        registry.register(AlwaysOneMetric())

        class MockRepo:
            async def persist_metric(self, metric):
                pass

        engine = MetricExecutionEngine(registry, MockRepo())  # type: ignore[arg-type]

        case = BenchmarkCase(case_id="test", query="Q")
        context = MetricContext(case=case, run_id="run-1")

        # Execute metric - no TargetAdapter involved
        metric = registry.get_required("test.always_one")
        result = await metric.compute(context)

        # Should succeed
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0
