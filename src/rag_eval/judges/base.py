"""Judge adapter protocol for model-based semantic evaluation.

Judges are separate from target execution. They evaluate claims,
evidence relationships, and other semantic judgments.

This is a minimal protocol - provider implementations come later.
"""

from typing import Any, Protocol, runtime_checkable

from rag_eval.models import Claim, ClaimAssessment, EvidenceAssessment
from rag_eval.models.common import SourceLocation


@runtime_checkable
class JudgeAdapter(Protocol):
    """Protocol for semantic judge implementations.

    Judges evaluate claims against evidence, classify relationships,
    and perform other semantic assessments requiring model reasoning.

    Critical: Judges are NOT TargetAdapters. They evaluate offline
    using persisted data, not by calling the evaluated target.
    """

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
