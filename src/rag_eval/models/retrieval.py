"""Canonical retrieval observations, including multi-stage pipelines."""

from pydantic import Field, model_validator

from rag_eval.models.common import CanonicalModel, JsonDict, SourceLocation
from rag_eval.models.enums import RetrievalStageType


class RetrievalScore(CanonicalModel):
    """A score whose type makes cross-system interpretation explicit."""

    value: float
    type: str
    metadata: JsonDict = Field(default_factory=dict)


class RetrievedItem(CanonicalModel):
    """One rank-ordered item observed within a retrieval stage."""

    retrieval_id: str
    rank: int = Field(ge=1)
    text: str | None = None
    source: SourceLocation | None = None
    score: RetrievalScore | None = None
    metadata: JsonDict = Field(default_factory=dict)


class RetrievalStage(CanonicalModel):
    """A transformation stage in a target retrieval pipeline."""

    stage_id: str
    type: RetrievalStageType
    parent_stage_id: str | None = None
    parent_stage_ids: list[str] = Field(default_factory=list)
    component_name: str | None = None
    parameters: JsonDict = Field(default_factory=dict)
    trace_span_id: str | None = None
    items: list[RetrievedItem] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def normalize_parent_stage_ids(self) -> "RetrievalStage":
        """Keep the legacy singular parent and graph form in sync."""
        parents = list(dict.fromkeys(self.parent_stage_ids))
        if self.parent_stage_id is not None and self.parent_stage_id not in parents:
            parents.insert(0, self.parent_stage_id)
        self.parent_stage_ids = parents
        if self.parent_stage_id is None and parents:
            self.parent_stage_id = parents[0]
        return self


class RetrievalResult(CanonicalModel):
    """All exposed retrieval stages for a completed target operation."""

    stages: list[RetrievalStage] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)

    @model_validator(mode="after")
    def validate_unique_stage_ids(self) -> "RetrievalResult":
        """Reject duplicate stage identities that make graph metrics ambiguous."""
        stage_ids = [stage.stage_id for stage in self.stages]
        if len(stage_ids) != len(set(stage_ids)):
            raise ValueError("retrieval stage IDs must be unique")
        return self
