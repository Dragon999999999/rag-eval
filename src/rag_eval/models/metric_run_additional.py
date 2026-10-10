"""Canonical models for target assessment and decision outputs."""

from datetime import datetime

from pydantic import Field, field_validator

from rag_eval.models.common import CanonicalModel, JsonDict, validate_aware_timestamp
from rag_eval.models.enums import DecisionAction, MetricStatus


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


class JudgeResult(CanonicalModel):
    """One persisted semantic-judge outcome independent of target output."""

    judge_result_id: str
    metric_id: str
    metric_version: str
    score: float | None = None
    label: str | None = None
    reasoning_summary: str | None = None
    evidence_ids: list[str] = Field(default_factory=list)
    claim_ids: list[str] = Field(default_factory=list)
    confidence: float | None = None
    judge_model: str | None = None
    prompt_version: str | None = None
    usage: JsonDict = Field(default_factory=dict)
    latency_ms: float | None = Field(default=None, ge=0)
    status: MetricStatus = MetricStatus.COMPUTED
    cache_key: str | None = None
    metadata: JsonDict = Field(default_factory=dict)
    created_at: datetime | None = None

    _validate_created_at = field_validator("created_at")(validate_aware_timestamp)
