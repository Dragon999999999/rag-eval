"""Aggregation utilities for run-level metric statistics.

Supports common numeric aggregations with explicit coverage tracking.
Only aggregates COMPUTED status values - never converts unavailable/failed to zero.
"""

import math
from dataclasses import dataclass, field
from typing import Any

from rag_eval.models import AggregateMetricResult as AggregateMetricResultModel
from rag_eval.models.enums import MetricStatus


@dataclass(frozen=True)
class AggregationResult:
    """Result of aggregating metric values.

    Includes coverage counts to distinguish:
    - total cases
    - computed (available for aggregation)
    - unavailable (missing input)
    - failed (execution error)
    """

    metric_id: str
    metric_version: str
    aggregation_name: str
    value: float | int | None
    total_count: int
    computed_count: int
    unavailable_count: int
    failed_count: int
    metadata: dict[str, Any] = field(default_factory=dict)


def compute_aggregations(
    metric_id: str,
    metric_version: str,
    values: list[float | int],
    statuses: list[MetricStatus],
) -> list[AggregationResult]:
    """Compute standard aggregations for one metric.

    Args:
        metric_id: Metric identifier.
        metric_version: Metric version.
        values: Computed numeric values (only COMPUTED status).
        statuses: All statuses (for coverage counts).

    Returns:
        List of aggregation results (mean, median, std, percentiles, etc.).
    """
    total_count = len(statuses)
    computed_count = sum(1 for s in statuses if s == MetricStatus.COMPUTED)
    unavailable_count = sum(
        1 for s in statuses if s == MetricStatus.UNAVAILABLE_MISSING_INPUT
    )
    failed_count = sum(1 for s in statuses if s == MetricStatus.FAILED)

    if not values:
        return [
            AggregationResult(
                metric_id=metric_id,
                metric_version=metric_version,
                aggregation_name="count",
                value=0,
                total_count=total_count,
                computed_count=computed_count,
                unavailable_count=unavailable_count,
                failed_count=failed_count,
            )
        ]

    results = [
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="count",
            value=len(values),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="mean",
            value=round(sum(values) / len(values), 6),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="median",
            value=_compute_percentile(values, 50),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="min",
            value=min(values),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="max",
            value=max(values),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="std",
            value=round(_compute_std(values), 6) if len(values) > 1 else 0.0,
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="p50",
            value=_compute_percentile(values, 50),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="p75",
            value=_compute_percentile(values, 75),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="p90",
            value=_compute_percentile(values, 90),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="p95",
            value=_compute_percentile(values, 95),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
        AggregationResult(
            metric_id=metric_id,
            metric_version=metric_version,
            aggregation_name="p99",
            value=_compute_percentile(values, 99),
            total_count=total_count,
            computed_count=computed_count,
            unavailable_count=unavailable_count,
            failed_count=failed_count,
        ),
    ]

    return results


def _compute_percentile(values: list[float | int], percentile: float) -> float:
    """Compute percentile using linear interpolation method.

    Args:
        values: Sorted list of values.
        percentile: Percentile to compute (0-100).

    Returns:
        Percentile value.
    """
    if not values:
        return 0.0

    sorted_values = sorted(values)
    n = len(sorted_values)

    if n == 1:
        return float(sorted_values[0])

    # Linear interpolation method
    k = (percentile / 100.0) * (n - 1)
    f = math.floor(k)
    c = math.ceil(k)

    if f == c:
        return float(sorted_values[int(k)])

    d0 = sorted_values[int(f)] * (c - k)
    d1 = sorted_values[int(c)] * (k - f)

    return round(d0 + d1, 6)


def _compute_std(values: list[float | int]) -> float:
    """Compute sample standard deviation.

    Args:
        values: List of values.

    Returns:
        Sample standard deviation.
    """
    if len(values) < 2:
        return 0.0

    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)

    return math.sqrt(variance)


def convert_to_canonical(
    agg: AggregationResult, run_id: str
) -> AggregateMetricResultModel:
    """Convert aggregation result to canonical model for persistence.

    Args:
        agg: Aggregation result.
        run_id: Run identifier.

    Returns:
        Canonical aggregate metric result model.
    """
    return AggregateMetricResultModel(
        metric_id=agg.metric_id,
        metric_version=agg.metric_version,
        aggregation=agg.aggregation_name,
        value=agg.value,
        sample_count=agg.total_count,
        available_count=agg.computed_count,
        failed_count=agg.failed_count,
        distribution={
            "unavailable_count": agg.unavailable_count,
        },
        metadata=agg.metadata,
    )
