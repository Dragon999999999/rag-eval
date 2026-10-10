"""Dependency-light paired statistical helpers for run comparisons."""

from __future__ import annotations

import math
from collections.abc import Sequence
from statistics import mean


def bootstrap_ci(
    values: Sequence[float],
    *,
    confidence: float = 0.95,
    resamples: int = 2000,
) -> tuple[float, float] | None:
    """Return a deterministic percentile bootstrap interval for a mean."""
    if not values:
        return None
    # A deterministic cyclic bootstrap avoids making statistical reports depend
    # on a process-global random seed.
    samples = []
    size = len(values)
    for offset in range(min(resamples, 2000)):
        samples.append(mean(values[(index + offset) % size] for index in range(size)))
    samples.sort()
    alpha = (1 - confidence) / 2
    return _quantile(samples, alpha), _quantile(samples, 1 - alpha)


def paired_permutation_pvalue(differences: Sequence[float]) -> float | None:
    """Estimate a paired two-sided permutation p-value by sign enumeration."""
    if not differences:
        return None
    observed = abs(mean(differences))
    total = 1 << len(differences)
    if total > 4096:
        total = 4096
    at_least = 0
    for mask in range(total):
        signed = [
            value if mask & (1 << index) else -value
            for index, value in enumerate(differences)
        ]
        if abs(mean(signed)) >= observed:
            at_least += 1
    return at_least / total


def cohens_dz(differences: Sequence[float]) -> float | None:
    """Return paired Cohen's dz effect size."""
    if not differences:
        return None
    center = mean(differences)
    if len(differences) < 2:
        return 0.0
    deviation = math.sqrt(
        sum((value - center) ** 2 for value in differences) / (len(differences) - 1)
    )
    return center / deviation if deviation else 0.0


def rank_biserial(differences: Sequence[float]) -> float | None:
    """Return the signed proportion of non-zero paired wins."""
    nonzero = [value for value in differences if value != 0]
    if not nonzero:
        return 0.0 if differences else None
    return (
        sum(value > 0 for value in nonzero) - sum(value < 0 for value in nonzero)
    ) / len(nonzero)


def cliffs_delta(left: Sequence[float], right: Sequence[float]) -> float | None:
    """Return Cliff's delta for two independent samples."""
    if not left or not right:
        return None
    wins = sum(a > b for a in left for b in right)
    losses = sum(a < b for a in left for b in right)
    return (wins - losses) / (len(left) * len(right))


def holm_bonferroni(p_values: Sequence[float]) -> list[float]:
    """Adjust p-values using Holm's step-down correction."""
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [0.0] * len(p_values)
    running = 0.0
    for rank, (index, value) in enumerate(indexed):
        running = max(running, min(1.0, (len(p_values) - rank) * value))
        adjusted[index] = running
    return adjusted


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Adjust p-values using the Benjamini-Hochberg procedure."""
    indexed = sorted(enumerate(p_values), key=lambda item: item[1])
    adjusted = [1.0] * len(p_values)
    running = 1.0
    for rank in range(len(indexed) - 1, -1, -1):
        index, value = indexed[rank]
        running = min(running, value * len(indexed) / (rank + 1))
        adjusted[index] = min(1.0, running)
    return adjusted


def _quantile(values: Sequence[float], fraction: float) -> float:
    if len(values) == 1:
        return float(values[0])
    position = max(0.0, min(1.0, fraction)) * (len(values) - 1)
    lower = math.floor(position)
    upper = math.ceil(position)
    if lower == upper:
        return float(values[lower])
    return values[lower] + (values[upper] - values[lower]) * (position - lower)


__all__ = [
    "benjamini_hochberg",
    "bootstrap_ci",
    "cliffs_delta",
    "cohens_dz",
    "holm_bonferroni",
    "paired_permutation_pvalue",
    "rank_biserial",
]
