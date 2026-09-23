"""Run comparison service.

Compares two runs across common metrics.
Warns about incompatibilities (different benchmarks, corpora, etc.).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from rag_eval.db.test_repository import TestRepository


@dataclass(frozen=True)
class MetricComparison:
    """Comparison of one metric between two runs."""

    metric_id: str
    metric_version: str
    aggregation: str

    # Run A values
    value_a: Any
    available_a: int | None
    total_a: int | None

    # Run B values
    value_b: Any
    available_b: int | None
    total_b: int | None

    # Delta
    absolute_delta: float | None = None
    relative_delta: float | None = None

    # Direction (higher_is_better, lower_is_better, unknown)
    direction: str = "unknown"

    # Assessment (improved, regressed, unchanged, inconclusive)
    assessment: str = "inconclusive"


@dataclass(frozen=True)
class ComparisonResult:
    """Result of comparing two runs."""

    run_a_id: str
    run_b_id: str

    # Compatibility warnings
    warnings: list[str] = field(default_factory=list)
    compatible: bool = True

    # Metric comparisons
    comparisons: list[MetricComparison] = field(default_factory=list)

    # Summary
    improved_count: int = 0
    regressed_count: int = 0
    unchanged_count: int = 0
    inconclusive_count: int = 0


# Metric direction metadata
# higher_is_better, lower_is_better, or unknown
_METRIC_DIRECTIONS = {
    # Answer metrics
    "answer.exact_match": "higher_is_better",
    "answer.normalized_exact_match": "higher_is_better",
    "answer.token_precision": "higher_is_better",
    "answer.token_recall": "higher_is_better",
    "answer.token_f1": "higher_is_better",
    # Retrieval metrics
    "retrieval.hit_at_k": "higher_is_better",
    "retrieval.precision_at_k": "higher_is_better",
    "retrieval.recall_at_k": "higher_is_better",
    "retrieval.mrr": "higher_is_better",
    "retrieval.map_at_k": "higher_is_better",
    "retrieval.ndcg_at_k": "higher_is_better",
    "retrieval.r_precision": "higher_is_better",
    # Citation metrics
    "citation.resolution": "higher_is_better",
    "citation.attribution_rate": "higher_is_better",
    "citation.broken": "lower_is_better",  # Lower broken rate is better
    # Performance metrics
    "performance.total_latency_ms": "lower_is_better",
    "performance.retrieval_latency_ms": "lower_is_better",
    "performance.generation_latency_ms": "lower_is_better",
    "performance.tokens_per_second": "higher_is_better",
    # Usage metrics
    "usage.total_tokens": "lower_is_better",  # Generally want efficiency
    "usage.input_tokens": "lower_is_better",
    "usage.output_tokens": "lower_is_better",
    # Cost metrics
    "cost.total": "lower_is_better",
    "cost.per_token": "lower_is_better",
    # Reliability metrics
    "reliability.success_rate": "higher_is_better",
    "reliability.availability": "higher_is_better",
    "reliability.error_rate": "lower_is_better",
    "reliability.latency_p50": "lower_is_better",
    "reliability.latency_p99": "lower_is_better",
}


class RunComparator:
    """Compare two benchmark runs."""

    def __init__(self, repository: TestRepository) -> None:
        """Initialize comparator.

        Args:
            repository: Repository for data access.
        """
        self._repository = repository

    async def compare_runs(self, run_a_id: str, run_b_id: str) -> ComparisonResult:
        """Compare two runs.

        Args:
            run_a_id: First run identifier.
            run_b_id: Second run identifier.

        Returns:
            Comparison result with warnings and metric deltas.
        """
        warnings = []
        compatible = True

        # Load runs
        run_a = await self._repository.get_run(run_a_id)
        run_b = await self._repository.get_run(run_b_id)

        if run_a is None:
            raise KeyError(f"Run {run_a_id} not found")
        if run_b is None:
            raise KeyError(f"Run {run_b_id} not found")

        # Check compatibility
        # Note: Different target/config is OK - that's what we're comparing
        # But different benchmark/corpus is a compatibility issue

        # Load configs to check benchmark identity
        config_a = await self._repository.get_run_config(run_a_id)
        config_b = await self._repository.get_run_config(run_b_id)

        if config_a and config_b:
            # Check benchmark name/version
            benchmark_a = config_a.canonical_config.get("dataset", {})
            benchmark_b = config_b.canonical_config.get("dataset", {})

            if benchmark_a.get("name") != benchmark_b.get("name"):
                warnings.append(
                    f"Different benchmarks: {benchmark_a.get('name')} "
                    f"vs {benchmark_b.get('name')}"
                )
                compatible = False

            if benchmark_a.get("version") != benchmark_b.get("version"):
                warnings.append(
                    f"Different benchmark versions: {benchmark_a.get('version')} "
                    f"vs {benchmark_b.get('version')}"
                )
                # Don't mark incompatible - version differences may be intentional

            # Check corpus hash
            corpus_a = config_a.canonical_config.get("target", {}).get("corpus", {})
            corpus_b = config_b.canonical_config.get("target", {}).get("corpus", {})

            if corpus_a.get("mode") != corpus_b.get("mode"):
                warnings.append(
                    f"Different corpus modes: {corpus_a.get('mode')} "
                    f"vs {corpus_b.get('mode')}"
                )

        # Load aggregates for both runs
        aggregates_a = await self._repository.list_aggregates(run_a_id)
        aggregates_b = await self._repository.list_aggregates(run_b_id)

        # Build lookup: (metric_id, aggregation) -> aggregate
        agg_lookup_a = {
            (a.metric_id, a.aggregation, a.metric_version): a for a in aggregates_a
        }
        agg_lookup_b = {
            (a.metric_id, a.aggregation, a.metric_version): a for a in aggregates_b
        }

        # Find common metrics
        common_keys = set(agg_lookup_a.keys()) & set(agg_lookup_b.keys())

        comparisons = []
        improved = 0
        regressed = 0
        unchanged = 0
        inconclusive = 0

        for metric_id, aggregation, version in sorted(common_keys):
            agg_a = agg_lookup_a[(metric_id, aggregation, version)]
            agg_b = agg_lookup_b[(metric_id, aggregation, version)]

            comparison = self._compare_metric(
                metric_id=metric_id,
                version=version,
                aggregation=aggregation,
                value_a=agg_a.value,
                available_a=agg_a.details.get(
                    "available_count", agg_a.details.get("computed_count")
                ),
                total_a=agg_a.details.get("sample_count"),
                value_b=agg_b.value,
                available_b=agg_b.details.get(
                    "available_count", agg_b.details.get("computed_count")
                ),
                total_b=agg_b.details.get("sample_count"),
            )

            comparisons.append(comparison)

            if comparison.assessment == "improved":
                improved += 1
            elif comparison.assessment == "regressed":
                regressed += 1
            elif comparison.assessment == "unchanged":
                unchanged += 1
            else:
                inconclusive += 1

        return ComparisonResult(
            run_a_id=run_a_id,
            run_b_id=run_b_id,
            warnings=warnings,
            compatible=compatible,
            comparisons=comparisons,
            improved_count=improved,
            regressed_count=regressed,
            unchanged_count=unchanged,
            inconclusive_count=inconclusive,
        )

    def _compare_metric(
        self,
        metric_id: str,
        version: str,
        aggregation: str,
        value_a: Any,
        available_a: int | None,
        total_a: int | None,
        value_b: Any,
        available_b: int | None,
        total_b: int | None,
    ) -> MetricComparison:
        """Compare one metric between runs."""
        direction = _METRIC_DIRECTIONS.get(metric_id, "unknown")

        # Compute deltas
        absolute_delta = None
        relative_delta = None

        if value_a is not None and value_b is not None:
            try:
                absolute_delta = float(value_b) - float(value_a)

                # Relative delta (avoid divide by zero)
                if value_a != 0:
                    relative_delta = (
                        (float(value_b) - float(value_a)) / abs(float(value_a)) * 100
                    )
            except (TypeError, ValueError):
                pass

        # Determine assessment
        assessment = "inconclusive"
        if absolute_delta is not None:
            if direction == "higher_is_better":
                if absolute_delta > 0.0001:  # Small epsilon for float comparison
                    assessment = "improved"
                elif absolute_delta < -0.0001:
                    assessment = "regressed"
                else:
                    assessment = "unchanged"
            elif direction == "lower_is_better":
                if absolute_delta < -0.0001:
                    assessment = "improved"
                elif absolute_delta > 0.0001:
                    assessment = "regressed"
                else:
                    assessment = "unchanged"
            else:
                # Unknown direction - just report delta
                if absolute_delta != 0:
                    assessment = "unchanged"  # Direction is unknown.
                else:
                    assessment = "unchanged"

        return MetricComparison(
            metric_id=metric_id,
            metric_version=version,
            aggregation=aggregation,
            value_a=value_a,
            available_a=available_a,
            total_a=total_a,
            value_b=value_b,
            available_b=available_b,
            total_b=total_b,
            absolute_delta=absolute_delta,
            relative_delta=relative_delta,
            direction=direction,
            assessment=assessment,
        )
