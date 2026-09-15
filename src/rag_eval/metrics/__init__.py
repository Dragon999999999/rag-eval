"""Metric execution engine and framework for rag-eval.

This package provides:
- Metric protocol and requirement detection
- Metric registry with versioned identity
- Metric execution engine with isolation
- Aggregation utilities
- Scoring service (no TargetAdapter dependency)

Metrics operate only on persisted benchmark truth and TargetObservations.
They must never call the evaluated target.
"""

from .aggregation import (
    AggregationResult,
    compute_aggregations,
    convert_to_canonical,
)
from .base import (
    Metric,
    MetricDefinition,
    MetricRequirement,
    MetricRequirementCheck,
    MetricResult,
    MetricScope,
)
from .context import MetricContext, RetrievalStageView
from .engine import MetricExecutionEngine, ScoringConfig
from .registry import MetricRegistry
from .service import ScoringService, ScoringResult

__all__ = [
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
]
