"""Tests for Stage 12 deterministic metric catalog.

Tests cover:
- Answer metrics (EM, NEM, token P/R/F1)
- Retrieval metrics (Hit@K, P@K, R@K, MRR, MAP, nDCG, R-Prec)
- Citation metrics (resolution, broken, attribution)
- Performance metrics (latency, throughput)
- Usage metrics (tokens, cost)
- Reliability metrics (success rate, availability)

All tests use hand-verifiable expected values.
"""

import pytest
from datetime import UTC, datetime
from uuid import uuid4

from rag_eval.metrics import (
    ExactMatch,
    NormalizedExactMatch,
    TokenPrecision,
    TokenRecall,
    TokenF1,
    HitAtK,
    PrecisionAtK,
    RecallAtK,
    MRR,
    MAPAtK,
    NDCGAtK,
    RPrecision,
    CitationResolution,
    BrokenCitations,
    AttributionRate,
    TotalLatency,
    RetrievalLatency,
    GenerationLatency,
    TokensPerSecond,
    TotalTokens,
    InputTokens,
    OutputTokens,
    TotalCost,
    CostPerToken,
    SuccessRate,
    ErrorRate,
    Availability,
)
from rag_eval.metrics.base import MetricStatus
from rag_eval.metrics.context import MetricContext
from rag_eval.models import (
    BenchmarkCase,
    TargetObservation,
    Answer,
    RetrievalStage,
    RetrievedItem,
    Citation,
    Usage,
    Trace,
    TraceSpan,
)
from rag_eval.models.retrieval import RetrievalResult, SourceLocation
from rag_eval.models.enums import RetrievalStageType


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def case_with_reference():
    """Create a benchmark case with reference answer."""
    return BenchmarkCase(
        case_id="test-case-1",
        query="What is the capital of France?",
        reference_answer="Paris",
        gold_evidence=[],
    )


@pytest.fixture
def case_with_gold_evidence():
    """Create a benchmark case with gold evidence."""
    from rag_eval.models import EvidenceSpan
    
    gold = EvidenceSpan(
        evidence_id="gold-1",
        document_id="doc1",
        page=1,
        start_char=0,
        end_char=100,
        text="Evidence about Paris",
    )
    
    return BenchmarkCase(
        case_id="test-case-2",
        query="What is the capital of France?",
        reference_answer="Paris",
        gold_evidence=[gold],
    )


@pytest.fixture
def observation_with_answer():
    """Create an observation with answer."""
    return TargetObservation(
        observation_id="obs-1",
        case_id="test-case-1",
        request_id="req-1",
        answer=Answer(text="Paris"),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def observation_with_answer_and_citations():
    """Create an observation with answer and citations."""
    citation = Citation(
        document_id="doc1",
        page=1,
        start_char=0,
        end_char=50,
        answer_span={"start_char": 0, "end_char": 5},
    )
    
    return TargetObservation(
        observation_id="obs-2",
        case_id="test-case-1",
        request_id="req-1",
        answer=Answer(text="Paris", citations=[citation]),
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def observation_with_retrieval():
    """Create an observation with retrieval results."""
    from rag_eval.models import RetrievalResult
    
    item = RetrievedItem(
        retrieval_id="retrieval-1",
        rank=1,
        source=SourceLocation(
            document_id="doc1",
            page=1,
            start_char=0,
            end_char=100,
        ),
        score={"value": 0.9, "type": "similarity"},
    )
    
    stage = RetrievalStage(
        stage_id="stage-1",
        type=RetrievalStageType.CANDIDATE_RETRIEVAL,
        items=[item],
    )
    
    retrieval = RetrievalResult(
        stages=[stage],
    )
    
    return TargetObservation(
        observation_id="obs-3",
        case_id="test-case-1",
        request_id="req-1",
        answer=Answer(text="Paris"),
        retrieval=retrieval,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def observation_with_trace():
    """Create an observation with execution trace."""
    from datetime import timedelta
    
    now = datetime.now(UTC)
    trace = Trace(
        trace_id="trace-1",
        spans=[
            TraceSpan(
                span_id="span-1",
                name="retrieval",
                started_at=now,
                ended_at=now + timedelta(milliseconds=50),
                duration_ms=50.0,
            ),
            TraceSpan(
                span_id="span-2",
                name="generation",
                started_at=now + timedelta(milliseconds=50),
                ended_at=now + timedelta(milliseconds=150.5),
                duration_ms=100.5,
            ),
        ],
    )
    
    return TargetObservation(
        observation_id="obs-4",
        case_id="test-case-1",
        request_id="req-1",
        answer=Answer(text="Paris"),
        trace=trace,
        created_at=datetime.now(UTC),
    )


@pytest.fixture
def observation_with_usage():
    """Create an observation with usage data."""
    usage = Usage(
        tokens={"input": 100, "output": 50, "total": 150},
        cost={"total": 0.002, "currency": "USD"},
    )
    
    return TargetObservation(
        observation_id="obs-5",
        case_id="test-case-1",
        request_id="req-1",
        answer=Answer(text="Paris"),
        usage=usage,
        created_at=datetime.now(UTC),
    )


# ============================================================================
# Answer Metrics Tests
# ============================================================================

class TestExactMatch:
    """Test exact match metric."""

    @pytest.mark.asyncio
    async def test_exact_match_perfect(self, case_with_reference, observation_with_answer) -> None:
        """Exact match should return 1.0 for identical answers."""
        metric = ExactMatch()
        context = MetricContext(case=case_with_reference, observation=observation_with_answer, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0
        assert result.metric_id == "answer.exact_match"
        assert result.metric_version == "1"

    @pytest.mark.asyncio
    async def test_exact_match_different(self, case_with_reference) -> None:
        """Exact match should return 0.0 for different answers."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="London"),
            created_at=datetime.now(UTC),
        )
        
        metric = ExactMatch()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 0.0

    @pytest.mark.asyncio
    async def test_exact_match_whitespace(self, case_with_reference) -> None:
        """Exact match should be sensitive to whitespace."""
        obs1 = TargetObservation(
            observation_id="obs1",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris "),  # trailing space
            created_at=datetime.now(UTC),
        )
        
        metric = ExactMatch()
        context = MetricContext(case=case_with_reference, observation=obs1, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 0.0  # Whitespace matters

    @pytest.mark.asyncio
    async def test_exact_match_missing_answer(self, case_with_reference) -> None:
        """Exact match should return UNAVAILABLE when answer missing."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=None,
            created_at=datetime.now(UTC),
        )
        
        metric = ExactMatch()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT

    @pytest.mark.asyncio
    async def test_exact_match_missing_reference(self, observation_with_answer) -> None:
        """Exact match should return UNAVAILABLE when reference missing."""
        case = BenchmarkCase(
            case_id="test",
            query="Q",
            reference_answer=None,
        )
        
        metric = ExactMatch()
        context = MetricContext(case=case, observation=observation_with_answer, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT


class TestNormalizedExactMatch:
    """Test normalized exact match metric."""

    @pytest.mark.asyncio
    async def test_normalized_match_case_insensitive(self, case_with_reference) -> None:
        """Normalized match should ignore case."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="paris"),  # lowercase
            created_at=datetime.now(UTC),
        )
        
        metric = NormalizedExactMatch()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0

    @pytest.mark.asyncio
    async def test_normalized_match_punctuation(self, case_with_reference) -> None:
        """Normalized match should ignore punctuation."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris!"),
            created_at=datetime.now(UTC),
        )
        
        metric = NormalizedExactMatch()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0

    @pytest.mark.asyncio
    async def test_normalized_match_whitespace(self, case_with_reference) -> None:
        """Normalized match should normalize whitespace."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="  Paris  "),
            created_at=datetime.now(UTC),
        )
        
        metric = NormalizedExactMatch()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0


class TestTokenMetrics:
    """Test token-level metrics."""

    @pytest.mark.asyncio
    async def test_token_f1_perfect(self, case_with_reference) -> None:
        """Token F1 should be 1.0 for perfect match."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris"),
            created_at=datetime.now(UTC),
        )
        
        metric = TokenF1()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0

    @pytest.mark.asyncio
    async def test_token_f1_partial(self) -> None:
        """Token F1 should handle partial overlap."""
        case = BenchmarkCase(
            case_id="test",
            query="Q",
            reference_answer="The capital is Paris",
        )
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris is the capital"),
            created_at=datetime.now(UTC),
        )
        
        metric = TokenF1()
        context = MetricContext(case=case, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        # All tokens match, just reordered - should be 1.0
        assert result.value == 1.0

    @pytest.mark.asyncio
    async def test_token_precision_empty_prediction(self, case_with_reference) -> None:
        """Token precision should be UNAVAILABLE for empty prediction."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text=""),
            created_at=datetime.now(UTC),
        )
        
        metric = TokenPrecision()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT

    @pytest.mark.asyncio
    async def test_token_recall_empty_reference(self) -> None:
        """Token recall should be UNAVAILABLE for empty reference."""
        case = BenchmarkCase(
            case_id="test",
            query="Q",
            reference_answer="",
        )
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris"),
            created_at=datetime.now(UTC),
        )
        
        metric = TokenRecall()
        context = MetricContext(case=case, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT


# ============================================================================
# Retrieval Metrics Tests
# ============================================================================

class TestHitAtK:
    """Test Hit@K metric."""

    @pytest.mark.asyncio
    async def test_hit_at_k_success(self, case_with_gold_evidence, observation_with_retrieval) -> None:
        """Hit@K should return 1.0 when gold is retrieved."""
        metric = HitAtK(k=5)
        context = MetricContext(case=case_with_gold_evidence, observation=observation_with_retrieval, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0  # doc1 is in both gold and retrieval

    @pytest.mark.asyncio
    async def test_hit_at_k_miss(self, case_with_gold_evidence) -> None:
        """Hit@K should return 0.0 when gold not retrieved."""
        # Create retrieval with different document
        from rag_eval.models import RetrievalResult
        
        item = RetrievedItem(
            retrieval_id="retrieval-1",
            rank=1,
            source=SourceLocation(document_id="doc2", page=1, start_char=0, end_char=100),
            score={"value": 0.9, "type": "similarity"},
        )
        stage = RetrievalStage(stage_id="s1", type=RetrievalStageType.CANDIDATE_RETRIEVAL, items=[item])
        retrieval = RetrievalResult(stages=[stage])

        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Answer"),
            retrieval=retrieval,
            created_at=datetime.now(UTC),
        )

        metric = HitAtK(k=5)
        context = MetricContext(case=case_with_gold_evidence, observation=obs, run_id="run-1")

        result = await metric.compute(context)

        assert result.status == MetricStatus.COMPUTED
        assert result.value == 0.0

    @pytest.mark.asyncio
    async def test_hit_at_k_no_gold(self, observation_with_retrieval) -> None:
        """Hit@K should be UNAVAILABLE without gold evidence."""
        case = BenchmarkCase(case_id="test", query="Q", gold_evidence=[])

        metric = HitAtK(k=5)
        context = MetricContext(case=case, observation=observation_with_retrieval, run_id="run-1")

        result = await metric.compute(context)

        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT


class TestMRR:
    """Test Mean Reciprocal Rank metric."""

    @pytest.mark.asyncio
    async def test_mrr_first_position(self, case_with_gold_evidence) -> None:
        """MRR should be 1.0 when relevant item is first."""
        # Create retrieval with relevant item first
        from rag_eval.models import RetrievalResult
        
        item1 = RetrievedItem(
            retrieval_id="retrieval-1",
            rank=1,
            source=SourceLocation(document_id="doc1", page=1, start_char=0, end_char=100),
            score={"value": 0.9, "type": "similarity"},
        )
        item2 = RetrievedItem(
            retrieval_id="retrieval-2",
            rank=2,
            source=SourceLocation(document_id="doc2", page=1, start_char=0, end_char=100),
            score={"value": 0.8, "type": "similarity"},
        )
        stage = RetrievalStage(stage_id="s1", type=RetrievalStageType.CANDIDATE_RETRIEVAL, items=[item1, item2])
        retrieval = RetrievalResult(stages=[stage])
        
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Answer"),
            retrieval=retrieval,
            created_at=datetime.now(UTC),
        )
        
        metric = MRR()
        context = MetricContext(case=case_with_gold_evidence, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0  # 1/1 = 1.0

    @pytest.mark.asyncio
    async def test_mrr_second_position(self, case_with_gold_evidence) -> None:
        """MRR should be 0.5 when relevant item is second."""
        # Create retrieval with relevant item second
        from rag_eval.models import RetrievalResult
        
        item1 = RetrievedItem(
            retrieval_id="retrieval-1",
            rank=1,
            source=SourceLocation(document_id="doc2", page=1, start_char=0, end_char=100),
            score={"value": 0.9, "type": "similarity"},
        )
        item2 = RetrievedItem(
            retrieval_id="retrieval-2",
            rank=2,
            source=SourceLocation(document_id="doc1", page=1, start_char=0, end_char=100),
            score={"value": 0.8, "type": "similarity"},
        )
        stage = RetrievalStage(stage_id="s1", type=RetrievalStageType.CANDIDATE_RETRIEVAL, items=[item1, item2])
        retrieval = RetrievalResult(stages=[stage])

        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Answer"),
            retrieval=retrieval,
            created_at=datetime.now(UTC),
        )

        metric = MRR()
        context = MetricContext(case=case_with_gold_evidence, observation=obs, run_id="run-1")

        result = await metric.compute(context)

        assert result.status == MetricStatus.COMPUTED
        assert result.value == 0.5  # 1/2 = 0.5


# ============================================================================
# Performance Metrics Tests
# ============================================================================

class TestTotalLatency:
    """Test total latency metric."""

    @pytest.mark.asyncio
    async def test_total_latency_from_trace(self, case_with_reference, observation_with_trace) -> None:
        """Total latency should extract timing from trace."""
        metric = TotalLatency()
        context = MetricContext(case=case_with_reference, observation=observation_with_trace, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 150.5
        assert result.metric_id == "performance.total_latency_ms"

    @pytest.mark.asyncio
    async def test_total_latency_no_trace(self, case_with_reference) -> None:
        """Total latency should be UNAVAILABLE without trace."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris"),
            created_at=datetime.now(UTC),
        )
        
        metric = TotalLatency()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT


# ============================================================================
# Usage Metrics Tests
# ============================================================================

class TestTotalTokens:
    """Test total tokens metric."""

    @pytest.mark.asyncio
    async def test_total_tokens(self, case_with_reference, observation_with_usage) -> None:
        """Total tokens should sum input and output."""
        metric = TotalTokens()
        context = MetricContext(case=case_with_reference, observation=observation_with_usage, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 150
        assert result.metric_id == "usage.total_tokens"

    @pytest.mark.asyncio
    async def test_total_tokens_no_usage(self, case_with_reference) -> None:
        """Total tokens should be UNAVAILABLE without usage."""
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris"),
            created_at=datetime.now(UTC),
        )
        
        metric = TotalTokens()
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT


class TestTotalCost:
    """Test total cost metric."""

    @pytest.mark.asyncio
    async def test_total_cost(self, case_with_reference, observation_with_usage) -> None:
        """Total cost should extract cost from usage."""
        metric = TotalCost(currency="USD")
        context = MetricContext(case=case_with_reference, observation=observation_with_usage, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 0.002
        assert result.metric_id == "cost.total"

    @pytest.mark.asyncio
    async def test_total_cost_no_cost_field(self, case_with_reference) -> None:
        """Total cost should be UNAVAILABLE if no cost field."""
        usage = Usage(
            tokens={"input": 100, "output": 50, "total": 150},
        )
        obs = TargetObservation(
            observation_id="obs",
            case_id="test",
            request_id="req",
            answer=Answer(text="Paris"),
            usage=usage,
            created_at=datetime.now(UTC),
        )
        
        metric = TotalCost(currency="USD")
        context = MetricContext(case=case_with_reference, observation=obs, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.UNAVAILABLE_MISSING_INPUT


# ============================================================================
# Reliability Metrics Tests
# ============================================================================

class TestSuccessRate:
    """Test success rate metric."""

    @pytest.mark.asyncio
    async def test_success_rate_with_observation(self, case_with_reference, observation_with_answer) -> None:
        """Success rate should return 1.0 when observation exists."""
        metric = SuccessRate()
        context = MetricContext(case=case_with_reference, observation=observation_with_answer, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0

    @pytest.mark.asyncio
    async def test_success_rate_no_observation(self, case_with_reference) -> None:
        """Success rate should return 0.0 without observation."""
        metric = SuccessRate()
        context = MetricContext(case=case_with_reference, observation=None, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 0.0


class TestAvailability:
    """Test availability metric."""

    @pytest.mark.asyncio
    async def test_availability_with_observation(self, case_with_reference, observation_with_answer) -> None:
        """Availability should return 1.0 when observation exists."""
        metric = Availability()
        context = MetricContext(case=case_with_reference, observation=observation_with_answer, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 1.0

    @pytest.mark.asyncio
    async def test_availability_no_observation(self, case_with_reference) -> None:
        """Availability should return 0.0 without observation."""
        metric = Availability()
        context = MetricContext(case=case_with_reference, observation=None, run_id="run-1")
        
        result = await metric.compute(context)
        
        assert result.status == MetricStatus.COMPUTED
        assert result.value == 0.0


# ============================================================================
# Stage 12 Catalog Tests
# ============================================================================

class TestStage12Catalog:
    """Test Stage 12 metric catalog registration."""

    def test_register_stage12_metrics(self) -> None:
        """Should register all Stage 12 metrics."""
        from rag_eval.metrics.stage12 import get_stage12_catalog
        
        registry = get_stage12_catalog()
        
        # Should have metrics registered
        assert len(registry) > 20
        
        # Check specific metrics exist
        assert registry.get("answer.exact_match", "1") is not None
        assert registry.get("retrieval.hit_at_k", "1") is not None
        assert registry.get("citation.resolution", "1") is not None
        assert registry.get("performance.total_latency_ms", "1") is not None
        assert registry.get("usage.total_tokens", "1") is not None
        assert registry.get("cost.total", "1") is not None
        assert registry.get("reliability.success_rate", "1") is not None

    def test_metric_ids_are_stable(self) -> None:
        """Metric IDs should be stable and versioned."""
        from rag_eval.metrics.stage12 import get_stage12_catalog
        
        registry = get_stage12_catalog()
        
        # Check versioned access
        em = registry.get("answer.exact_match", "1")
        assert em is not None
        assert em.definition.metric_id == "answer.exact_match"
        assert em.definition.version == "1"
