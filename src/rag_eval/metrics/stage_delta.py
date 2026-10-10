"""Deterministic before/after retrieval-stage comparison metrics."""

from typing import Any

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext, RetrievalStageView
from rag_eval.metrics.helpers import match_gold_evidence, safe_divide
from rag_eval.metrics.retrieval import (
    MRR,
    MAPAtK,
    NDCGAtK,
    PrecisionAtK,
    RecallAtK,
    _is_item_relevant,
)


class _StageDeltaMetric:
    """Base class for a metric comparing two explicitly named stages."""

    metric_id: str
    description: str

    def __init__(
        self,
        before_stage_id: str = "before",
        after_stage_id: str = "after",
        *,
        k: int = 5,
    ) -> None:
        self.before_stage_id = before_stage_id
        self.after_stage_id = after_stage_id
        self.k = k
        self._definition = MetricDefinition(
            metric_id=self.metric_id,
            version="1",
            scope=MetricScope.RETRIEVAL_STAGE_PAIR,
            requirements=frozenset(
                {
                    MetricRequirement.GOLD_EVIDENCE,
                    MetricRequirement.RETRIEVAL,
                    MetricRequirement.STAGE_PAIRS,
                }
            ),
            description=self.description,
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    def _pair(
        self, context: MetricContext
    ) -> tuple[RetrievalStageView, RetrievalStageView] | None:
        before, after = context.get_before_after_stage(
            self.before_stage_id, self.after_stage_id
        )
        if before is None or after is None:
            return None
        return before, after

    def _missing(self, context: MetricContext, reason: str) -> MetricResult:
        return MetricResult(
            metric_id=self.metric_id,
            metric_version="1",
            status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
            value=None,
            reason=reason,
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "before_stage_id": self.before_stage_id,
                "after_stage_id": self.after_stage_id,
            },
        )

    def _computed(
        self,
        context: MetricContext,
        value: float | int | None,
        details: dict[str, Any] | None = None,
    ) -> MetricResult:
        return MetricResult(
            metric_id=self.metric_id,
            metric_version="1",
            status=MetricStatus.COMPUTED,
            value=value,
            reason=("No relevant item exists" if value is None else None),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details=details or {},
        )

    def _gold(self, context: MetricContext) -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in context.case.gold_evidence]


class _QualityDelta(_StageDeltaMetric):
    """Run one existing retrieval quality metric against both stages."""

    metric_type: type

    async def compute(self, context: MetricContext) -> MetricResult:
        pair = self._pair(context)
        if pair is None:
            return self._missing(context, "Before or after retrieval stage is missing")
        if not context.has_gold_evidence():
            return self._missing(context, "Gold evidence is missing")
        before_metric = self.metric_type(k=self.k, stage_id=self.before_stage_id)
        after_metric = self.metric_type(k=self.k, stage_id=self.after_stage_id)
        before = await before_metric.compute(context)
        after = await after_metric.compute(context)
        if (
            before.status != MetricStatus.COMPUTED
            or after.status != MetricStatus.COMPUTED
        ):
            return self._missing(context, "A stage quality value is unavailable")
        if before.value is None or after.value is None:
            return self._computed(context, None)
        return self._computed(
            context,
            round(float(after.value) - float(before.value), 6),
            {"before": before.value, "after": after.value, "k": self.k},
        )


class RecallDelta(_QualityDelta):
    """Change in recall between two retrieval stages."""

    metric_id = "stage.recall_delta"
    description = "After-stage recall minus before-stage recall."
    metric_type = RecallAtK


class PrecisionDelta(_QualityDelta):
    """Change in precision between two retrieval stages."""

    metric_id = "stage.precision_delta"
    description = "After-stage precision minus before-stage precision."
    metric_type = PrecisionAtK


class NDCGDelta(_QualityDelta):
    """Change in nDCG between two retrieval stages."""

    metric_id = "stage.ndcg_delta"
    description = "After-stage nDCG minus before-stage nDCG."
    metric_type = NDCGAtK


class MRRDelta(_StageDeltaMetric):
    """Change in reciprocal rank between two retrieval stages."""

    metric_id = "stage.mrr_delta"
    description = "After-stage MRR minus before-stage MRR."

    async def compute(self, context: MetricContext) -> MetricResult:
        return await self._run_scalar_pair(context, MRR)

    async def _run_scalar_pair(
        self, context: MetricContext, metric_type: type
    ) -> MetricResult:
        pair = self._pair(context)
        if pair is None or not context.has_gold_evidence():
            return self._missing(context, "Stages or gold evidence are missing")
        before = await metric_type(stage_id=self.before_stage_id).compute(context)
        after = await metric_type(stage_id=self.after_stage_id).compute(context)
        if (
            before.status != MetricStatus.COMPUTED
            or after.status != MetricStatus.COMPUTED
        ):
            return self._missing(context, "A stage quality value is unavailable")
        if before.value is None or after.value is None:
            return self._computed(context, None)
        return self._computed(context, float(after.value) - float(before.value))


class MAPDelta(MRRDelta):
    """Change in mean average precision between two stages."""

    metric_id = "stage.map_delta"
    description = "After-stage MAP minus before-stage MAP."

    async def compute(self, context: MetricContext) -> MetricResult:
        return await self._run_scalar_pair(context, MAPAtK)


class _SetDelta(_StageDeltaMetric):
    """Base for set-based stage deltas."""

    def _items(self, context: MetricContext) -> tuple[list[dict], list[dict]] | None:
        pair = self._pair(context)
        if pair is None:
            return None
        return pair[0].items, pair[1].items


class GoldRetention(_StageDeltaMetric):
    """Fraction of before-stage gold evidence retained after reranking/filtering."""

    metric_id = "stage.gold_retention"
    description = "Gold evidence retained from before to after stage."

    async def compute(self, context: MetricContext) -> MetricResult:
        pair = self._pair(context)
        if pair is None or not context.has_gold_evidence():
            return self._missing(context, "Stages or gold evidence are missing")
        gold = self._gold(context)
        before = match_gold_evidence(gold, pair[0].items)
        after = match_gold_evidence(gold, pair[1].items)
        value = safe_divide(
            sum(
                a.matched and b.matched
                for a, b in zip(before, after, strict=True)
            ),
            len(gold),
        )
        return self._computed(context, round(value, 6))


class NoiseRejection(_StageDeltaMetric):
    """Fraction of irrelevant before-stage items removed by the after stage."""

    metric_id = "stage.noise_rejection"
    description = "Irrelevant retrieval items rejected by the after stage."

    async def compute(self, context: MetricContext) -> MetricResult:
        items = self._items(context)
        if items is None or not context.has_gold_evidence():
            return self._missing(context, "Stages or gold evidence are missing")
        before, after = items
        gold = self._gold(context)
        before_noise = {
            item.get("retrieval_id")
            for item in before
            if not _is_item_relevant(item, gold)
        }
        after_ids = {item.get("retrieval_id") for item in after}
        rejected = len(before_noise - after_ids)
        return self._computed(
            context, round(safe_divide(rejected, len(before_noise)), 6)
        )


class ItemRetentionRate(_SetDelta):
    """Fraction of before-stage retrieval item identities retained."""

    metric_id = "stage.item_retention_rate"
    description = "After-stage item retention rate."

    async def compute(self, context: MetricContext) -> MetricResult:
        items = self._items(context)
        if items is None:
            return self._missing(context, "Before or after retrieval stage is missing")
        before, after = items
        before_ids = {item.get("retrieval_id") for item in before}
        after_ids = {item.get("retrieval_id") for item in after}
        return self._computed(
            context, round(safe_divide(len(before_ids & after_ids), len(before_ids)), 6)
        )


class SourceRetentionRate(_SetDelta):
    """Fraction of before-stage source identities retained."""

    metric_id = "stage.source_retention_rate"
    description = "After-stage source retention rate."

    async def compute(self, context: MetricContext) -> MetricResult:
        items = self._items(context)
        if items is None:
            return self._missing(context, "Before or after retrieval stage is missing")
        before, after = items
        def source(item: dict) -> Any:
            """Return the stable document identity for one item."""
            return item.get("source", {}).get("document_id")
        before_ids = {source(item) for item in before}
        after_ids = {source(item) for item in after}
        return self._computed(
            context, round(safe_divide(len(before_ids & after_ids), len(before_ids)), 6)
        )


class TopKChurn(_SetDelta):
    """Compute one minus top-K item-set overlap."""

    metric_id = "stage.top_k_churn"
    description = "Top-K retrieval item churn between two stages."

    async def compute(self, context: MetricContext) -> MetricResult:
        items = self._items(context)
        if items is None:
            return self._missing(context, "Before or after retrieval stage is missing")
        before, after = items
        before_ids = {item.get("retrieval_id") for item in before[: self.k]}
        after_ids = {item.get("retrieval_id") for item in after[: self.k]}
        union = before_ids | after_ids
        return self._computed(
            context, round(1 - safe_divide(len(before_ids & after_ids), len(union)), 6)
        )


class RankGain(_StageDeltaMetric):
    """Return before first-relevant rank minus after rank."""

    metric_id = "stage.rank_gain"
    description = "Improvement in first relevant rank between stages."

    async def compute(self, context: MetricContext) -> MetricResult:
        return await self._rank_delta(context, reverse=False)

    async def _rank_delta(self, context: MetricContext, reverse: bool) -> MetricResult:
        pair = self._pair(context)
        if pair is None or not context.has_gold_evidence():
            return self._missing(context, "Stages or gold evidence are missing")
        gold = self._gold(context)
        ranks = []
        for stage in pair:
            rank = next(
                (
                    index
                    for index, item in enumerate(stage.items, 1)
                    if _is_item_relevant(item, gold)
                ),
                None,
            )
            ranks.append(rank)
        if any(rank is None for rank in ranks):
            return self._computed(context, None)
        value = ranks[0] - ranks[1]
        return self._computed(
            context,
            -value if reverse else value,
            {"before_rank": ranks[0], "after_rank": ranks[1]},
        )


class RankRegression(RankGain):
    """Return after first-relevant rank minus before rank."""

    metric_id = "stage.rank_regression"
    description = "Regression in first relevant rank between stages."

    async def compute(self, context: MetricContext) -> MetricResult:
        return await self._rank_delta(context, reverse=True)


class StageLatency(_StageDeltaMetric):
    """Return after-stage latency minus before-stage latency."""

    metric_id = "stage.latency_ms"
    description = "Latency delta between linked retrieval-stage spans."

    async def compute(self, context: MetricContext) -> MetricResult:
        pair = self._pair(context)
        if pair is None or not context.has_trace():
            return self._missing(context, "Stages or trace is missing")
        values: list[float] = []
        for stage in pair:
            if stage.trace_span_id is None:
                return self._missing(context, "A stage has no linked trace span")
            span = next(
                (
                    span
                    for span in context.observation.trace.spans
                    if span.span_id == stage.trace_span_id
                ),
                None,
            )
            if span is None or span.duration_ms is None:
                return self._missing(context, "A linked trace span is missing duration")
            values.append(span.duration_ms)
        return self._computed(context, round(values[1] - values[0], 6))


class QualityGainPerMs(RecallDelta):
    """Normalize recall gain by positive stage latency cost."""

    metric_id = "stage.quality_gain_per_ms"
    description = "Recall gain per millisecond of added stage latency."

    async def compute(self, context: MetricContext) -> MetricResult:
        quality = await super().compute(context)
        latency = await StageLatency(
            self.before_stage_id, self.after_stage_id, k=self.k
        ).compute(context)
        quality.metric_id = self.metric_id
        if (
            quality.status != MetricStatus.COMPUTED
            or latency.status != MetricStatus.COMPUTED
        ):
            quality.status = MetricStatus.UNAVAILABLE_MISSING_INPUT
            quality.value = None
            quality.reason = "Quality or stage latency is unavailable"
            return quality
        if quality.value is None or latency.value is None or float(latency.value) <= 0:
            quality.value = None
            quality.reason = "No positive stage latency cost is available"
            quality.status = MetricStatus.UNAVAILABLE_MISSING_INPUT
            return quality
        quality.value = round(float(quality.value) / float(latency.value), 6)
        return quality


__all__ = [
    "RecallDelta",
    "PrecisionDelta",
    "NDCGDelta",
    "MRRDelta",
    "MAPDelta",
    "RankGain",
    "RankRegression",
    "GoldRetention",
    "NoiseRejection",
    "ItemRetentionRate",
    "SourceRetentionRate",
    "TopKChurn",
    "StageLatency",
    "QualityGainPerMs",
]
