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
    parent_stage_ids: list[str]
    component_name: str | None
    parameters: dict[str, Any]
    trace_span_id: str | None
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
        """Check if an answer observation exposed a citation collection.

        An empty collection is present data and is intentionally different from
        an absent answer observation.
        """
        return (
            self.observation is not None
            and self.observation.answer is not None
        )

    def has_claims(self) -> bool:
        """Check whether the target exposed claims, including an empty list."""
        return self.observation is not None and self.observation.claims is not None

    def has_assessments(self) -> bool:
        """Check whether the target exposed assessments, including empty ones."""
        return self.observation is not None and self.observation.assessments is not None

    def has_decision(self) -> bool:
        """Check whether the target exposed a decision."""
        return self.observation is not None and self.observation.decision is not None

    def has_component_trace(self) -> bool:
        """Check whether the target trace contains at least one named component."""
        return self.has_trace() and any(
            span.component_name or span.name
            for span in self.observation.trace.spans
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

        return self.get_retrieval_stage_by_type(stage_type)

    def get_retrieval_stage_by_id(self, stage_id: str) -> RetrievalStageView | None:
        """Get a stage by stable stage identity."""
        if self.observation is None or self.observation.retrieval is None:
            return None
        for stage in self.observation.retrieval.stages:
            if stage.stage_id == stage_id:
                return self._stage_view(stage)
        return None

    def get_retrieval_stage_by_type(
        self, stage_type: RetrievalStageType
    ) -> RetrievalStageView | None:
        """Get the first stage of a canonical type."""
        if self.observation is None or self.observation.retrieval is None:
            return None
        for stage in self.observation.retrieval.stages:
            if stage.type == stage_type:
                return self._stage_view(stage)
        return None

    def list_stages(
        self, stage_type: RetrievalStageType | None = None
    ) -> list[RetrievalStageView]:
        """List all exposed stages, optionally filtered by canonical type."""
        if self.observation is None or self.observation.retrieval is None:
            return []
        return [
            self._stage_view(stage)
            for stage in self.observation.retrieval.stages
            if stage_type is None or stage.type == stage_type
        ]

    def stage_present(
        self,
        *,
        stage_id: str | None = None,
        stage_type: RetrievalStageType | None = None,
    ) -> bool:
        """Return whether a stage executed, including when it returned zero items."""
        if stage_id is not None:
            return self.get_retrieval_stage_by_id(stage_id) is not None
        if stage_type is not None:
            return bool(self.list_stages(stage_type))
        return bool(self.list_stages())

    def get_before_after_stage(
        self, before_stage_id: str, after_stage_id: str
    ) -> tuple[RetrievalStageView | None, RetrievalStageView | None]:
        """Return a requested before/after pair without inferring missing stages."""
        return (
            self.get_retrieval_stage_by_id(before_stage_id),
            self.get_retrieval_stage_by_id(after_stage_id),
        )

    @staticmethod
    def _stage_view(stage: Any) -> RetrievalStageView:
        """Convert a canonical stage to a metric-facing immutable view."""
        return RetrievalStageView(
            stage_id=stage.stage_id,
            stage_type=stage.type,
            parent_stage_id=stage.parent_stage_id,
            parent_stage_ids=list(stage.parent_stage_ids),
            component_name=stage.component_name,
            parameters=dict(stage.parameters),
            trace_span_id=stage.trace_span_id,
            items=[item.model_dump(mode="json") for item in stage.items],
            metadata=stage.metadata,
        )

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

    def get_claims(self) -> list[dict[str, Any]] | None:
        """Return normalized claims, or None when claims were not exposed."""
        if self.observation is None or self.observation.claims is None:
            return None
        return [claim.model_dump(mode="json") for claim in self.observation.claims]

    def get_assessments(self) -> list[dict[str, Any]] | None:
        """Return normalized assessments, or None when absent."""
        if self.observation is None or self.observation.assessments is None:
            return None
        return [
            assessment.model_dump(mode="json")
            for assessment in self.observation.assessments
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
