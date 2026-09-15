"""Retrieval quality metrics for Stage 12.

Deterministic metrics evaluating retrieval effectiveness against gold evidence.
No LLM judges or embeddings.

Metrics:
- hit_at_k: Whether any gold evidence appears in top-k
- precision_at_k: Fraction of retrieved items that are relevant
- recall_at_k: Fraction of gold evidence retrieved in top-k
- mrr: Mean Reciprocal Rank (first relevant item)
- map_at_k: Mean Average Precision at k
- ndcg_at_k: Normalized Discounted Cumulative Gain at k
- r_precision: Precision at R (where R = number of gold items)
"""

from dataclasses import dataclass, field
from typing import Any

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext
from rag_eval.metrics.helpers import (
    match_gold_evidence,
    safe_divide,
)


def _is_item_relevant(
    item: dict[str, Any], gold_evidence: list[dict[str, Any]]
) -> bool:
    """Check if one retrieved item matches any gold evidence.

    Uses document-level matching (not span-level for simplicity).

    Args:
        item: Retrieved item with source metadata.
        gold_evidence: Gold evidence list.

    Returns:
        True if item's document_id matches any gold document_id.
    """
    # Handle both dict and SourceLocation
    if hasattr(item, "source"):
        source = item.source
        if source is None:
            return False
        item_doc_id = (
            source.document_id
            if hasattr(source, "document_id")
            else source.get("document_id")
        )  # type: ignore[union-attr]
    else:
        source = item.get("source", {})
        item_doc_id = source.get("document_id") if isinstance(source, dict) else None

    if not item_doc_id:
        return False

    for gold in gold_evidence:
        gold_doc_id = (
            gold.document_id
            if hasattr(gold, "document_id")
            else gold.get("document_id")
        )  # type: ignore[union-attr]
        if gold_doc_id == item_doc_id:
            return True

    return False


def _get_relevance_scores(
    retrieved_items: list[dict[str, Any]], gold_evidence: list[dict[str, Any]]
) -> list[int]:
    """Get binary relevance scores for retrieved items.

    Args:
        retrieved_items: List of retrieved items.
        gold_evidence: Gold evidence list.

    Returns:
        List of 0/1 relevance scores.
    """
    scores = []
    for item in retrieved_items:
        if _is_item_relevant(item, gold_evidence):
            scores.append(1)
        else:
            scores.append(0)
    return scores


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert object to dictionary, handling Pydantic models."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    elif hasattr(obj, "__dict__"):
        return obj.__dict__
    else:
        return dict(obj)


@dataclass
class HitAtKResult(MetricResult):
    """Result of Hit@K computation."""

    metric_id: str = field(init=False, default="retrieval.hit_at_k")
    metric_version: str = field(init=False, default="1")


class HitAtK:
    """Hit@K: Whether any gold evidence appears in top-k retrieved items.

    Formula:
        Hit@K = 1 if any(top-k items match gold) else 0

    Requirements:
        - GOLD_EVIDENCE: Benchmark must have gold evidence
        - RETRIEVAL: Target must produce retrieval results

    Edge cases:
        - k >= len(retrieved) → use all retrieved items
        - No gold evidence → UNAVAILABLE_MISSING_INPUT
        - Zero retrieved items → 0.0 (no hit possible)
        - k = 0 → 0.0 (cannot hit with zero items)
    """

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self._definition = MetricDefinition(
            metric_id="retrieval.hit_at_k",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.GOLD_EVIDENCE, MetricRequirement.RETRIEVAL}
            ),
            description=f"Whether any gold evidence appears in top-{k} retrieved items.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check gold evidence
        if not context.has_gold_evidence():
            return HitAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Benchmark has no gold evidence",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return HitAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        items = stage.items
        # Convert gold evidence to dicts
        gold = []
        for e in context.case.gold_evidence:
            if hasattr(e, "model_dump"):
                gold.append(e.model_dump(mode="json"))
            else:
                gold.append(dict(e))

        # Handle k = 0 or empty retrieval
        if self._k <= 0 or not items:
            return HitAtKResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k, "retrieved_count": len(items), "hit": False},
            )

        # Check top-k
        top_k = items[: self._k]
        hit = any(_is_item_relevant(item, gold) for item in top_k)

        return HitAtKResult(
            status=MetricStatus.COMPUTED,
            value=1.0 if hit else 0.0,
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "k": self._k,
                "retrieved_count": len(items),
                "gold_count": len(gold),
                "hit": hit,
            },
        )


@dataclass
class PrecisionAtKResult(MetricResult):
    """Result of Precision@K computation."""

    metric_id: str = field(init=False, default="retrieval.precision_at_k")
    metric_version: str = field(init=False, default="1")


class PrecisionAtK:
    """Precision@K: Fraction of top-k retrieved items that are relevant.

    Formula:
        Precision@K = relevant_in_top_k / k

    Requirements:
        - GOLD_EVIDENCE: Benchmark must have gold evidence
        - RETRIEVAL: Target must produce retrieval results

    Edge cases:
        - k > len(retrieved) → use len(retrieved) as denominator
        - Zero retrieved → 0.0
        - No gold evidence → UNAVAILABLE_MISSING_INPUT
    """

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self._definition = MetricDefinition(
            metric_id="retrieval.precision_at_k",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.GOLD_EVIDENCE, MetricRequirement.RETRIEVAL}
            ),
            description=f"Fraction of top-{k} retrieved items that are relevant.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check gold evidence
        if not context.has_gold_evidence():
            return PrecisionAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Benchmark has no gold evidence",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return PrecisionAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        items = stage.items
        gold = [e.model_dump(mode="json") for e in context.case.gold_evidence]

        # Handle k = 0 or empty retrieval
        if self._k <= 0 or not items:
            return PrecisionAtKResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "k": self._k,
                    "retrieved_count": len(items),
                    "relevant_count": 0,
                },
            )

        # Count relevant in top-k
        top_k = items[: self._k]
        relevant_count = sum(1 for item in top_k if _is_item_relevant(item, gold))

        # Use actual k (not len(top_k)) as denominator per standard convention
        precision = safe_divide(relevant_count, self._k, default=0.0)

        return PrecisionAtKResult(
            status=MetricStatus.COMPUTED,
            value=round(precision, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "k": self._k,
                "retrieved_count": len(items),
                "relevant_count": relevant_count,
            },
        )


@dataclass
class RecallAtKResult(MetricResult):
    """Result of Recall@K computation."""

    metric_id: str = field(init=False, default="retrieval.recall_at_k")
    metric_version: str = field(init=False, default="1")


class RecallAtK:
    """Recall@K: Fraction of gold evidence retrieved in top-k.

    Formula:
        Recall@K = |gold evidence matched in top-k| / |gold evidence|

    Uses hierarchical matching:
    1. Same document + overlapping span (best)
    2. Same document + same page
    3. Same document only

    Requirements:
        - GOLD_EVIDENCE: Benchmark must have gold evidence
        - RETRIEVAL: Target must produce retrieval results

    Edge cases:
        - No gold evidence → UNAVAILABLE_MISSING_INPUT
        - Zero retrieved → 0.0
        - More gold than k → recall may be < 1.0 even with perfect retrieval
    """

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self._definition = MetricDefinition(
            metric_id="retrieval.recall_at_k",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.GOLD_EVIDENCE, MetricRequirement.RETRIEVAL}
            ),
            description=f"Fraction of gold evidence matched in top-{k} retrieved items.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check gold evidence
        if not context.has_gold_evidence():
            return RecallAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Benchmark has no gold evidence",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return RecallAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        items = stage.items
        gold = [e.model_dump(mode="json") for e in context.case.gold_evidence]

        # Handle k = 0 or empty retrieval
        if self._k <= 0 or not items:
            return RecallAtKResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "k": self._k,
                    "retrieved_count": len(items),
                    "gold_count": len(gold),
                    "matched": 0,
                },
            )

        # Match gold against top-k
        top_k = items[: self._k]
        matches = match_gold_evidence(gold, top_k)
        matched_count = sum(1 for m in matches if m.matched)

        recall = safe_divide(matched_count, len(gold), default=0.0)

        return RecallAtKResult(
            status=MetricStatus.COMPUTED,
            value=round(recall, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "k": self._k,
                "retrieved_count": len(items),
                "gold_count": len(gold),
                "matched_count": matched_count,
            },
        )


@dataclass
class MRRResult(MetricResult):
    """Result of MRR computation."""

    metric_id: str = field(init=False, default="retrieval.mrr")
    metric_version: str = field(init=False, default="1")


class MRR:
    """Mean Reciprocal Rank: 1 / rank of first relevant item.

    Formula:
        MRR = 1 / rank_first_relevant (0 if none relevant)

    Requirements:
        - GOLD_EVIDENCE: Benchmark must have gold evidence
        - RETRIEVAL: Target must produce retrieval results

    Edge cases:
        - No relevant items → 0.0
        - First item relevant → 1.0
        - Zero retrieved → 0.0
        - No gold evidence → UNAVAILABLE_MISSING_INPUT
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="retrieval.mrr",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.GOLD_EVIDENCE, MetricRequirement.RETRIEVAL}
            ),
            description="Reciprocal rank of first relevant retrieved item.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check gold evidence
        if not context.has_gold_evidence():
            return MRRResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Benchmark has no gold evidence",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return MRRResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        items = stage.items
        gold = [e.model_dump(mode="json") for e in context.case.gold_evidence]

        # Handle empty retrieval
        if not items:
            return MRRResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"first_relevant_rank": None, "retrieved_count": len(items)},
            )

        # Find first relevant
        first_relevant_rank = None
        for idx, item in enumerate(items):
            if _is_item_relevant(item, gold):
                first_relevant_rank = idx + 1  # 1-indexed
                break

        if first_relevant_rank is None:
            mrr = 0.0
        else:
            mrr = 1.0 / first_relevant_rank

        return MRRResult(
            status=MetricStatus.COMPUTED,
            value=round(mrr, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "first_relevant_rank": first_relevant_rank,
                "retrieved_count": len(items),
            },
        )


@dataclass
class MAPAtKResult(MetricResult):
    """Result of MAP@K computation."""

    metric_id: str = field(init=False, default="retrieval.map_at_k")
    metric_version: str = field(init=False, default="1")


class MAPAtK:
    """Mean Average Precision at K.

    Formula:
        AP@K = (1 / min(R, K)) * sum_{i=1}^{K} P@i * rel(i)

    Where:
        - R = total relevant items (gold count)
        - rel(i) = 1 if item at position i is relevant, 0 otherwise
        - P@i = precision at i

    Requirements:
        - GOLD_EVIDENCE: Benchmark must have gold evidence
        - RETRIEVAL: Target must produce retrieval results

    Edge cases:
        - No gold evidence → UNAVAILABLE_MISSING_INPUT
        - Zero retrieved → 0.0
        - No relevant items → 0.0
    """

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self._definition = MetricDefinition(
            metric_id="retrieval.map_at_k",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.GOLD_EVIDENCE, MetricRequirement.RETRIEVAL}
            ),
            description=f"Mean Average Precision at {k}.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check gold evidence
        if not context.has_gold_evidence():
            return MAPAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Benchmark has no gold evidence",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return MAPAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        items = stage.items
        gold = [e.model_dump(mode="json") for e in context.case.gold_evidence]

        # Handle k = 0 or empty retrieval
        if self._k <= 0 or not items:
            return MAPAtKResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "k": self._k,
                    "retrieved_count": len(items),
                    "gold_count": len(gold),
                    "sum_precision": 0.0,
                },
            )

        # Compute AP@K
        top_k = items[: self._k]
        relevant_count = 0
        sum_precision = 0.0

        for i, item in enumerate(top_k):
            if _is_item_relevant(item, gold):
                relevant_count += 1
                precision_at_i = relevant_count / (i + 1)
                sum_precision += precision_at_i

        # Normalize by min(R, K)
        r = len(gold)
        k_actual = min(r, self._k)

        if k_actual == 0:
            ap = 0.0
        else:
            ap = sum_precision / k_actual

        return MAPAtKResult(
            status=MetricStatus.COMPUTED,
            value=round(ap, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "k": self._k,
                "retrieved_count": len(items),
                "gold_count": len(gold),
                "relevant_found": relevant_count,
                "sum_precision": round(sum_precision, 6),
            },
        )


@dataclass
class NDCGAtKResult(MetricResult):
    """Result of nDCG@K computation."""

    metric_id: str = field(init=False, default="retrieval.ndcg_at_k")
    metric_version: str = field(init=False, default="1")


class NDCGAtK:
    """Normalized Discounted Cumulative Gain at K.

    Formula:
        DCG@K = sum_{i=1}^{K} rel(i) / log2(i + 1)
        IDCG@K = DCG@K for ideal ranking (all relevant first)
        nDCG@K = DCG@K / IDCG@K

    Uses binary relevance (0 or 1).

    Requirements:
        - GOLD_EVIDENCE: Benchmark must have gold evidence
        - RETRIEVAL: Target must produce retrieval results

    Edge cases:
        - No gold evidence → UNAVAILABLE_MISSING_INPUT
        - Zero retrieved → 0.0
        - IDCG = 0 → 0.0 (no relevant items)
    """

    def __init__(self, k: int = 5) -> None:
        self._k = k
        self._definition = MetricDefinition(
            metric_id="retrieval.ndcg_at_k",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.GOLD_EVIDENCE, MetricRequirement.RETRIEVAL}
            ),
            description=f"Normalized Discounted Cumulative Gain at {k}.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        import math

        # Check gold evidence
        if not context.has_gold_evidence():
            return NDCGAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Benchmark has no gold evidence",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return NDCGAtKResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"k": self._k},
            )

        items = stage.items
        gold = [e.model_dump(mode="json") for e in context.case.gold_evidence]

        # Handle k = 0 or empty retrieval
        if self._k <= 0 or not items:
            return NDCGAtKResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "k": self._k,
                    "retrieved_count": len(items),
                    "gold_count": len(gold),
                    "dcg": 0.0,
                    "idcg": 0.0,
                },
            )

        # Get relevance scores
        relevance_scores = _get_relevance_scores(items, gold)
        top_k_scores = relevance_scores[: self._k]

        # Compute DCG@K
        dcg = sum(
            rel / math.log2(i + 2) for i, rel in enumerate(top_k_scores)
        )  # i+2 because i is 0-indexed

        # Compute IDCG@K (ideal: all relevant first)
        num_relevant = sum(relevance_scores)
        ideal_scores = [1] * num_relevant + [0] * (len(top_k_scores) - num_relevant)
        idcg = sum(
            rel / math.log2(i + 2) for i, rel in enumerate(ideal_scores[: self._k])
        )

        # Normalize
        if idcg == 0:
            ndcg = 0.0
        else:
            ndcg = dcg / idcg

        return NDCGAtKResult(
            status=MetricStatus.COMPUTED,
            value=round(ndcg, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "k": self._k,
                "retrieved_count": len(items),
                "gold_count": len(gold),
                "dcg": round(dcg, 6),
                "idcg": round(idcg, 6),
                "num_relevant": num_relevant,
            },
        )


@dataclass
class RPrecisionResult(MetricResult):
    """Result of R-Precision computation."""

    metric_id: str = field(init=False, default="retrieval.r_precision")
    metric_version: str = field(init=False, default="1")


class RPrecision:
    """R-Precision: Precision at R where R = number of relevant items.

    Formula:
        R-Prec = relevant_in_top_R / R

    Where R = total number of gold evidence items.

    Requirements:
        - GOLD_EVIDENCE: Benchmark must have gold evidence
        - RETRIEVAL: Target must produce retrieval results

    Edge cases:
        - No gold evidence → UNAVAILABLE_MISSING_INPUT
        - R > len(retrieved) → use len(retrieved) as R
        - Zero retrieved → 0.0
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="retrieval.r_precision",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.GOLD_EVIDENCE, MetricRequirement.RETRIEVAL}
            ),
            description="Precision at R where R = number of gold evidence items.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check gold evidence
        if not context.has_gold_evidence():
            return RPrecisionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Benchmark has no gold evidence",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return RPrecisionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        items = stage.items
        gold = [e.model_dump(mode="json") for e in context.case.gold_evidence]

        # R = number of gold items
        r = len(gold)

        # Handle empty retrieval
        if not items:
            return RPrecisionResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"r": r, "retrieved_count": len(items), "relevant_count": 0},
            )

        # Use min(R, len(items)) as cutoff
        cutoff = min(r, len(items))
        top_r = items[:cutoff]

        # Count relevant
        relevant_count = sum(1 for item in top_r if _is_item_relevant(item, gold))

        # Precision at R
        precision = safe_divide(relevant_count, cutoff, default=0.0)

        return RPrecisionResult(
            status=MetricStatus.COMPUTED,
            value=round(precision, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "r": r,
                "cutoff": cutoff,
                "retrieved_count": len(items),
                "relevant_count": relevant_count,
            },
        )


# Export all retrieval metrics
__all__ = [
    "HitAtK",
    "PrecisionAtK",
    "RecallAtK",
    "MRR",
    "MAPAtK",
    "NDCGAtK",
    "RPrecision",
]
