"""Judge adapter protocol for model-based semantic evaluation.

Judges are separate from target execution. They evaluate claims,
evidence relationships, and other semantic judgments.

This is a minimal protocol - provider implementations come later.
"""

from typing import Any, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from rag_eval.models import Claim, ClaimAssessment, EvidenceAssessment
from rag_eval.models.common import SourceLocation


class JudgeConfiguration(BaseModel):
    """Validated, hashable configuration shared by judge implementations."""

    model_config = ConfigDict(extra="forbid")

    provider: str = "openai_compatible"
    model_id: str = "local-model"
    model_version: str | None = None
    prompt_id: str = "default"
    prompt_version: str = "1"
    temperature: float = Field(default=0.0, ge=0, le=2)
    max_tokens: int | None = Field(default=None, gt=0)
    retries: int = Field(default=2, ge=0)
    timeout_seconds: float = Field(default=120.0, gt=0)
    allow_reference_answer: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


@runtime_checkable
class JudgeAdapter(Protocol):
    """Protocol for semantic judge implementations.

    Judges evaluate claims against evidence, classify relationships,
    and perform other semantic assessments requiring model reasoning.

    Critical: Judges are NOT TargetAdapters. They evaluate offline
    using persisted data, not by calling the evaluated target.
    """

    @property
    def configuration(self) -> JudgeConfiguration:
        """Return the non-secret configuration used for judge calls."""
        ...

    async def configure(self, configuration: JudgeConfiguration) -> None:
        """Update judge configuration before scoring begins."""
        ...

    async def assess_claims_batch(
        self,
        batches: list[tuple[list[Claim], list[SourceLocation] | None]],
        context: dict[str, Any] | None = None,
    ) -> list[list[ClaimAssessment]]:
        """Assess independent claim batches while preserving batch order."""
        ...

    async def assess_claims(
        self,
        claims: list[Claim],
        evidence: list[SourceLocation] | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[ClaimAssessment]:
        """Assess claims against available evidence.

        Args:
            claims: Claims to assess.
            evidence: Optional evidence locations for assessment.
            context: Optional additional context for the judge.

        Returns:
            List of claim assessments with classifications.

        Note:
            Must not call TargetAdapter.
            Must operate on persisted data only.
        """
        ...

    async def assess_evidence_relationship(
        self,
        claim: Claim,
        evidence: SourceLocation,
        context: dict[str, Any] | None = None,
    ) -> EvidenceAssessment:
        """Assess relationship between one claim and one evidence item.

        Args:
            claim: Claim to assess.
            evidence: Evidence location to compare against.
            context: Optional additional context.

        Returns:
            Evidence assessment with relationship classification.
        """
        ...
