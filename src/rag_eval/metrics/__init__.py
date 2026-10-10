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
    BrokenRate,
    CitationResolution,
    ClaimCoverage,
    DocumentAttributionAccuracy,
    EvidenceUtilization,
    MeanCitationsPerClaim,
    PageAttributionAccuracy,
    ResolutionRate,
    UncitedClaimRate,
)
from .context import MetricContext, RetrievalStageView
from .decision import (
    AbstentionPrecision,
    AbstentionRate,
    AbstentionRecall,
    AcceptRate,
    AnswerabilityAccuracy,
    FalseAbstentionRate,
    FalseAnswerRate,
    RejectRate,
)
from .engine import MetricExecutionEngine, ScoringConfig
from .performance import (
    AssessmentLatency,
    ComponentFailureRate,
    ContextConstructionLatency,
    E2ELatency,
    EmbeddingLatency,
    GenerationLatency,
    RetrievalLatency,
    StageLatency,
    StageLatencyShare,
    StageThroughput,
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
    DocumentRecall,
    F1AtK,
    FirstRelevantRank,
    HitAtK,
    MAPAtK,
    NDCGAtK,
    PageRecall,
    PrecisionAtK,
    RecallAtK,
    RPrecision,
)
from .service import ScoringResult, ScoringService
from .stage12 import get_stage12_catalog, register_stage12_metrics
from .stage_delta import (
    GoldRetention,
    ItemRetentionRate,
    MAPDelta,
    MRRDelta,
    NDCGDelta,
    NoiseRejection,
    PrecisionDelta,
    QualityGainPerMs,
    RankGain,
    RankRegression,
    RecallDelta,
    SourceRetentionRate,
    TopKChurn,
)
from .stage_delta import (
    StageLatency as StageLatencyDelta,
)
from .usage import (
    ContextTokens,
    CostPerToken,
    EmbeddingCalls,
    InputTokens,
    LLMCalls,
    OutputTokens,
    RelevantEvidencePerContextToken,
    RerankerCalls,
    RetrievalCalls,
    TokensPerCorrectAnswer,
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
    # Stage 12 catalog
    "get_stage12_catalog",
    "register_stage12_metrics",
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
    "ResolutionRate",
    "BrokenRate",
    "ClaimCoverage",
    "DocumentAttributionAccuracy",
    "PageAttributionAccuracy",
    "MeanCitationsPerClaim",
    "UncitedClaimRate",
    "EvidenceUtilization",
    # Decision metrics
    "AcceptRate",
    "RejectRate",
    "AbstentionRate",
    "AnswerabilityAccuracy",
    "FalseAnswerRate",
    "FalseAbstentionRate",
    "AbstentionPrecision",
    "AbstentionRecall",
    # Performance metrics
    "TotalLatency",
    "RetrievalLatency",
    "GenerationLatency",
    "TokensPerSecond",
    "E2ELatency",
    "EmbeddingLatency",
    "ContextConstructionLatency",
    "AssessmentLatency",
    "StageLatency",
    "StageLatencyShare",
    "StageThroughput",
    "ComponentFailureRate",
    # Usage metrics
    "TotalTokens",
    "InputTokens",
    "OutputTokens",
    "ContextTokens",
    "LLMCalls",
    "EmbeddingCalls",
    "RetrievalCalls",
    "RerankerCalls",
    "TokensPerCorrectAnswer",
    "RelevantEvidencePerContextToken",
    # Cost metrics
    "TotalCost",
    "CostPerToken",
    # Reliability metrics
    "SuccessRate",
    "ErrorRate",
    "Availability",
    "LatencyP50",
    "LatencyP99",
    # Stage deltas
    "F1AtK",
    "FirstRelevantRank",
    "DocumentRecall",
    "PageRecall",
    "RecallDelta",
    "PrecisionDelta",
    "NDCGDelta",
    "MRRDelta",
    "MAPDelta",
    "RankGain",
    "RankRegression",
    "GoldRetention",
    "NoiseRejection",
    "ItemRetentionRate",
    "SourceRetentionRate",
    "TopKChurn",
    "StageLatencyDelta",
    "QualityGainPerMs",
]
