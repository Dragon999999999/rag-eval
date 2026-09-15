"""Citation structure metrics for Stage 12.

Deterministic metrics evaluating citation structure and attribution.
These measure structural resolution, not semantic faithfulness.

Metrics:
- citation_resolution: Fraction of answer span covered by citations
- broken_citations: Fraction of citations pointing to non-existent sources
- attribution_rate: Fraction of answer tokens covered by cited spans
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
    compute_span_union_length,
    get_answer_span_union,
    safe_divide,
    spans_overlap,
)


@dataclass
class CitationResolutionResult(MetricResult):
    """Result of citation resolution computation."""

    metric_id: str = field(init=False, default="citation.resolution")
    metric_version: str = field(init=False, default="1")


class CitationResolution:
    """Citation Resolution: Fraction of answer span covered by citations.

    Measures whether citations structurally resolve to retrieved evidence.
    Does NOT measure whether citations semantically support claims.

    Formula:
        Resolution = covered_answer_span / total_answer_span

    Where:
        - covered_answer_span: Length of answer covered by valid citations
        - total_answer_span: Total length of answer text

    Requirements:
        - ANSWER: Target must produce answer
        - CITATIONS: Target must produce citations
        - RETRIEVAL: Citations must reference retrieved items

    Edge cases:
        - No answer → UNAVAILABLE_MISSING_INPUT
        - No citations → UNAVAILABLE_MISSING_INPUT
        - Empty answer → 0.0 (no span to cover)
        - All citations broken → 0.0
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="citation.resolution",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {
                    MetricRequirement.ANSWER,
                    MetricRequirement.CITATIONS,
                    MetricRequirement.RETRIEVAL,
                }
            ),
            description="Fraction of answer span covered by valid citations.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check answer
        answer_text = context.get_answer_text()
        if answer_text is None:
            return CitationResolutionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Check citations
        if not context.has_citations():
            return CitationResolutionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no citations",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"answer_length": len(answer_text)},
            )

        # Get citations
        observation = context.observation
        if observation is None or observation.answer is None:
            return CitationResolutionResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access answer citations",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        citations = observation.answer.citations

        # Handle empty answer
        if len(answer_text) == 0:
            return CitationResolutionResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "answer_length": 0,
                    "citation_count": len(citations),
                    "covered_length": 0,
                    "reason": "Empty answer",
                },
            )

        # Get answer span union from citations
        answer_spans = get_answer_span_union(citations)
        covered_length = compute_span_union_length(answer_spans)
        total_length = len(answer_text)

        resolution = safe_divide(covered_length, total_length, default=0.0)

        return CitationResolutionResult(
            status=MetricStatus.COMPUTED,
            value=round(resolution, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "answer_length": total_length,
                "citation_count": len(citations),
                "covered_length": covered_length,
                "span_count": len(answer_spans),
            },
        )


@dataclass
class BrokenCitationsResult(MetricResult):
    """Result of broken citations computation."""

    metric_id: str = field(init=False, default="citation.broken")
    metric_version: str = field(init=False, default="1")


class BrokenCitations:
    """Broken Citations: Fraction of citations pointing to non-existent sources.

    A citation is broken if:
    - It references a document_id not in retrieval results
    - It references a page number not in the cited document
    - It references a span outside the cited document's bounds

    Formula:
        Broken Rate = broken_citations / total_citations

    Requirements:
        - ANSWER: Target must produce answer
        - CITATIONS: Target must produce citations
        - RETRIEVAL: Must have retrieval results to validate against

    Edge cases:
        - No citations → UNAVAILABLE_MISSING_INPUT
        - No retrieval → UNAVAILABLE_MISSING_INPUT
        - All citations valid → 0.0
        - All citations broken → 1.0
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="citation.broken",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {
                    MetricRequirement.ANSWER,
                    MetricRequirement.CITATIONS,
                    MetricRequirement.RETRIEVAL,
                }
            ),
            description="Fraction of citations pointing to non-existent sources.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check citations
        if not context.has_citations():
            return BrokenCitationsResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no citations",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Check retrieval
        stage = context.get_candidate_retrieval()
        if stage is None:
            return BrokenCitationsResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no retrieval results",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Get citations
        observation = context.observation
        if observation is None or observation.answer is None:
            return BrokenCitationsResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access answer citations",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        citations = observation.answer.citations

        if not citations:
            return BrokenCitationsResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Citations list is empty",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Build document index from retrieval
        doc_ids = set()
        doc_pages: dict[str, set[int]] = {}
        doc_spans: dict[str, list[tuple[int, int]]] = {}

        for item in stage.items:
            source = item.get("source", {})
            doc_id = source.get("document_id")
            if doc_id:
                doc_ids.add(doc_id)

                # Track pages
                page = source.get("page")
                if page is not None:
                    if doc_id not in doc_pages:
                        doc_pages[doc_id] = set()
                    doc_pages[doc_id].add(page)

                # Track spans
                start = source.get("start_char")
                end = source.get("end_char")
                if start is not None and end is not None:
                    if doc_id not in doc_spans:
                        doc_spans[doc_id] = []
                    doc_spans[doc_id].append((start, end))

        # Check each citation
        broken_count = 0
        broken_details = []

        for idx, citation in enumerate(citations):
            cited_doc_id = citation.get("document_id")
            cited_page = citation.get("page")
            cited_start = citation.get("start_char")
            cited_end = citation.get("end_char")

            is_broken = False
            break_reason = None

            # Check document exists
            if cited_doc_id not in doc_ids:
                is_broken = True
                break_reason = f"Document {cited_doc_id} not in retrieval"
            else:
                # Check page if specified
                if cited_page is not None:
                    doc_page_set = doc_pages.get(cited_doc_id, set())
                    if cited_page not in doc_page_set:
                        is_broken = True
                        break_reason = (
                            f"Page {cited_page} not in document {cited_doc_id}"
                        )

                # Check span if specified
                if cited_start is not None and cited_end is not None:
                    doc_span_list = doc_spans.get(cited_doc_id, [])
                    # Check if citation span overlaps with any retrieved span
                    span_valid = False
                    for start, end in doc_span_list:
                        if spans_overlap(cited_start, cited_end, start, end):
                            span_valid = True
                            break

                    if not span_valid:
                        is_broken = True
                        break_reason = f"Span [{cited_start}, {cited_end}) not in document {cited_doc_id}"

            if is_broken:
                broken_count += 1
                broken_details.append({"citation_index": idx, "reason": break_reason})

        broken_rate = safe_divide(broken_count, len(citations), default=0.0)

        return BrokenCitationsResult(
            status=MetricStatus.COMPUTED,
            value=round(broken_rate, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "total_citations": len(citations),
                "broken_citations": broken_count,
                "broken_details": broken_details[:10],  # Limit details
            },
        )


@dataclass
class AttributionRateResult(MetricResult):
    """Result of attribution rate computation."""

    metric_id: str = field(init=False, default="citation.attribution_rate")
    metric_version: str = field(init=False, default="1")


class AttributionRate:
    """Attribution Rate: Fraction of answer tokens covered by cited spans.

    Token-level version of citation resolution.
    Measures what fraction of answer content is attributed to sources.

    Formula:
        Attribution = covered_tokens / total_answer_tokens

    Requirements:
        - ANSWER: Target must produce answer
        - CITATIONS: Target must produce citations

    Edge cases:
        - No answer → UNAVAILABLE_MISSING_INPUT
        - No citations → UNAVAILABLE_MISSING_INPUT
        - Empty answer → 0.0
        - All tokens covered → 1.0
    """

    def __init__(self) -> None:
        self._definition = MetricDefinition(
            metric_id="citation.attribution_rate",
            version="1",
            scope=MetricScope.CASE,
            requirements=frozenset(
                {MetricRequirement.ANSWER, MetricRequirement.CITATIONS}
            ),
            description="Fraction of answer tokens covered by cited spans.",
        )

    @property
    def definition(self) -> MetricDefinition:
        return self._definition

    async def compute(self, context: MetricContext) -> MetricResult:
        # Check answer
        answer_text = context.get_answer_text()
        if answer_text is None:
            return AttributionRateResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target answer missing",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        # Check citations
        if not context.has_citations():
            return AttributionRateResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Target has no citations",
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={"answer_tokens": len(answer_text.split())},
            )

        # Get citations
        observation = context.observation
        if observation is None or observation.answer is None:
            return AttributionRateResult(
                status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
                reason="Cannot access answer citations",
                case_id=context.case.case_id,
                run_id=context.run_id,
            )

        citations = observation.answer.citations

        # Tokenize answer
        answer_tokens = answer_text.split()
        total_tokens = len(answer_tokens)

        # Handle empty answer
        if total_tokens == 0:
            return AttributionRateResult(
                status=MetricStatus.COMPUTED,
                value=0.0,
                case_id=context.case.case_id,
                run_id=context.run_id,
                details={
                    "total_tokens": 0,
                    "covered_tokens": 0,
                    "reason": "Empty answer",
                },
            )

        # Get character spans from citations
        spans = get_answer_span_union(citations)
        covered_length = compute_span_union_length(spans)

        # Estimate token coverage proportionally
        # This is approximate - assumes uniform token length
        answer_length = len(answer_text)
        if answer_length == 0:
            covered_tokens = 0
        else:
            coverage_fraction = covered_length / answer_length
            covered_tokens = int(coverage_fraction * total_tokens)

        attribution = safe_divide(covered_tokens, total_tokens, default=0.0)

        return AttributionRateResult(
            status=MetricStatus.COMPUTED,
            value=round(attribution, 6),
            case_id=context.case.case_id,
            run_id=context.run_id,
            details={
                "total_tokens": total_tokens,
                "covered_tokens": covered_tokens,
                "answer_length": answer_length,
                "covered_length": covered_length,
            },
        )


# Export all citation metrics
__all__ = [
    "CitationResolution",
    "BrokenCitations",
    "AttributionRate",
]
