"""Explicit metric registry with versioned identity.

Metrics are registered by (metric_id, version) tuple.
Duplicate registrations are rejected to prevent accidental overwrites.
"""

import logging

from .base import Metric, MetricDefinition

logger = logging.getLogger(__name__)


class MetricRegistry:
    """Registry for metric implementations.

    Metrics are identified by (metric_id, version) tuple.
    Registration is explicit - no automatic discovery.

    Thread-safe for concurrent reads, not for concurrent modification.
    """

    def __init__(self) -> None:
        """Initialize empty metric registry."""
        # Key: (metric_id, version) -> Metric instance
        self._metrics: dict[tuple[str, str], Metric] = {}

    def register(self, metric: Metric) -> None:
        """Register a metric implementation.

        Args:
            metric: Metric instance to register.

        Raises:
            ValueError: If metric with same ID and version already registered.
        """
        key = (metric.definition.metric_id, metric.definition.version)

        if key in self._metrics:
            existing = self._metrics[key]
            raise ValueError(
                f"Metric '{metric.definition.metric_id}' version "
                f"'{metric.definition.version}' already registered. "
                f"Existing: {type(existing).__module__}.{type(existing).__name__}, "
                f"New: {type(metric).__module__}.{type(metric).__name__}"
            )

        self._metrics[key] = metric
        logger.debug(
            "Registered metric: %s v%s",
            metric.definition.metric_id,
            metric.definition.version,
        )

    def get(self, metric_id: str, version: str = "1") -> Metric | None:
        """Get a metric by ID and version.

        Args:
            metric_id: Metric identifier.
            version: Metric version (default: "1").

        Returns:
            Metric instance if registered, None otherwise.
        """
        return self._metrics.get((metric_id, version))

    def get_required(self, metric_id: str, version: str = "1") -> Metric:
        """Get a metric, raising if not found.

        Args:
            metric_id: Metric identifier.
            version: Metric version (default: "1").

        Returns:
            Metric instance.

        Raises:
            KeyError: If metric not registered.
        """
        metric = self.get(metric_id, version)
        if metric is None:
            raise KeyError(
                f"Metric '{metric_id}' version '{version}' not registered. "
                f"Available metrics: {sorted(set(k[0] for k in self._metrics.keys()))}"
            )
        return metric

    def list_metrics(self) -> list[MetricDefinition]:
        """List all registered metric definitions.

        Returns:
            List of metric definitions (identity and requirements only).
        """
        return [metric.definition for metric in self._metrics.values()]

    def get_definition(
        self,
        metric_id: str,
        version: str = "1",
    ) -> MetricDefinition | None:
        """Get one registered metric definition by ID and version.

        Args:
            metric_id: Metric identifier.
            version: Metric version.

        Returns:
            Metric definition if registered, otherwise None.
        """
        metric = self.get(
            metric_id,
            version,
        )

        if metric is None:
            return None

        return metric.definition

    def list_metric_ids(self) -> list[str]:
        """List all unique metric IDs (all versions).

        Returns:
            Sorted list of unique metric identifiers.
        """
        return sorted(set(metric_id for metric_id, _ in self._metrics.keys()))

    def get_versions(self, metric_id: str) -> list[str]:
        """Get all registered versions for a metric ID.

        Args:
            metric_id: Metric identifier.

        Returns:
            Sorted list of registered versions.
        """
        return sorted(
            version for mid, version in self._metrics.keys() if mid == metric_id
        )

    def clear(self) -> None:
        """Clear all registered metrics.

        Use primarily for testing.
        """
        self._metrics.clear()

    def __len__(self) -> int:
        """Return number of registered metrics."""
        return len(self._metrics)

    def __contains__(self, metric_id: str) -> bool:
        """Check if any version of a metric is registered."""
        return any(mid == metric_id for mid, _ in self._metrics.keys())
