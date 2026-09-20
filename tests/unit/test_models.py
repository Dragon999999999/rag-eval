"""Round-trip and invariant tests for canonical Stage 2 data models."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from rag_eval.models import (
    Answer,
    AnswerSpan,
    ArtifactRef,
    BenchmarkCase,
    Citation,
    ConfidenceSignal,
    ContextPolicy,
    ErrorCategory,
    ErrorRecord,
    EvidenceSpan,
    FinishReason,
    Message,
    MetricResult,
    MetricStatus,
    QueryRequest,
    QueryResponse,
    RetrievalResult,
    RetrievalScore,
    RetrievalStage,
    RetrievalStageType,
    RetrievedItem,
    RetrieveRequest,
    RetrieveResponse,
    SourceLocation,
    SuppliedContext,
    TargetCapabilities,
    TargetObservation,
    Trace,
    TraceSpan,
    Usage,
)
from rag_eval.models.common import MessageRole

NOW = datetime(2026, 9, 14, 15, 0, tzinfo=UTC)


def build_retrieval() -> RetrievalResult:
    """Build a representative multi-stage retrieval result."""
    source = SourceLocation(
        document_id="paper-17",
        chunk_id="paper-17-c23",
        page=8,
        start_char=1404,
        end_char=1694,
    )
    item = RetrievedItem(
        retrieval_id="r-283",
        rank=1,
        text="The main limitation is incomplete coverage.",
        source=source,
        score=RetrievalScore(value=0.927, type="cosine_similarity"),
    )
    return RetrievalResult(
        stages=[
            RetrievalStage(
                stage_id="dense",
                type=RetrievalStageType.CANDIDATE_RETRIEVAL,
                items=[item],
            ),
            RetrievalStage(
                stage_id="final",
                parent_stage_id="dense",
                type=RetrievalStageType.FINAL_CONTEXT,
                items=[item],
            ),
        ]
    )


def test_benchmark_case_serializes_and_preserves_gold_evidence() -> None:
    """Benchmark truth round-trips without depending on a target chunk ID."""
    case = BenchmarkCase(
        case_id="case-1",
        query="What limitation was identified?",
        history=[Message(role=MessageRole.USER, content="Read the paper.")],
        gold_evidence=[
            EvidenceSpan(
                evidence_id="evidence-1",
                document_id="paper-17",
                page=8,
                start_char=1404,
                end_char=1694,
            )
        ],
    )

    assert BenchmarkCase.model_validate_json(case.model_dump_json()) == case


def test_invalid_rank_page_and_span_are_rejected() -> None:
    """Canonical coordinate and ranking invariants reject invalid values."""
    with pytest.raises(ValidationError):
        RetrievedItem(retrieval_id="r", rank=0)
    with pytest.raises(ValidationError):
        SourceLocation(page=0)
    with pytest.raises(ValidationError):
        AnswerSpan(start_char=8, end_char=7)


def test_timestamps_must_be_timezone_aware() -> None:
    """Trace and artifact timestamps reject naive datetime values."""
    with pytest.raises(ValidationError):
        ArtifactRef(
            artifact_id="a", uri="s3://bucket/a", created_at=datetime(2026, 1, 1)
        )
    with pytest.raises(ValidationError):
        TraceSpan(span_id="s", name="query", started_at=datetime(2026, 1, 1))


def test_query_request_context_policy_and_optional_capabilities() -> None:
    """Context injection is explicit and capabilities permit minor extensions."""
    context = SuppliedContext(context_id="ctx-1", text="Evidence")
    request = QueryRequest(
        request_id="request-1",
        query="Question",
        context_policy=ContextPolicy.SUPPLIED_CONTEXT,
        supplied_contexts=[context],
    )
    capabilities = TargetCapabilities.model_validate(
        {
            "target": {"name": "example"},
            "query": True,
            "future_optional_capability": True,
        }
    )

    assert request.supplied_contexts == [context]
    assert capabilities.retrieval is False
    with pytest.raises(ValidationError):
        QueryRequest(
            request_id="request-2",
            query="Question",
            context_policy=ContextPolicy.SUPPLIED_CONTEXT,
        )


def test_query_response_round_trip_preserves_empty_and_absent_retrieval() -> None:
    """A complete response round-trips while preserving retrieval semantics."""
    retrieval = build_retrieval()
    response = QueryResponse(
        request_id="request-1",
        answer=Answer(
            text="The limitation is incomplete coverage.",
            finish_reason=FinishReason.STOP,
            citations=[
                Citation(
                    citation_id="citation-1",
                    answer_span=AnswerSpan(start_char=0, end_char=35),
                    source=retrieval.stages[-1].items[0].source,
                    retrieval_id="r-283",
                    display="[1]",
                )
            ],
        ),
        retrieval=retrieval,
        confidence=[
            ConfidenceSignal(
                name="answer_confidence",
                value=0.87,
                minimum=0,
                maximum=1,
                semantics="probability_of_correctness",
            ),
            ConfidenceSignal(name="retrieval_confidence", value=0.93),
        ],
        trace=Trace(
            trace_id="trace-1",
            spans=[
                TraceSpan(span_id="root", name="query", started_at=NOW, duration_ms=10)
            ],
        ),
        usage=Usage(tokens={"input": 12, "output": 5, "total": 17}),
    )

    assert QueryResponse.model_validate_json(response.model_dump_json()) == response
    assert response.retrieval is not None and len(response.retrieval.stages) == 2
    empty_response = QueryResponse(request_id="empty", retrieval=RetrievalResult())
    assert empty_response.retrieval is not None
    assert empty_response.retrieval.stages == []
    assert QueryResponse(request_id="missing").retrieval is None


def test_target_observation_round_trip_preserves_raw_artifacts() -> None:
    """Normalized target data keeps response artifacts for future rescoring."""
    observation = TargetObservation(
        observation_id="observation-1",
        case_id="case-1",
        request_id="request-1",
        answer=Answer(text="Answer", finish_reason=FinishReason.STOP),
        retrieval=build_retrieval(),
        raw_request_artifact=ArtifactRef(
            artifact_id="raw-request", uri="s3://bucket/request"
        ),
        raw_response_artifact=ArtifactRef(
            artifact_id="raw-response", uri="s3://bucket/response"
        ),
        created_at=NOW,
    )

    assert (
        TargetObservation.model_validate_json(observation.model_dump_json())
        == observation
    )


def test_metric_null_values_require_an_explanation() -> None:
    """Unavailable metrics remain null instead of becoming fabricated zeroes."""
    result = MetricResult(
        metric_result_id="metric-1",
        metric_id="citation_precision",
        metric_version="1.0",
        status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
        value=None,
        reason="Target did not expose citations.",
    )

    assert result.value is None
    with pytest.raises(ValidationError):
        MetricResult(
            metric_result_id="metric-2",
            metric_id="citation_precision",
            metric_version="1.0",
            status=MetricStatus.UNAVAILABLE_MISSING_INPUT,
        )


def test_protocol_models_generate_json_schema() -> None:
    """Public request, response, and result models expose Pydantic schemas."""
    models = [
        TargetCapabilities,
        BenchmarkCase,
        RetrieveRequest,
        RetrieveResponse,
        QueryRequest,
        QueryResponse,
        TargetObservation,
        MetricResult,
    ]

    for model in models:
        schema = model.model_json_schema()
        assert schema["type"] == "object"


def test_error_category_uses_canonical_enum() -> None:
    """Error records normalize target failures to documented categories."""
    error = ErrorRecord(
        error_id="error-1",
        category=ErrorCategory.RATE_LIMIT,
        code="RATE_LIMITED",
        message="Retry later.",
        retryable=True,
    )

    assert error.category == ErrorCategory.RATE_LIMIT
