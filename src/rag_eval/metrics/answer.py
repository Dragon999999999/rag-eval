"""Answer quality metrics for Stage 12.

Deterministic metrics comparing target answer against reference answer.
No LLM judges, embeddings, or external calls.

Metrics:
- exact_match: String equality
- normalized_exact_match: Equality after normalization
- token_precision: Token overlap precision
- token_recall: Token overlap recall
- token_f1: Token overlap F1
"""

from dataclasses import dataclass, field

from rag_eval.metrics.base import (
    MetricDefinition,
    MetricRequirement,
    MetricResult,
    MetricScope,
    MetricStatus,
)
from rag_eval.metrics.context import MetricContext
from rag_eval.metrics.helpers import (
    normalize_text_with_punctuation,
    safe_divide,
    token_overlap,
    tokenize,
)


@dataclass
class ExactMatchResult(MetricResult):
    """Result of exact match comparison.

    Fields:
        value: 1.0 for exact match, 0.0 otherwise
        details:
            - pred_text: Prediction text (may be null if missing)
            - ref_text: Reference text (may be null if missing)
            - match_type: "exact", "normalized", "none"
    """

    metric_id: str = field(init=False, default="answer.exact_match")
    metric_version: str = field(init=False, default="1")


class ExactMatch:
    """Exact string match between prediction and reference.

    Formula:
        EM = 1.0 if pred_text == ref_text else 0.0

    Requirements:
        - REFERENCE_ANSWER: Benchmark must have reference answer
        - ANSWER: Target must produce answer

    Edge cases:
        - Both empty strings → 1.0 (match)
        - One None, one "" → UNAVAILABLE_MISSING_INPUT
        - Whitespace differences → 0.0 (not exact match)
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="answer.exact_match",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.REFERENCE_ANSWER, MetricRequirement.ANSWER}
            ),
            description="Exact string equality between prediction and reference.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        pred_text = context.get_answer_text()
        ref_text = context.get_reference_answer()

        # Check requirements explicitly
        if pred_text is None:
            return ExactMatchResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"pred_text": None, "ref_text": ref_text},
            )

        if ref_text is None:
            return ExactMatchResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Reference answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"pred_text": pred_text, "ref_text": None},
            )

        # Exact string comparison
        match = pred_text == ref_text

        return ExactMatchResult(
            status=MetricStatus.COMPUTED,
            value=1.0 if match else 0.0,
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "pred_text": pred_text,
                "ref_text": ref_text,
                "match_type": "exact" if match else "none",
            },
        )


@dataclass
class NormalizedExactMatchResult(MetricResult):
    """Result of normalized exact match comparison."""

    metric_id: str = field(init=False, default="answer.normalized_exact_match")
    metric_version: str = field(init=False, default="1")


class NormalizedExactMatch:
    """Normalized exact match after text normalization.

    Formula:
        NEM = 1.0 if normalize(pred_text) == normalize(ref_text) else 0.0

    Normalization:
        - Unicode NFKC normalization
        - Lowercase
        - Whitespace normalization
        - Punctuation removal

    Requirements:
        - REFERENCE_ANSWER: Benchmark must have reference answer
        - ANSWER: Target must produce answer

    Edge cases:
        - Both empty → 1.0
        - "Hello!" vs "hello" → 1.0 (punctuation removed, case insensitive)
        - "Hello World" vs "hello  world" → 1.0 (whitespace normalized)
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="answer.normalized_exact_match",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.REFERENCE_ANSWER, MetricRequirement.ANSWER}
            ),
            description="Exact match after text normalization (lowercase, whitespace, punctuation).",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        pred_text = context.get_answer_text()
        ref_text = context.get_reference_answer()

        # Check requirements explicitly
        if pred_text is None:
            return NormalizedExactMatchResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"pred_text": None, "ref_text": ref_text},
            )

        if ref_text is None:
            return NormalizedExactMatchResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Reference answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"pred_text": pred_text, "ref_text": None},
            )

        # Normalize both
        pred_normalized = normalize_text_with_punctuation(pred_text)
        ref_normalized = normalize_text_with_punctuation(ref_text)

        match = pred_normalized == ref_normalized

        return NormalizedExactMatchResult(
            status=MetricStatus.COMPUTED,
            value=1.0 if match else 0.0,
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "pred_text": pred_text,
                "ref_text": ref_text,
                "pred_normalized": pred_normalized,
                "ref_normalized": ref_normalized,
                "match_type": "normalized" if match else "none",
            },
        )


@dataclass
class TokenPrecisionResult(MetricResult):
    """Result of token precision computation."""

    metric_id: str = field(init=False, default="answer.token_precision")
    metric_version: str = field(init=False, default="1")


class TokenPrecision:
    """Token-level precision using multiset overlap.

    Formula:
        Precision = overlap_count / pred_token_count

    Where overlap_count is the sum of min(pred_count[token], ref_count[token])
    for all tokens.

    Requirements:
        - REFERENCE_ANSWER: Benchmark must have reference answer
        - ANSWER: Target must produce answer

    Edge cases:
        - Empty prediction → UNAVAILABLE_MISSING_INPUT (cannot divide by zero)
        - Empty reference → 0.0 (no overlap possible)
        - Both empty → UNAVAILABLE_MISSING_INPUT
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="answer.token_precision",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.REFERENCE_ANSWER, MetricRequirement.ANSWER}
            ),
            description="Token-level precision using multiset overlap.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        pred_text = context.get_answer_text()
        ref_text = context.get_reference_answer()

        # Check requirements explicitly
        if pred_text is None:
            return TokenPrecisionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        if ref_text is None:
            return TokenPrecisionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Reference answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Tokenize
        pred_tokens = tokenize(pred_text)
        ref_tokens = tokenize(ref_text)

        # Handle empty prediction
        if not pred_tokens:
            return TokenPrecisionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Prediction has no tokens (cannot compute precision)",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "pred_text": pred_text,
                    "ref_text": ref_text,
                    "pred_tokens": 0,
                    "ref_tokens": len(ref_tokens),
                },
            )

        # Handle empty reference
        if not ref_tokens:
            return TokenPrecisionResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "pred_text": pred_text,
                    "ref_text": ref_text,
                    "pred_tokens": len(pred_tokens),
                    "ref_tokens": 0,
                    "overlap": 0,
                },
            )

        # Compute overlap
        overlap, pred_count, ref_count = token_overlap(pred_tokens, ref_tokens)
        precision = safe_divide(overlap, pred_count, default=0.0)

        return TokenPrecisionResult(
            status=MetricStatus.COMPUTED,
            value=round(precision, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "pred_text": pred_text,
                "ref_text": ref_text,
                "pred_tokens": pred_count,
                "ref_tokens": ref_count,
                "overlap": overlap,
            },
        )


@dataclass
class TokenRecallResult(MetricResult):
    """Result of token recall computation."""

    metric_id: str = field(init=False, default="answer.token_recall")
    metric_version: str = field(init=False, default="1")


class TokenRecall:
    """Token-level recall using multiset overlap.

    Formula:
        Recall = overlap_count / ref_token_count

    Requirements:
        - REFERENCE_ANSWER: Benchmark must have reference answer
        - ANSWER: Target must produce answer

    Edge cases:
        - Empty reference → UNAVAILABLE_MISSING_INPUT (cannot divide by zero)
        - Empty prediction → 0.0 (no overlap)
        - Both empty → UNAVAILABLE_MISSING_INPUT
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="answer.token_recall",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.REFERENCE_ANSWER, MetricRequirement.ANSWER}
            ),
            description="Token-level recall using multiset overlap.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        pred_text = context.get_answer_text()
        ref_text = context.get_reference_answer()

        # Check requirements explicitly
        if pred_text is None:
            return TokenRecallResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        if ref_text is None:
            return TokenRecallResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Reference answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Tokenize
        pred_tokens = tokenize(pred_text)
        ref_tokens = tokenize(ref_text)

        # Handle empty reference
        if not ref_tokens:
            return TokenRecallResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Reference has no tokens (cannot compute recall)",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "pred_text": pred_text,
                    "ref_text": ref_text,
                    "pred_tokens": len(pred_tokens),
                    "ref_tokens": 0,
                },
            )

        # Handle empty prediction
        if not pred_tokens:
            return TokenRecallResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "pred_text": pred_text,
                    "ref_text": ref_text,
                    "pred_tokens": 0,
                    "ref_tokens": len(ref_tokens),
                    "overlap": 0,
                },
            )

        # Compute overlap
        overlap, pred_count, ref_count = token_overlap(pred_tokens, ref_tokens)
        recall = safe_divide(overlap, ref_count, default=0.0)

        return TokenRecallResult(
            status=MetricStatus.COMPUTED,
            value=round(recall, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "pred_text": pred_text,
                "ref_text": ref_text,
                "pred_tokens": pred_count,
                "ref_tokens": ref_count,
                "overlap": overlap,
            },
        )


@dataclass
class TokenF1Result(MetricResult):
    """Result of token F1 computation."""

    metric_id: str = field(init=False, default="answer.token_f1")
    metric_version: str = field(init=False, default="1")


class TokenF1:
    """Token-level F1 score (harmonic mean of precision and recall).

    Formula:
        F1 = 2 * (precision * recall) / (precision + recall)

    Or equivalently:
        F1 = 2 * overlap / (pred_count + ref_count)

    Requirements:
        - REFERENCE_ANSWER: Benchmark must have reference answer
        - ANSWER: Target must produce answer

    Edge cases:
        - Both empty → 0.0 (no information content)
        - One empty → 0.0 (no overlap)
        - Perfect match → 1.0
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="answer.token_f1",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.REFERENCE_ANSWER, MetricRequirement.ANSWER}
            ),
            description="Token-level F1 score (harmonic mean of precision and recall).",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        pred_text = context.get_answer_text()
        ref_text = context.get_reference_answer()

        # Check requirements explicitly
        if pred_text is None:
            return TokenF1Result(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        if ref_text is None:
            return TokenF1Result(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Reference answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Tokenize
        pred_tokens = tokenize(pred_text)
        ref_tokens = tokenize(ref_text)

        # Handle both empty
        if not pred_tokens and not ref_tokens:
            return TokenF1Result(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "pred_text": pred_text,
                    "ref_text": ref_text,
                    "pred_tokens": 0,
                    "ref_tokens": 0,
                    "overlap": 0,
                    "reason": "Both prediction and reference are empty",
                },
            )

        # Compute overlap
        overlap, pred_count, ref_count = token_overlap(pred_tokens, ref_tokens)

        # F1 = 2 * overlap / (pred_count + ref_count)
        denominator = pred_count + ref_count
        if denominator == 0:
            f1 = 0.0
        else:
            f1 = 2.0 * overlap / denominator

        return TokenF1Result(
            status=MetricStatus.COMPUTED,
            value=round(f1, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "pred_text": pred_text,
                "ref_text": ref_text,
                "pred_tokens": pred_count,
                "ref_tokens": ref_count,
                "overlap": overlap,
            },
        )


# Export all answer metrics
__all__ = [
    "ExactMatch",
    "NormalizedExactMatch",
    "TokenPrecision",
    "TokenRecall",
    "TokenF1",
]
