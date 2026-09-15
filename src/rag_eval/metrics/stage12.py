"""Stage 12 metric catalog registration.

Registers all deterministic baseline metrics with the registry.
Metrics are organized by category:
- answer: Answer quality metrics
- retrieval: Retrieval effectiveness metrics
- citation: Citation structure metrics
- performance: Latency and throughput metrics
- usage: Token consumption metrics
- cost: Monetary cost metrics
- reliability: Execution reliability metrics

All metrics are deterministic - no LLM judges, embeddings, or target calls.
"""

from rag_eval.metrics.answer import (
    ExactMatch,
    NormalizedExactMatch,
    TokenF1,
    TokenPrecision,
    TokenRecall,
)
from rag_eval.metrics.citations import (
    AttributionRate,
    BrokenCitations,
    CitationResolution,
)
from rag_eval.metrics.performance import (
    GenerationLatency,
    RetrievalLatency,
    TokensPerSecond,
    TotalLatency,
)
from rag_eval.metrics.registry import MetricRegistry
from rag_eval.metrics.reliability import (
    Availability,
    ErrorRate,
    LatencyP50,
    LatencyP99,
    SuccessRate,
)
from rag_eval.metrics.retrieval import (
    MRR,
    HitAtK,
    MAPAtK,
    NDCGAtK,
    PrecisionAtK,
    RecallAtK,
    RPrecision,
)
from rag_eval.metrics.usage import (
    CostPerToken,
    InputTokens,
    OutputTokens,
    TotalCost,
    TotalTokens,
)


def register_stage12_metrics(registry: MetricRegistry | None = None) -> MetricRegistry:
    """Register all Stage 12 deterministic metrics.

    Args:
        registry: Optional registry to use. Creates new if None.

    Returns:
        Registry with all Stage 12 metrics registered.
    """
    if registry is None:
        registry = MetricRegistry()

    # Answer metrics
    registry.register(ExactMatch())
    registry.register(NormalizedExactMatch())
    registry.register(TokenPrecision())
    registry.register(TokenRecall())
    registry.register(TokenF1())

    # Retrieval metrics (with default k=5)
    registry.register(HitAtK(k=5))
    registry.register(PrecisionAtK(k=5))
    registry.register(RecallAtK(k=5))
    registry.register(MRR())
    registry.register(MAPAtK(k=5))
    registry.register(NDCGAtK(k=5))
    registry.register(RPrecision())

    # Citation metrics
    registry.register(CitationResolution())
    registry.register(BrokenCitations())
    registry.register(AttributionRate())

    # Performance metrics
    registry.register(TotalLatency())
    registry.register(RetrievalLatency())
    registry.register(GenerationLatency())
    registry.register(TokensPerSecond())

    # Usage metrics
    registry.register(TotalTokens())
    registry.register(InputTokens())
    registry.register(OutputTokens())

    # Cost metrics (default USD)
    registry.register(TotalCost(currency="USD"))
    registry.register(CostPerToken(currency="USD"))

    # Reliability metrics
    registry.register(SuccessRate())
    registry.register(ErrorRate())
    registry.register(Availability())
    registry.register(LatencyP50())
    registry.register(LatencyP99())

    return registry


def get_stage12_catalog() -> MetricRegistry:
    """Get the complete Stage 12 metric catalog.

    Returns:
        Registry with all Stage 12 metrics.
    """
    return register_stage12_metrics()


__all__ = [
    "register_stage12_metrics",
    "get_stage12_catalog",
]
