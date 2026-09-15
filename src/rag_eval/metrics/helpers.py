"""Shared helpers for Stage 12 deterministic metrics.

Centralizes reusable formulas for:
- Text normalization
- Tokenization
- Safe math
- Span overlap
- Relevance matching
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Any


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Safely divide two numbers with explicit default for zero denominator.

    Args:
        numerator: Dividend.
        denominator: Divisor.
        default: Value to return when denominator is zero.

    Returns:
        Division result or default.
    """
    if denominator == 0:
        return default
    return numerator / denominator


def normalize_text(text: str) -> str:
    """Normalize text for comparison.

    Applies:
    - Unicode NFKC normalization
    - Lowercase
    - Whitespace normalization

    Args:
        text: Input text.

    Returns:
        Normalized text.
    """
    # Unicode normalize
    text = unicodedata.normalize("NFKC", text)
    # Lowercase
    text = text.lower()
    # Normalize whitespace
    text = " ".join(text.split())
    return text


def normalize_text_with_punctuation(text: str) -> str:
    """Normalize text with punctuation removal for normalized exact match.

    Applies:
    - Unicode NFKC normalization
    - Lowercase
    - Whitespace normalization
    - Punctuation removal

    Args:
        text: Input text.

    Returns:
        Normalized text without punctuation.
    """
    text = normalize_text(text)
    # Remove punctuation (keep alphanumeric and whitespace)
    text = re.sub(r"[^\w\s]", "", text)
    return text


def tokenize(text: str) -> list[str]:
    """Tokenize text into words.

    Uses Unicode-aware word boundaries.
    Lowercases and normalizes whitespace.

    Args:
        text: Input text.

    Returns:
        List of lowercase word tokens.
    """
    text = text.lower()
    # Match Unicode word characters
    tokens = re.findall(r"\w+", text, re.UNICODE)
    return tokens


def count_tokens(tokens: list[str]) -> dict[str, int]:
    """Count token occurrences (multiset representation).

    Args:
        tokens: List of tokens.

    Returns:
        Dictionary mapping token to count.
    """
    counts: dict[str, int] = {}
    for token in tokens:
        counts[token] = counts.get(token, 0) + 1
    return counts


def token_overlap(
    pred_tokens: list[str], ref_tokens: list[str]
) -> tuple[int, int, int]:
    """Compute token overlap between prediction and reference.

    Uses multiset (count-based) overlap.

    Args:
        pred_tokens: Prediction tokens.
        ref_tokens: Reference tokens.

    Returns:
        Tuple of (overlap_count, pred_count, ref_count).
    """
    pred_counts = count_tokens(pred_tokens)
    ref_counts = count_tokens(ref_tokens)

    overlap = 0
    for token, pred_count in pred_counts.items():
        ref_count = ref_counts.get(token, 0)
        overlap += min(pred_count, ref_count)

    return overlap, len(pred_tokens), len(ref_tokens)


def spans_overlap(start_a: int, end_a: int, start_b: int, end_b: int) -> bool:
    """Check if two half-open character spans overlap.

    Spans are [start, end) - start inclusive, end exclusive.

    Overlap exists iff:
        max(start_a, start_b) < min(end_a, end_b)

    Args:
        start_a: Start of span A.
        end_a: End of span A (exclusive).
        start_b: Start of span B.
        end_b: End of span B (exclusive).

    Returns:
        True if spans overlap.

    Examples:
        [0, 5) and [5, 10) → False (touching but not overlapping)
        [0, 5) and [4, 10) → True (overlap at [4, 5))
    """
    return max(start_a, start_b) < min(end_a, end_b)


@dataclass(frozen=True)
class SpanMatch:
    """Result of matching one gold span against retrieved items."""

    gold_document_id: str
    gold_start_char: int | None
    gold_end_char: int | None
    gold_page: int | None
    matched: bool
    matched_item_index: int | None = None
    match_type: str | None = None  # "span", "page", "document"


def match_gold_evidence(
    gold_evidence: list[dict[str, Any]],
    retrieved_items: list[dict[str, Any]],
) -> list[SpanMatch]:
    """Match gold evidence against retrieved items.

    Uses hierarchical matching:
    1. Same document + overlapping character span (most specific)
    2. Same document + matching page
    3. Same document identity only (least specific)

    Args:
        gold_evidence: List of gold evidence dicts with document_id, page, start_char, end_char.
        retrieved_items: List of retrieved item dicts with source info.

    Returns:
        List of span matches for each gold evidence.
    """
    matches = []

    for gold in gold_evidence:
        gold_doc_id = gold.get("document_id")
        gold_page = gold.get("page")
        gold_start = gold.get("start_char")
        gold_end = gold.get("end_char")

        if not gold_doc_id:
            # No document ID - cannot match
            matches.append(
                SpanMatch(
                    gold_document_id=gold_doc_id or "",
                    gold_start_char=gold_start,
                    gold_end_char=gold_end,
                    gold_page=gold_page,
                    matched=False,
                )
            )
            continue

        match_found = False
        match_index = None
        match_type = None

        # Try to find matching retrieved item
        for idx, item in enumerate(retrieved_items):
            source = item.get("source", {})
            item_doc_id = source.get("document_id")

            if item_doc_id != gold_doc_id:
                continue

            # Document matches - check for more specific match
            # Try character span overlap
            if gold_start is not None and gold_end is not None:
                item_start = source.get("start_char")
                item_end = source.get("end_char")

                if item_start is not None and item_end is not None:
                    if spans_overlap(gold_start, gold_end, item_start, item_end):
                        match_found = True
                        match_index = idx
                        match_type = "span"
                        break

            # Try page match
            if gold_page is not None:
                item_page = source.get("page")
                if item_page == gold_page:
                    match_found = True
                    match_index = idx
                    match_type = "page"
                    # Continue searching for potentially better span match

        # If no span match, use page or document match if found
        if not match_found and match_index is not None:
            match_found = True
            match_type = "page" if gold_page is not None else "document"

        # If still no match but document matched at page level
        if not match_found:
            for idx, item in enumerate(retrieved_items):
                source = item.get("source", {})
                if source.get("document_id") == gold_doc_id:
                    if gold_page is not None and source.get("page") == gold_page:
                        match_found = True
                        match_index = idx
                        match_type = "page"
                        break

        # Fall back to document-only match
        if not match_found:
            for idx, item in enumerate(retrieved_items):
                source = item.get("source", {})
                if source.get("document_id") == gold_doc_id:
                    match_found = True
                    match_index = idx
                    match_type = "document"
                    break

        matches.append(
            SpanMatch(
                gold_document_id=gold_doc_id,
                gold_start_char=gold_start,
                gold_end_char=gold_end,
                gold_page=gold_page,
                matched=match_found,
                matched_item_index=match_index,
                match_type=match_type,
            )
        )

    return matches


def compute_span_union_length(spans: list[tuple[int, int]]) -> int:
    """Compute the total length covered by a union of spans.

    Handles overlapping spans correctly (no double-counting).

    Args:
        spans: List of (start, end) tuples.

    Returns:
        Total covered length.
    """
    if not spans:
        return 0

    # Sort by start
    sorted_spans = sorted(spans, key=lambda s: s[0])

    # Merge overlapping spans
    merged = [sorted_spans[0]]
    for start, end in sorted_spans[1:]:
        last_start, last_end = merged[-1]
        if start <= last_end:
            # Overlapping - extend
            merged[-1] = (last_start, max(last_end, end))
        else:
            merged.append((start, end))

    # Sum lengths
    return sum(end - start for start, end in merged)


def get_answer_span_union(citations: list[dict[str, Any]]) -> list[tuple[int, int]]:
    """Extract union of answer spans from citations.

    Args:
        citations: List of citation dicts with answer_span info.

    Returns:
        List of (start, end) span tuples.
    """
    spans = []
    for citation in citations:
        answer_span = citation.get("answer_span")
        if answer_span:
            start = answer_span.get("start_char")
            end = answer_span.get("end_char")
            if start is not None and end is not None:
                spans.append((start, end))
    return spans


def format_currency(value: float, currency: str) -> str:
    """Format currency value with explicit currency code.

    Args:
        value: Monetary value.
        currency: Currency code (USD, EUR, etc.).

    Returns:
        Formatted string with currency code.
    """
    return f"{value:.4f} {currency}"
