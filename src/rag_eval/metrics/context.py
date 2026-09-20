"""Metric context providing normalized access to scoring data.

Metrics receive MetricContext rather than raw ORM entities.
This keeps metrics independent of database/persistence details.
"""

from dataclasses import dataclass, field
from typing import Any

from rag_eval.models import BenchmarkCase, TargetObservation
from rag_eval.models.enums import RetrievalStageType


@dataclass(frozen=True)
class RetrievalStageView:
    """Read-only view of one retrieval stage.

    Preserves canonical stage distinctions without exposing ORM entities.
    """

    stage_id: str
    stage_type: RetrievalStageType
    parent_stage_id: str | None
    items: list[dict[str, Any]]
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MetricContext:
    """Context provided to metrics for computation.

    Provides normalized access to:
    - Benchmark case (truth)
    - Target observation (prediction)
    - Run metadata
    - Optional judge adapter

    Metrics must treat all data as immutable.
    """

    # Benchmark case (evaluator truth)
    case: BenchmarkCase

    # Target observation (target prediction) - immutable
    observation: TargetObservation | None = None

    # Run-level metadata
    run_id: str = ""
    run_metadata: dict[str, Any] = field(default_factory=dict)

    # Configuration metadata
    config_metadata: dict[str, Any] = field(default_factory=dict)

    # Optional judge (may be None if metric doesn't require it)
    judge: Any | None = None

    def has_answer(self) -> bool:
        """Check if target produced an answer.

        Explicit presence check, not truthiness.
        answer=None means no answer.
        answer.text="" means empty answer exists.
        """
        return self.observation is not None and self.observation.answer is not None

    def has_retrieval(self) -> bool:
        """Check if target produced retrieval results.

        Explicit presence check, not truthiness.
        retrieval=None means no retrieval.
        retrieval with zero items means retrieval executed but found nothing.
        """
        return self.observation is not None and self.observation.retrieval is not None

    def has_reference_answer(self) -> bool:
        """Check if benchmark has a reference answer.

        Explicit None check, not truthiness.
        Empty string reference answer still counts as present.
        """
        return self.case.reference_answer is not None

    def has_gold_evidence(self) -> bool:
        """Check if benchmark has gold evidence.

        Explicit check for non-empty evidence list.
        """
        return bool(self.case.gold_evidence)

    def has_citations(self) -> bool:
        """Check if target produced citations."""
        return (
            self.observation is not None
            and self.observation.answer is not None
            and bool(self.observation.answer.citations)
        )

    def has_confidence(self) -> bool:
        """Check if target produced confidence signals."""
        return self.observation is not None and bool(self.observation.confidence)

    def has_trace(self) -> bool:
        """Check if target produced execution trace."""
        return self.observation is not None and self.observation.trace is not None

    def has_usage(self) -> bool:
        """Check if target produced usage information."""
        return self.observation is not None and self.observation.usage is not None

    def get_retrieval_stage(
        self, stage_type: RetrievalStageType
    ) -> RetrievalStageView | None:
        """Get a specific retrieval stage by type.

        Args:
            stage_type: Canonical retrieval stage type to find.

        Returns:
            Read-only view of stage if available, None otherwise.
        """
        observation = self.observation
        if observation is None or observation.retrieval is None:
            return None

        retrieval = observation.retrieval
        if not retrieval.stages:
            return None

        for stage in retrieval.stages:
            if stage.type == stage_type:
                return RetrievalStageView(
                    stage_id=stage.stage_id,
                    stage_type=stage.type,
                    parent_stage_id=stage.parent_stage_id,
                    items=[item.model_dump(mode="json") for item in stage.items],
                    metadata=stage.metadata,
                )

        return None

    def get_final_context(self) -> RetrievalStageView | None:
        """Get the FINAL_CONTEXT retrieval stage.

        This is the evidence actually supplied to generation.
        Different from earlier candidate/reRanked stages.
        """
        return self.get_retrieval_stage(RetrievalStageType.FINAL_CONTEXT)

    def get_candidate_retrieval(self) -> RetrievalStageView | None:
        """Get the CANDIDATE_RETRIEVAL stage if available."""
        return self.get_retrieval_stage(RetrievalStageType.CANDIDATE_RETRIEVAL)

    def get_rerank(self) -> RetrievalStageView | None:
        """Get the RERANK stage if available."""
        return self.get_retrieval_stage(RetrievalStageType.RERANK)

    def get_citations(self) -> list[dict[str, Any]] | None:
        """Get target citations as normalized metric-friendly dictionaries.

        Returns:
            None if no answer exists.
            An empty list if an answer exists but contains no citations.
            Otherwise, normalized citation dictionaries.
        """
        if self.observation is None or self.observation.answer is None:
            return None

        return [
            citation.model_dump(mode="json")
            for citation in self.observation.answer.citations
        ]

    def get_answer_text(self) -> str | None:
        """Get target answer text if available.

        Returns None if no answer exists.
        May return empty string if answer exists but is empty.
        """
        observation = self.observation
        if observation is None or observation.answer is None:
            return None

        return observation.answer.text

    def get_reference_answer(self) -> str | None:
        """Get benchmark reference answer if available.

        Returns None if no reference exists.
        May return empty string if reference exists but is empty.
        """
        return self.case.reference_answer
