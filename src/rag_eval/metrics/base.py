"""Base metric protocol and requirement detection for rag-eval.

Metrics operate only on persisted benchmark truth and TargetObservations.
They must never call the evaluated target.
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Protocol, runtime_checkable

from rag_eval.models.enums import MetricStatus
from rag_eval.metrics.context import MetricContext


class MetricScope(Enum):
    """Scope at which a metric operates."""

    CASE = auto()  # Single case/observation
    RETRIEVAL_STAGE = auto()  # Specific retrieval stage
    CLAIM = auto()  # Individual claim
    RUN = auto()  # Entire run aggregation


class MetricRequirement(Enum):
    """Required inputs for metric computation.

    These are explicit requirements, not truthiness checks.
    A metric requiring ANSWER needs answer to exist, not just be non-empty.
    """

    # Benchmark case requirements
    QUERY = auto()
    HISTORY = auto()
    REFERENCE_ANSWER = auto()
    GOLD_EVIDENCE = auto()
    ANSWERABILITY = auto()

    # Target observation requirements
    ANSWER = auto()
    RETRIEVAL = auto()
    FINAL_CONTEXT = auto()
    CITATIONS = auto()
    CONFIDENCE = auto()
    TRACE = auto()
    USAGE = auto()

    # Judge requirements
    JUDGE = auto()

    # Metadata requirements
    RUN_METADATA = auto()


@dataclass(frozen=True, slots=True)
class MetricRequirementCheck:
    """Result of checking one requirement against available data."""

    requirement: MetricRequirement
    satisfied: bool
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class MetricDefinition:
    """Static definition of a metric independent of execution.

    This separates metric identity/requirements from execution logic.
    """

    metric_id: str
    version: str
    scope: MetricScope
    requirements: frozenset[MetricRequirement]
    description: str = ""


@runtime_checkable
class Metric(Protocol):
    """Protocol for metric implementations.

    Metrics receive MetricContext with benchmark data and observations.
    They return MetricResult with status and optional value.

    Critical invariant: Metrics must never call TargetAdapter.
    """

    @property
    def definition(self) -> MetricDefinition:
        """Return static metric definition including identity and requirements."""
        ...

    async def compute(self, context: MetricContext) -> "MetricResult":
        """Compute metric value from persisted data.

        Args:
            context: Metric context with benchmark case, observation, and metadata.

        Returns:
            Metric result with status and optional value.

        Note:
            Must not call TargetAdapter or execute target operations.
            Must not modify TargetObservation (immutable input).
        """
        ...


@dataclass
class MetricResult:
    """Result of one metric computation.

    Uses canonical status to distinguish:
    - COMPUTED: metric executed successfully
    - UNAVAILABLE_MISSING_INPUT: required input does not exist
    - NOT_APPLICABLE: metric logically does not apply
    - FAILED: metric execution attempted and failed
    - SKIPPED: metric intentionally not executed

    Critical: None value with COMPUTED status is valid (e.g., metric returns null).
    None value with UNAVAILABLE_MISSING_INPUT means required data missing.
    """

    metric_id: str
    metric_version: str
    status: MetricStatus
    value: float | int | bool | str | None = None
    reason: str | None = None
    details: dict[str, object] = field(default_factory=dict)
    case_id: str | None = None
    run_id: str | None = None

    def is_computed(self) -> bool:
        """Check if metric was successfully computed."""
        return self.status == MetricStatus.COMPUTED

    def is_unavailable(self) -> bool:
        """Check if metric is unavailable due to missing input."""
        return self.status == MetricStatus.UNAVAILABLE_MISSING_INPUT

    def is_failed(self) -> bool:
        """Check if metric execution failed."""
        return self.status == MetricStatus.FAILED
