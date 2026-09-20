"""Canonical models for persisted metric and semantic assessment outputs."""

from datetime import datetime

from pydantic import Field, field_validator, model_validator

from rag_eval.models.common import (
    CanonicalModel,
    JsonDict,
    SourceLocation,
    validate_aware_timestamp,
)
from rag_eval.models.enums import (
    ClaimClassification,
    EvidenceRelationship,
    MetricStatus,
)
from rag_eval.models.target import AnswerSpan


class MetricResult(CanonicalModel):
    """One case- or run-scoped metric outcome without conflating null and zero."""

    metric_result_id: str
    metric_id: str
    metric_version: str
    status: MetricStatus
    value: float | int | bool | str | None = None
    run_id: str | None = None
    case_id: str | None = None
    reason: str | None = None
    details: JsonDict = Field(default_factory=dict)
    evaluator_metadata: JsonDict = Field(default_factory=dict)
    created_at: datetime | None = None

    _validate_created_at = field_validator("created_at")(validate_aware_timestamp)

    @model_validator(mode="after")
    def validate_null_value_reason(self) -> "MetricResult":
        """Require an explanation when a metric does not carry a value."""
        if self.value is None and self.reason is None:
            raise ValueError("a null metric value requires a reason")
        return self


class AggregateMetricResult(CanonicalModel):
    """Run-level aggregation kept distinct from individual metric results."""

    run_id: str

    metric_id: str
    metric_version: str
    aggregation: str

    value: float | int | bool | str | None
    status: MetricStatus
    reason: str | None = None

    sample_count: int = Field(ge=0)
    available_count: int = Field(ge=0)
    failed_count: int = Field(ge=0)

    distribution: JsonDict = Field(default_factory=dict)
    metadata: JsonDict = Field(default_factory=dict)


class Claim(CanonicalModel):
    """A derived claim from an answer, reference, or evidence source."""

    claim_id: str
    text: str
    source: str
    answer_span: AnswerSpan | None = None
    metadata: JsonDict = Field(default_factory=dict)


class ClaimAssessment(CanonicalModel):
    """Semantic classification of a claim against available evidence."""

    claim_id: str
    classification: ClaimClassification
    supporting_evidence: list[SourceLocation] = Field(default_factory=list)
    contradicting_evidence: list[SourceLocation] = Field(default_factory=list)
    score: float | None = None
    confidence: float | None = None
    judge_metadata: JsonDict = Field(default_factory=dict)


class EvidenceAssessment(CanonicalModel):
    """Semantic relationship between a claim and one evidence location."""

    claim_id: str
    evidence: SourceLocation
    relationship: EvidenceRelationship
    score: float | None = None
    confidence: float | None = None
    judge_metadata: JsonDict = Field(default_factory=dict)
