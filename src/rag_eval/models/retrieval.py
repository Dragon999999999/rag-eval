"""Canonical retrieval observations, including multi-stage pipelines."""

from pydantic import Field

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
    items: list[RetrievedItem] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)


class RetrievalResult(CanonicalModel):
    """All exposed retrieval stages for a completed target operation."""

    stages: list[RetrievalStage] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)
