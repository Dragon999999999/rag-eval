"""Tests for the versioned public metric registry API."""

import pytest

from rag_eval.metrics.base import MetricDefinition, MetricScope
from rag_eval.metrics.registry import MetricRegistry


class RegistryMetric:
    """Minimal metric object accepted by ``MetricRegistry``."""

    def __init__(self, metric_id: str, version: str = "1") -> None:
        self._definition = MetricDefinition(
            metric_id=metric_id,
            version=version,
            scope=MetricScope.CASE,
            requirements=frozenset(),
            description="registry test metric",
        )

    @property
    def definition(self) -> MetricDefinition:
        """Return the registered definition."""
        return self._definition

    async def compute(self, context: object) -> object:
        """This implementation is not executed by registry tests."""
        raise NotImplementedError


def test_registry_registers_and_lists_versioned_definitions() -> None:
    """The public listing APIs expose IDs and definitions without internals."""
    registry = MetricRegistry()
    first = RegistryMetric("quality", "1")
    second = RegistryMetric("quality", "2")
    other = RegistryMetric("latency", "1")
    registry.register(first)
    registry.register(second)
    registry.register(other)

    assert len(registry) == 3
    assert registry.get("quality", "1") is first
    assert registry.get("missing") is None
    assert registry.get_required("quality", "2") is second
    assert registry.get_definition("quality", "2") == second.definition
    assert [definition.metric_id for definition in registry.list_metrics()] == [
        "quality",
        "quality",
        "latency",
    ]
    assert registry.list_metric_ids() == ["latency", "quality"]
    assert registry.get_versions("quality") == ["1", "2"]
    assert "quality" in registry
    assert "missing" not in registry


def test_registry_rejects_duplicate_identity_and_required_missing_metrics() -> None:
    """A duplicate identity cannot replace an existing implementation."""
    registry = MetricRegistry()
    registry.register(RegistryMetric("quality", "1"))
    with pytest.raises(ValueError, match="already registered"):
        registry.register(RegistryMetric("quality", "1"))
    with pytest.raises(KeyError, match="missing"):
        registry.get_required("missing")


def test_registry_clear_removes_all_versions() -> None:
    """The test-only reset API removes every registered version."""
    registry = MetricRegistry()
    registry.register(RegistryMetric("quality", "1"))
    registry.register(RegistryMetric("quality", "2"))
    registry.clear()
    assert len(registry) == 0
    assert registry.list_metrics() == []
    assert registry.list_metric_ids() == []
