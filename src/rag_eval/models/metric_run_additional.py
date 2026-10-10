"""Canonical models for target assessment and decision outputs."""

from pydantic import Field

from rag_eval.models.common import CanonicalModel, JsonDict
from rag_eval.models.enums import DecisionAction


class Assessment(CanonicalModel):
    """One normalized assessment of a claim or answer dimension."""

    assessment_id: str
    assessor: str
    dimension: str
    label: str
    score: float | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)


class Decision(CanonicalModel):
    """A target or evaluator decision derived from assessments."""

    action: DecisionAction
    reason: str | None = None
    assessment_ids: list[str] = Field(default_factory=list)
    metadata: JsonDict = Field(default_factory=dict)
