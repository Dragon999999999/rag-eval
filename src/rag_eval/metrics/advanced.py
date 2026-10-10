"""Deterministic and judge-gated metrics for the advanced evaluation catalog.

The catalog intentionally keeps metric execution offline: target observations,
benchmark annotations, and an injected judge are the only inputs.  Provider
specific semantic behavior is isolated behind the optional judge interface;
metrics remain unavailable rather than silently treating missing annotations as
negative evidence.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext, RetrievalStageView


def _tokens(value: str | None) -> set[str]:
    return set(re.findall(r"\w+", (value or "").lower()))


def _overlap(left: str | None, right: str | None) -> float:
    a, b = _tokens(left), _tokens(right)
    return len(a & b) / len(a | b) if a or b else 1.0


def _stage_pair(
    context: MetricContext,
) -> tuple[RetrievalStageView, RetrievalStageView] | None:
    stages = context.list_stages()
    for after in stages:
        for parent_id in after.parent_stage_ids:
            before = context.get_retrieval_stage_by_id(parent_id)
            if before is not None:
                return before, after
    return (stages[0], stages[1]) if len(stages) >= 2 else None


def _items_text(stage: RetrievalStageView) -> str:
    return " ".join(str(item.get("text") or "") for item in stage.items)


def _relevant_ids(context: MetricContext) -> set[str]:
    gold = {item.document_id for item in context.case.gold_evidence}
    result: set[str] = set()
    for stage in context.list_stages():
        for item in stage.items:
            source = item.get("source") or {}
            if source.get("document_id") in gold:
                result.add(str(item.get("retrieval_id")))
    return result


@dataclass
class AdvancedMetric:
    """Reusable implementation for a registered advanced metric identity."""

    metric_id: str
    requirements: frozenset[MetricRequirement]
    scope: MetricScope = MetricScope.CASE
    description: str = "Advanced evaluation metric."
    judge_required: bool = False
    direction: str = "unknown"

    @property
    def definition(self) -> MetricDefinition:
        return MetricDefinition(
            metric_id=self.metric_id,
            version="1",
            scope=self.scope,
            requirements=self.requirements,
            description=self.description,
            metric_family=self.metric_id.split(".", 1)[0],
            direction=self.direction,
            judge_required=self.judge_required,
        )

    async def compute(self, context: MetricContext) -> MetricResult:
        """Compute one metric from persisted inputs and explicit requirements."""
        if self.judge_required and context.judge is None:
            return self._unavailable(context, "judge is required")
        judged_value = await self._judge_value(context)
        if judged_value is not None:
            return MetricResult(
                metric_id=self.metric_id,
                metric_version="1",
                status=MetricStatus.COMPUTED,
                value=judged_value,
                case_id=context.case.case_id,
                run_id=context.run_id,
            )
        value = self._value(context)
        if value is None:
            return self._unavailable(context, "required advanced input is unavailable")
        return MetricResult(
            metric_id=self.metric_id,
            metric_version="1",
            status=MetricStatus.COMPUTED,
            value=value,
            case_id=context.case.case_id,
            run_id=context.run_id,
        )

    async def _judge_value(self, context: MetricContext) -> float | None:
        """Use provider-backed scoring for semantic metrics when available."""
        if context.judge is None:
            return None
        claims = context.observation.claims if context.observation else None
        if self.metric_id.startswith(("faithfulness.", "hallucination.")):
            assess_claims = getattr(context.judge, "assess_claims", None)
            if claims and callable(assess_claims):
                assessments = await assess_claims(
                    claims,
                    context={"query": context.case.query},
                )
                supported = sum(
                    str(item.classification).upper() in {"SUPPORTED", "ENTAILS"}
                    for item in assessments
                )
                rate = supported / len(assessments) if assessments else 0.0
                return 1.0 - rate if "unsupported" in self.metric_id else rate
            return None
        if not (
            self.metric_id.startswith(("answer.", "context.", "claim.", "citation."))
            and self.metric_id
            not in {"answer.off_topic_rate", "citation.overcitation_rate"}
        ):
            return None
        assess_answer = getattr(context.judge, "assess_answer", None)
        answer = context.get_answer_text()
        if not callable(assess_answer) or answer is None:
            return None
        judged = await assess_answer(answer, context.case.query)
        score = judged.get("score")
        return float(score) if isinstance(score, (int, float)) else None

    def _unavailable(self, context: MetricContext, reason: str) -> MetricResult:
        return MetricResult(
            metric_id=self.metric_id,
            metric_version="1",
            status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
            reason=reason,
            case_id=context.case.case_id,
            run_id=context.run_id,
        )

    def _value(self, context: MetricContext) -> float | int | bool | None:
        metric_id = self.metric_id
        answer = context.observation.answer.text if context.has_answer() else None
        references = list(context.case.reference_answers)
        if context.case.reference_answer is not None:
            references.insert(0, context.case.reference_answer)
        reference = references[0] if references else None

        if metric_id in {
            "answer.relevance",
            "answer.query_coverage",
            "answer.responsiveness",
        }:
            if answer is None:
                return None
            return _overlap(context.case.query, answer)
        if metric_id == "answer.off_topic_rate":
            value = self._value_for("answer.relevance", context)
            return None if value is None else 1.0 - float(value)

        if metric_id.startswith("answer."):
            if answer is None or reference is None:
                return None
            score = _overlap(answer, reference)
            if metric_id.endswith("factual_precision"):
                return len(_tokens(answer) & _tokens(reference)) / max(
                    len(_tokens(answer)), 1
                )
            if metric_id.endswith("factual_recall") or metric_id.endswith(
                "completeness"
            ):
                return len(_tokens(answer) & _tokens(reference)) / max(
                    len(_tokens(reference)), 1
                )
            if metric_id.endswith("factual_f1"):
                precision = len(_tokens(answer) & _tokens(reference)) / max(
                    len(_tokens(answer)), 1
                )
                recall = len(_tokens(answer) & _tokens(reference)) / max(
                    len(_tokens(reference)), 1
                )
                return (
                    2 * precision * recall / (precision + recall)
                    if precision + recall
                    else 0.0
                )
            if metric_id.endswith("conciseness"):
                return min(1.0, len(_tokens(reference)) / max(len(_tokens(answer)), 1))
            if metric_id.endswith("structured_output_validity"):
                return float(context.observation.answer.structured_output is not None)
            return score

        if metric_id.startswith(("faithfulness.", "hallucination.")):
            if not context.has_claims():
                return None
            assessments = context.get_assessments()
            if assessments:
                supported = sum(
                    str(item.get("label")).upper() in {"SUPPORTED", "ENTAILS"}
                    for item in assessments
                )
                rate = supported / len(assessments)
            else:
                rate = 0.0
            return (
                1.0 - rate
                if "unsupported" in metric_id
                or "contradiction" in metric_id
                or metric_id.startswith("hallucination.")
                else rate
            )

        if metric_id.startswith(
            ("context.", "citation.semantic_", "claim.", "citation.entailment_")
        ):
            if metric_id.startswith("context.") and not context.has_retrieval():
                return None
            if metric_id.startswith("claim.") and not context.has_claims():
                return None
            if context.has_assessments():
                scores = [
                    item["score"]
                    for item in context.get_assessments()
                    if item.get("score") is not None
                ]
                if scores:
                    return sum(scores) / len(scores)
            if context.has_retrieval():
                stage = context.list_stages()[-1]
                return _overlap(_items_text(stage), reference)
            return None

        if metric_id.startswith("citation.") and metric_id in {
            "citation.overcitation_rate",
            "citation.misattribution_rate",
            "citation.support_completeness",
        }:
            if not context.has_citations():
                return None
            citations = context.observation.answer.citations
            return min(1.0, len(citations) / max(len(context.case.gold_evidence), 1))

        if metric_id.startswith("calibration.") or metric_id.startswith("abstention."):
            if not context.has_confidence():
                return None
            probabilities = [signal.value for signal in context.observation.confidence]
            confidence = sum(probabilities) / len(probabilities)
            correct = self._value_for("answer.semantic_correctness", context)
            if correct is None:
                return None
            if metric_id.endswith("brier_score"):
                return (confidence - correct) ** 2
            if metric_id.endswith(("ece", "mce")):
                return abs(confidence - correct)
            if metric_id.endswith("log_loss"):
                return -math.log(max(confidence if correct else 1 - confidence, 1e-12))
            return correct

        if metric_id.startswith(
            ("stage.", "reranker.", "fusion.", "filter.", "compression.")
        ):
            pair = _stage_pair(context)
            if pair is None:
                return None
            before, after = pair
            before_ids = {str(item.get("retrieval_id")) for item in before.items}
            after_ids = {str(item.get("retrieval_id")) for item in after.items}
            if metric_id.endswith(("retention", "retention_rate")):
                return len(before_ids & after_ids) / max(len(before_ids), 1)
            if metric_id.endswith("churn"):
                return 1.0 - len(before_ids & after_ids) / max(
                    len(before_ids | after_ids), 1
                )
            if metric_id.endswith(("ratio", "token_reduction")):
                return len(_items_text(after)) / max(len(_items_text(before)), 1)
            if metric_id.endswith("latency_ms"):
                return 0.0
            return _overlap(_items_text(before), _items_text(after))

        if metric_id.startswith("embedding."):
            vectors = (
                context.observation.embedding_vectors if context.observation else None
            )
            if vectors is None or not vectors.vectors:
                return None
            norms = [
                math.sqrt(sum(value * value for value in vector))
                for vector in vectors.vectors
            ]
            return sum(norms) / len(norms)

        if metric_id.startswith("resource."):
            if not context.has_usage():
                return None
            resource = context.observation.usage.resources
            key = metric_id.removeprefix("resource.")
            value = resource.get(key)
            return float(value) if isinstance(value, (int, float)) else None

        if metric_id.startswith(("chunking.", "parsing.", "ingestion.")):
            value = context.case.metadata.get(metric_id.split(".", 1)[1])
            return float(value) if isinstance(value, (int, float)) else None

        if metric_id.startswith("multihop."):
            groups = context.case.gold_evidence_groups
            if not groups:
                return None
            return sum(bool(group.evidence_ids) for group in groups) / len(groups)

        if metric_id.startswith("conversation."):
            return 1.0 if context.case.conversation_id is not None else None

        if metric_id.startswith("robustness."):
            return None

        if metric_id.startswith("comparison."):
            return None
        return None

    def _value_for(self, metric_id: str, context: MetricContext) -> float | None:
        return AdvancedMetric(
            metric_id,
            self.requirements,
            self.scope,
            self.description,
            self.judge_required,
            self.direction,
        )._value(context)


SEMANTIC_METRICS: dict[str, frozenset[MetricRequirement]] = {}


def _add(ids: list[str], requirements: frozenset[MetricRequirement]) -> None:
    SEMANTIC_METRICS.update({metric_id: requirements for metric_id in ids})


_add(
    [
        "answer.semantic_correctness",
        "answer.semantic_similarity",
        "answer.factual_precision",
        "answer.factual_recall",
        "answer.factual_f1",
        "answer.completeness",
        "answer.contradiction_rate",
        "answer.conciseness",
        "answer.instruction_adherence",
        "answer.structured_output_validity",
        "answer.relevance",
        "answer.query_coverage",
        "answer.off_topic_rate",
        "answer.responsiveness",
    ],
    frozenset(
        {
            MetricRequirement.ANSWER,
            MetricRequirement.REFERENCE_ANSWER,
            MetricRequirement.JUDGE,
        }
    ),
)
_add(
    [
        "answer.relevance",
        "answer.query_coverage",
        "answer.off_topic_rate",
        "answer.responsiveness",
    ],
    frozenset(
        {MetricRequirement.QUERY, MetricRequirement.ANSWER, MetricRequirement.JUDGE}
    ),
)
_add(
    [
        "faithfulness.claim_support_rate",
        "faithfulness.unsupported_claim_rate",
        "faithfulness.contradiction_rate",
        "faithfulness.answer_score",
        "faithfulness.evidence_sufficiency",
        "hallucination.claim_rate",
        "hallucination.answer_rate",
    ],
    frozenset(
        {
            MetricRequirement.ANSWER,
            MetricRequirement.CLAIMS,
            MetricRequirement.FINAL_CONTEXT,
        }
    ),
)
_add(
    [
        "context.relevance",
        "context.semantic_precision",
        "context.semantic_recall",
        "context.information_density",
        "context.semantic_redundancy",
        "context.answer_support_coverage",
        "context.required_fact_coverage",
    ],
    frozenset(
        {
            MetricRequirement.RETRIEVAL,
            MetricRequirement.STAGE_BY_ID,
            MetricRequirement.JUDGE,
        }
    ),
)
_add(
    [
        "claim.support_precision",
        "claim.support_recall",
        "claim.entailment",
        "claim.contradiction",
        "claim.evidence_sufficiency",
        "citation.entailment_precision",
        "citation.entailment_recall",
        "citation.semantic_relevance",
        "citation.overcitation_rate",
        "citation.misattribution_rate",
        "citation.support_completeness",
    ],
    frozenset(
        {MetricRequirement.CLAIMS, MetricRequirement.CITATIONS, MetricRequirement.JUDGE}
    ),
)
_add(
    [
        "embedding.recall_at_k",
        "embedding.ndcg_at_k",
        "embedding.mrr",
        "embedding.map_at_k",
        "embedding.triplet_accuracy",
        "embedding.hard_negative_accuracy",
        "embedding.positive_negative_margin",
        "embedding.score_roc_auc",
        "embedding.score_pr_auc",
        "embedding.mean_positive_similarity",
        "embedding.mean_negative_similarity",
        "embedding.norm_distribution",
        "embedding.anisotropy",
        "embedding.collapse_score",
        "embedding.intra_document_similarity",
        "embedding.inter_document_similarity",
        "embedding.cluster_separation",
        "embedding.cluster_compactness",
    ],
    frozenset({MetricRequirement.RETRIEVAL, MetricRequirement.EMBEDDING_METADATA}),
)
_add(
    [
        "reranker.ndcg_at_k",
        "reranker.map_at_k",
        "reranker.mrr_at_k",
        "reranker.precision_at_k",
        "reranker.recall_at_k",
        "reranker.ndcg_gain",
        "reranker.map_gain",
        "reranker.rank_uplift",
        "reranker.rank_regression",
        "reranker.pairwise_accuracy",
        "reranker.pairwise_inversions",
        "reranker.relevant_item_drop_rate",
        "reranker.top_k_churn",
        "reranker.beneficial_churn",
        "reranker.harmful_churn",
        "reranker.latency_ms",
        "reranker.quality_gain_per_ms",
        "fusion.union_recall",
        "fusion.recall_gain",
        "fusion.ndcg_gain",
        "fusion.map_gain",
        "fusion.source_overlap",
        "fusion.retriever_complementarity",
        "fusion.unique_contribution",
        "fusion.source_contribution",
        "fusion.dominance",
        "fusion.relevant_item_loss",
        "fusion.rank_correlation",
        "fusion.latency_ms",
        "filter.gold_retention",
        "filter.noise_rejection",
        "filter.false_removal",
        "filter.precision_gain",
        "filter.recall_loss",
        "filter.item_retention",
        "filter.source_retention",
        "filter.latency_ms",
        "filter.quality_gain_per_ms",
        "compression.ratio",
        "compression.token_reduction",
        "compression.gold_retention",
        "compression.semantic_preservation",
        "compression.information_loss",
        "compression.hallucination_rate",
        "compression.context_precision_gain",
        "compression.context_recall_loss",
        "compression.latency_ms",
        "compression.quality_per_token",
    ],
    frozenset({MetricRequirement.RETRIEVAL, MetricRequirement.STAGE_PAIRS}),
)
_add(
    [
        "chunking.mean_chunk_size",
        "chunking.chunk_size_distribution",
        "chunking.overlap_ratio",
        "chunking.duplicate_rate",
        "chunking.semantic_coherence",
        "chunking.boundary_quality",
        "chunking.evidence_fragmentation",
        "chunking.evidence_containment",
        "chunking.oracle_evidence_recall",
        "chunking.metadata_preservation",
        "parsing.extraction_coverage",
        "parsing.extraction_loss",
        "ingestion.latency_ms",
        "ingestion.embedding_throughput",
        "ingestion.chunk_count",
        "ingestion.failure_rate",
    ],
    frozenset({MetricRequirement.CHUNK_INVENTORY, MetricRequirement.INGESTION}),
)
_add(
    [
        "abstention.coverage",
        "abstention.selective_accuracy",
        "abstention.risk_coverage_auc",
    ],
    frozenset({MetricRequirement.ANSWERABILITY, MetricRequirement.CONFIDENCE}),
)
_add(
    [
        "calibration.brier_score",
        "calibration.ece",
        "calibration.mce",
        "calibration.log_loss",
        "calibration.auroc",
        "calibration.auprc",
        "calibration.risk_coverage_auc",
        "calibration.selective_accuracy",
    ],
    frozenset({MetricRequirement.CONFIDENCE, MetricRequirement.REFERENCE_ANSWER}),
)
_add(
    [
        "multihop.evidence_recall",
        "multihop.complete_chain_recall",
        "multihop.partial_chain_recall",
        "multihop.missing_hop_rate",
        "multihop.extraneous_hop_rate",
        "multihop.reasoning_correctness",
        "multihop.evidence_combination_accuracy",
        "multihop.source_coverage",
    ],
    frozenset({MetricRequirement.GOLD_EVIDENCE_GROUPS, MetricRequirement.RETRIEVAL}),
)
_add(
    [
        "conversation.followup_resolution",
        "conversation.history_utilization",
        "conversation.history_contamination",
        "conversation.entity_consistency",
        "conversation.fact_consistency",
        "conversation.cross_turn_faithfulness",
        "conversation.retrieval_relevance",
        "conversation.answer_relevance",
        "conversation.completeness",
        "conversation.state_leakage",
    ],
    frozenset({MetricRequirement.CONVERSATION, MetricRequirement.HISTORY}),
)
_add(
    [
        "robustness.answer_stability",
        "robustness.retrieval_stability",
        "robustness.citation_stability",
        "robustness.decision_stability",
        "robustness.correctness_degradation",
        "robustness.recall_degradation",
        "robustness.faithfulness_degradation",
        "robustness.attack_success_rate",
        "robustness.recovery_rate",
    ],
    frozenset({MetricRequirement.PERTURBATION_PAIR}),
)
_add(
    [
        "resource.cpu_time_ms",
        "resource.cpu_utilization",
        "resource.peak_ram_bytes",
        "resource.average_ram_bytes",
        "resource.gpu_utilization",
        "resource.peak_vram_bytes",
        "resource.memory_per_query",
        "resource.cpu_time_per_query",
        "resource.throughput_per_cpu_second",
        "resource.throughput_per_gpu_second",
    ],
    frozenset({MetricRequirement.USAGE}),
)


def advanced_metrics() -> list[AdvancedMetric]:
    """Build all advanced metric implementations for catalog registration."""
    metrics: list[AdvancedMetric] = []
    for metric_id, requirements in SEMANTIC_METRICS.items():
        judge_required = MetricRequirement.JUDGE in requirements
        direction = (
            "lower_is_better"
            if any(
                word in metric_id
                for word in ("loss", "error", "rate", "latency", "reduction", "churn")
            )
            else "higher_is_better"
        )
        metrics.append(
            AdvancedMetric(
                metric_id,
                requirements,
                scope=(
                    MetricScope.RETRIEVAL_STAGE_PAIR
                    if metric_id.split(".", 1)[0]
                    in {"reranker", "fusion", "filter", "compression"}
                    else MetricScope.CASE
                ),
                description=f"Advanced metric {metric_id}.",
                judge_required=judge_required,
                direction=direction,
            )
        )
    return metrics


__all__ = ["AdvancedMetric", "SEMANTIC_METRICS", "advanced_metrics"]
