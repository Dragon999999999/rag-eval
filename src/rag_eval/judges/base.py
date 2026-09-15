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


class DummyJudgeAdapter:
    """Deterministic dummy judge for testing.

    Returns fixed assessments without calling any model.
    Useful for testing metric framework without LLM dependencies.
    """

    def __init__(
        self,
        default_classification: str = "SUPPORTED",
        default_confidence: float = 0.9,
    ) -> None:
        """Initialize dummy judge with fixed outputs.

        Args:
            default_classification: Default claim classification.
            default_confidence: Default confidence score.
        """
        self._default_classification = default_classification
        self._default_confidence = default_confidence

    async def assess_claims(
        self,
        claims: list[Claim],
        evidence: list[SourceLocation] | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[ClaimAssessment]:
        """Return deterministic assessments for all claims."""
        from rag_eval.models.enums import ClaimClassification

        assessments = []
        for claim in claims:
            assessment = ClaimAssessment(
                claim_id=claim.claim_id,
                classification=ClaimClassification(self._default_classification),
                supporting_evidence=list(evidence) if evidence else [],
                contradicting_evidence=[],
                confidence=self._default_confidence,
                judge_metadata={"dummy": True, "context": context},
            )
            assessments.append(assessment)
        return assessments

    async def assess_evidence_relationship(
        self,
        claim: Claim,
        evidence: SourceLocation,
        context: dict[str, Any] | None = None,
    ) -> EvidenceAssessment:
        """Return deterministic evidence relationship assessment."""
        from rag_eval.models.enums import EvidenceRelationship

        return EvidenceAssessment(
            claim_id=claim.claim_id,
            evidence=evidence,
            relationship=EvidenceRelationship.ENTAILS,
            confidence=self._default_confidence,
            judge_metadata={"dummy": True, "context": context},
        )
