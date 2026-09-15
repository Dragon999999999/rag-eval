"""Metric execution engine and framework for rag-eval.

This package provides:
- Metric protocol and requirement detection
- Metric registry with versioned identity
- Metric execution engine with isolation
- Aggregation utilities
- Scoring service (no TargetAdapter dependency)
- Stage 12 deterministic metric catalog

Metrics operate only on persisted benchmark truth and TargetObservations.
They must never call the evaluated target.

Stage 12 Metrics:
- Answer: exact_match, normalized_exact_match, token_precision/recall/f1
- Retrieval: hit_at_k, precision_at_k, recall_at_k, mrr, map, ndcg, r_precision
- Citation: resolution, broken, attribution_rate
- Performance: latency, throughput
- Usage: tokens, cost
- Reliability: success_rate, error_rate, availability
"""

from .aggregation import (
    AggregationResult,
    compute_aggregations,
    convert_to_canonical,
)
from .answer import (
    ExactMatch,
    NormalizedExactMatch,
    TokenF1,
    TokenPrecision,
    TokenRecall,
)
from .base import (
    Metric,
    MetricDefinition,
    MetricRequirement,
    MetricRequirementCheck,
    MetricResult,
    MetricScope,
)
from .citations import (
    AttributionRate,
    BrokenCitations,
    CitationResolution,
)
from .context import MetricContext, RetrievalStageView
from .engine import MetricExecutionEngine, ScoringConfig
from .performance import (
    GenerationLatency,
    RetrievalLatency,
    TokensPerSecond,
    TotalLatency,
)
from .registry import MetricRegistry
from .reliability import (
    Availability,
    ErrorRate,
    LatencyP50,
    LatencyP99,
    SuccessRate,
)
from .retrieval import (
    MRR,
    HitAtK,
    MAPAtK,
    NDCGAtK,
    PrecisionAtK,
    RecallAtK,
    RPrecision,
)
from .service import ScoringResult, ScoringService
from .usage import (
    CostPerToken,
    InputTokens,
    OutputTokens,
    TotalCost,
    TotalTokens,
)

__all__ = [
    # Framework
    "AggregationResult",
    "compute_aggregations",
    "convert_to_canonical",
    "Metric",
    "MetricDefinition",
    "MetricRequirement",
    "MetricRequirementCheck",
    "MetricResult",
    "MetricScope",
    "MetricContext",
    "RetrievalStageView",
    "MetricExecutionEngine",
    "ScoringConfig",
    "MetricRegistry",
    "ScoringService",
    "ScoringResult",
    # Answer metrics
    "ExactMatch",
    "NormalizedExactMatch",
    "TokenPrecision",
    "TokenRecall",
    "TokenF1",
    # Retrieval metrics
    "HitAtK",
    "PrecisionAtK",
    "RecallAtK",
    "MRR",
    "MAPAtK",
    "NDCGAtK",
    "RPrecision",
    # Citation metrics
    "CitationResolution",
    "BrokenCitations",
    "AttributionRate",
    # Performance metrics
    "TotalLatency",
    "RetrievalLatency",
    "GenerationLatency",
    "TokensPerSecond",
    # Usage metrics
    "TotalTokens",
    "InputTokens",
    "OutputTokens",
    # Cost metrics
    "TotalCost",
    "CostPerToken",
    # Reliability metrics
    "SuccessRate",
    "ErrorRate",
    "Availability",
    "LatencyP50",
    "LatencyP99",
]
