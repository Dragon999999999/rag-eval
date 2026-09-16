"""Deterministic mock target server for Stage 14 E2E tests.

Implements Target Protocol v1 with:
- Deterministic behavior
- Fixture-controlled failure injection
- Idempotent request handling
- Synthetic retrieval/query/citations/usage/traces
- No external dependencies
"""

from __future__ import annotations

import hashlib
import json
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from fastapi import BackgroundTasks, Body, FastAPI, Header, HTTPException
from fastapi.responses import StreamingResponse

# Use canonical models where possible
from rag_eval.models import (
    AnswerSpan,
    Citation,
    CreateCorpusRequest,
    CreateCorpusResponse,
    ErrorRecord,
    HealthStatus,
    Operation,
    QueryRequest,
    QueryResponse,
    RequestRecoveryResult,
    RetrievalResult,
    RetrievalStage,
    RetrievedItem,
    RetrieveRequest,
    RetrieveResponse,
    SourceLocation,
    TargetCapabilities,
    TargetInfo,
    Trace,
    TraceSpan,
    Usage,
)
from rag_eval.models.enums import (
    ErrorCategory,
    FinishReason,
    HealthState,
    OperationStatus,
    RetrievalStageType,
)
from rag_eval.models.target import (
    RetrievalMetadataCapabilities,
    UsageCapabilities,
)

# ============================================================================
# Mock Target State
# ============================================================================


class FailureScenario(StrEnum):
    """Deterministic failure injection scenarios."""

    NONE = "none"
    RATE_LIMIT_ONCE = "429_once"
    RATE_LIMIT_ALWAYS = "429_always"
    OUTAGE_ONCE = "503_once"
    OUTAGE_TWICE = "503_twice"
    TIMEOUT_ONCE = "timeout_once"
    CONNECTION_DROP = "connection_drop"
    MALFORMED_JSON = "malformed_json"
    INVALID_PROTOCOL = "invalid_protocol"
    STREAM_INTERRUPT = "stream_interrupt"
    OPERATION_FAILURE = "operation_failure"


@dataclass
class MockCorpus:
    """In-memory corpus state."""

    corpus_id: str
    target_corpus_id: str | None = None
    status: str = "EMPTY"
    mode: str = "DOCUMENTS"
    documents: dict[str, dict[str, Any]] = field(default_factory=dict)
    chunks: list[dict[str, Any]] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class MockOperation:
    """In-memory operation state."""

    operation_id: str
    kind: str
    status: OperationStatus = OperationStatus.PENDING
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    progress: int = 0


@dataclass
class MockRequest:
    """In-memory request state for idempotency."""

    request_id: str
    idempotency_key: str | None = None
    request_hash: str | None = None
    status: str = "RUNNING"
    result: Any = None
    error: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    completed_at: datetime | None = None
    expensive_execution_count: int = 0  # Track actual expensive work


class MockTargetState:
    """Global mock target state."""

    def __init__(self) -> None:
        self.corpora: dict[str, MockCorpus] = {}
        self.operations: dict[str, MockOperation] = {}
        self.requests: dict[str, MockRequest] = {}
        self.idempotency_store: dict[str, MockRequest] = {}

        # Failure injection
        self.failure_scenario: FailureScenario = FailureScenario.NONE
        self.failure_counts: dict[str, int] = defaultdict(int)

        # Deterministic counters
        self.query_count = 0
        self.retrieve_count = 0

        # Fixture data
        self.fixture_answers: dict[str, str] = {}
        self.fixture_retrieval: dict[str, list[dict[str, Any]]] = {}


# Global state instance
state = MockTargetState()


# ============================================================================
# FastAPI Application
# ============================================================================


app = FastAPI(title="rag-eval Mock Target", version="1.0.0")


# ============================================================================
# Helper Functions
# ============================================================================


def check_failure_injection(endpoint: str) -> None:
    """Check if failure should be injected for this request."""
    scenario = state.failure_scenario

    if scenario == FailureScenario.NONE:
        return

    key = f"{endpoint}_{scenario.value}"
    count = state.failure_counts[key]

    # Determine if this request should fail
    should_fail = False

    if scenario == FailureScenario.RATE_LIMIT_ONCE and count == 0:
        should_fail = True
    elif scenario == FailureScenario.RATE_LIMIT_ALWAYS:
        should_fail = True
    elif scenario == FailureScenario.OUTAGE_ONCE and count == 0:
        should_fail = True
    elif scenario == FailureScenario.OUTAGE_TWICE and count < 2:
        should_fail = True
    elif scenario == FailureScenario.TIMEOUT_ONCE and count == 0:
        should_fail = True
    elif scenario == FailureScenario.CONNECTION_DROP:
        should_fail = True
    elif scenario == FailureScenario.MALFORMED_JSON:
        should_fail = True
    elif scenario == FailureScenario.INVALID_PROTOCOL:
        should_fail = True

    if should_fail:
        state.failure_counts[key] += 1

        # Raise appropriate error
        if scenario in (
            FailureScenario.RATE_LIMIT_ONCE,
            FailureScenario.RATE_LIMIT_ALWAYS,
        ):
            raise HTTPException(
                status_code=429,
                detail="Rate limit exceeded",
                headers={"Retry-After": "5"},
            )
        elif scenario in (FailureScenario.OUTAGE_ONCE, FailureScenario.OUTAGE_TWICE):
            raise HTTPException(
                status_code=503,
                detail="Service temporarily unavailable",
            )
        elif scenario == FailureScenario.TIMEOUT_ONCE:
            # Simulate timeout by sleeping too long
            time.sleep(30)
        elif scenario == FailureScenario.CONNECTION_DROP:
            # Simulate connection drop
            raise HTTPException(status_code=500, detail="Connection dropped")
        elif scenario == FailureScenario.MALFORMED_JSON:
            # Return invalid JSON
            raise HTTPException(status_code=200, detail="not-json{")
        elif scenario == FailureScenario.INVALID_PROTOCOL:
            raise HTTPException(status_code=400, detail="Invalid protocol version")


def compute_request_hash(request_data: dict[str, Any]) -> str:
    """Compute deterministic hash of request data."""
    canonical = json.dumps(request_data, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()


def get_or_create_request(
    request_id: str,
    idempotency_key: str | None,
    request_hash: str | None,
) -> MockRequest:
    """Get existing request or create new one with idempotency checking."""

    # Check idempotency
    if idempotency_key:
        if idempotency_key in state.idempotency_store:
            existing = state.idempotency_store[idempotency_key]

            # Check if request hash matches
            if request_hash and existing.request_hash != request_hash:
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency conflict: different request for same key",
                )

            return existing

    # Create new request
    request = MockRequest(
        request_id=request_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )

    state.requests[request_id] = request
    if idempotency_key:
        state.idempotency_store[idempotency_key] = request

    return request


def create_deterministic_trace(request_id: str) -> Trace:
    """Create deterministic trace spans."""
    now = datetime.now(UTC)

    return Trace(
        trace_id=f"trace-{request_id}",
        spans=[
            TraceSpan(
                span_id=f"span-retrieve-{request_id}",
                parent_span_id=None,
                name="retrieval",
                started_at=now,
                ended_at=datetime(
                    now.year,
                    now.month,
                    now.day,
                    now.hour,
                    now.minute,
                    now.second + 1,
                    now.microsecond,
                    tzinfo=UTC,
                ),
                duration_ms=50.0,
                attributes={"stage": "candidate_retrieval"},
            ),
            TraceSpan(
                span_id=f"span-rerank-{request_id}",
                parent_span_id=f"span-retrieve-{request_id}",
                name="reranking",
                started_at=datetime(
                    now.year,
                    now.month,
                    now.day,
                    now.hour,
                    now.minute,
                    now.second + 1,
                    now.microsecond,
                    tzinfo=UTC,
                ),
                ended_at=datetime(
                    now.year,
                    now.month,
                    now.day,
                    now.hour,
                    now.minute,
                    now.second + 2,
                    now.microsecond,
                    tzinfo=UTC,
                ),
                duration_ms=30.0,
                attributes={"stage": "rerank"},
            ),
            TraceSpan(
                span_id=f"span-generate-{request_id}",
                parent_span_id=f"span-retrieve-{request_id}",
                name="generation",
                started_at=datetime(
                    now.year,
                    now.month,
                    now.day,
                    now.hour,
                    now.minute,
                    now.second + 2,
                    now.microsecond,
                    tzinfo=UTC,
                ),
                ended_at=datetime(
                    now.year,
                    now.month,
                    now.day,
                    now.hour,
                    now.minute,
                    now.second + 3,
                    now.microsecond,
                    tzinfo=UTC,
                ),
                duration_ms=100.0,
                attributes={"stage": "generation"},
            ),
        ],
    )


def create_deterministic_usage() -> Usage:
    """Create deterministic usage data."""
    return Usage(
        tokens={"input": 100, "output": 50, "total": 150},
        calls={"retrieval": 1, "generation": 1},
        cost={"total": 0.002, "currency": "USD"},
        resources={},
        network={},
        metadata={},
    )


def create_deterministic_citations(request_id: str, answer_text: str) -> list[Citation]:
    """Create deterministic citations."""
    return [
        Citation(
            citation_id=f"cite-{uuid.uuid4()}",
            answer_span=AnswerSpan(
                start_char=0,
                end_char=min(20, len(answer_text)),
            ),
            source=SourceLocation(
                document_id="doc-1",
                page=1,
                start_char=0,
                end_char=50,
            ),
            retrieval_id=f"retrieval-{uuid.uuid4()}",
            display="Example Document (p.1)",
        ),
    ]


def create_deterministic_retrieval(query: str) -> RetrievalResult:
    """Create deterministic retrieval results with multiple stages."""
    items = [
        RetrievedItem(
            retrieval_id=f"retrieval-{uuid.uuid4()}",
            rank=1,
            text="Example document content for testing",
            source=SourceLocation(
                document_id="doc-1",
                page=1,
                start_char=0,
                end_char=100,
            ),
            score={"value": 0.95, "type": "similarity"},
            metadata={"stage": "candidate"},
        ),
        RetrievedItem(
            retrieval_id=f"retrieval-{uuid.uuid4()}",
            rank=2,
            text="Another relevant document",
            source=SourceLocation(
                document_id="doc-2",
                page=1,
                start_char=0,
                end_char=80,
            ),
            score={"value": 0.85, "type": "similarity"},
            metadata={"stage": "candidate"},
        ),
    ]

    return RetrievalResult(
        stages=[
            RetrievalStage(
                stage_id="stage-candidate",
                type=RetrievalStageType.CANDIDATE_RETRIEVAL,
                items=items,
                metadata={"count": len(items)},
            ),
            RetrievalStage(
                stage_id="stage-final",
                type=RetrievalStageType.FINAL_CONTEXT,
                items=items[:1],  # Top 1
                metadata={"count": 1},
            ),
        ],
        metadata={"query": query},
    )


# ============================================================================
# Protocol Endpoints
# ============================================================================


@app.get("/eval/v1/health")
async def health() -> HealthStatus:
    """Health check endpoint."""
    check_failure_injection("health")

    return HealthStatus(
        status=HealthState.READY,
        target=TargetInfo(
            name="rag-eval-mock-target",
            version="1.0.0",
            implementation="mock-fastapi",
        ),
    )


@app.get("/eval/v1/capabilities")
async def capabilities() -> TargetCapabilities:
    """Advertise target capabilities."""
    check_failure_injection("capabilities")

    return TargetCapabilities(
        target=TargetInfo(
            name="rag-eval-mock-target",
            version="1.0.0",
            implementation="mock-fastapi",
        ),
        protocol_version="1",
        query=True,
        streaming=True,
        retrieval=True,
        retrieval_stages=True,
        document_ingestion=True,
        chunk_ingestion=True,
        context_injection=True,
        citations=True,
        confidence=True,
        target_trace=True,
        usage=UsageCapabilities(tokens=True, cost=True),
        retrieval_metadata=RetrievalMetadataCapabilities(
            rank=True,
            score=True,
            document_id=True,
            chunk_id=True,
            page=True,
            character_span=True,
        ),
        idempotency=True,
        request_recovery=True,
    )


@app.post("/eval/v1/corpora")
async def create_corpus(request: CreateCorpusRequest) -> CreateCorpusResponse:
    """Create a new corpus."""
    check_failure_injection("create_corpus")

    corpus_id = f"corpus-{uuid.uuid4()}"
    target_corpus_id = f"target-{corpus_id}"

    corpus = MockCorpus(
        corpus_id=corpus_id,
        target_corpus_id=target_corpus_id,
        status="EMPTY",
        mode=request.mode.value
        if hasattr(request.mode, "value")
        else str(request.mode),
    )

    state.corpora[corpus_id] = corpus

    return CreateCorpusResponse(
        corpus_id=corpus_id,
        status="EMPTY",
    )


@app.get("/eval/v1/corpora/{corpus_id}")
async def get_corpus(corpus_id: str) -> dict[str, Any]:
    """Get corpus status."""
    check_failure_injection("get_corpus")

    if corpus_id not in state.corpora:
        raise HTTPException(status_code=404, detail="Corpus not found")

    corpus = state.corpora[corpus_id]
    return {
        "corpus_id": corpus.corpus_id,
        "target_corpus_id": corpus.target_corpus_id,
        "status": corpus.status,
        "mode": corpus.mode,
        "document_count": len(corpus.documents),
        "chunk_count": len(corpus.chunks),
        "created_at": corpus.created_at.isoformat(),
    }


@app.delete("/eval/v1/corpora/{corpus_id}")
async def delete_corpus(corpus_id: str) -> dict[str, str]:
    """Delete a corpus."""
    check_failure_injection("delete_corpus")

    if corpus_id not in state.corpora:
        raise HTTPException(status_code=404, detail="Corpus not found")

    del state.corpora[corpus_id]
    return {"status": "deleted"}


@app.post("/eval/v1/corpora/{corpus_id}/documents")
async def upload_document(
    corpus_id: str,
    background_tasks: BackgroundTasks,
) -> Operation:
    """Upload a document to the corpus."""
    check_failure_injection("upload_document")

    if corpus_id not in state.corpora:
        raise HTTPException(status_code=404, detail="Corpus not found")

    operation_id = f"op-doc-{uuid.uuid4()}"

    operation = MockOperation(
        operation_id=operation_id,
        kind="DOCUMENT_INGESTION",
        status=OperationStatus.RUNNING,
        progress=0,
    )

    state.operations[operation_id] = operation

    # Simulate async processing
    async def process_document() -> None:
        operation.status = OperationStatus.SUCCEEDED
        operation.progress = 100
        operation.result = {"document_id": "doc-1"}
        operation.updated_at = datetime.now(UTC)

        # Update corpus
        corpus = state.corpora[corpus_id]
        corpus.documents["doc-1"] = {"filename": "test.txt", "size": 100}
        corpus.status = "READY"

    background_tasks.add_task(process_document)

    return Operation(
        operation_id=operation_id,
        kind="DOCUMENT_INGESTION",
        status=OperationStatus.PENDING,
    )


@app.post("/eval/v1/corpora/{corpus_id}/chunks")
async def upload_chunks(corpus_id: str) -> Operation:
    """Upload chunks to the corpus."""
    check_failure_injection("upload_chunks")

    if corpus_id not in state.corpora:
        raise HTTPException(status_code=404, detail="Corpus not found")

    operation_id = f"op-chunks-{uuid.uuid4()}"

    operation = MockOperation(
        operation_id=operation_id,
        kind="CHUNK_INGESTION",
        status=OperationStatus.SUCCEEDED,
        progress=100,
    )

    state.operations[operation_id] = operation

    # Update corpus
    corpus = state.corpora[corpus_id]
    corpus.chunks.append({"chunk_id": "chunk-1", "text": "test"})
    corpus.status = "READY"

    return Operation(
        operation_id=operation_id,
        kind="CHUNK_INGESTION",
        status=OperationStatus.SUCCEEDED,
    )


@app.get("/eval/v1/operations/{operation_id}")
async def get_operation(operation_id: str) -> Operation:
    """Get operation status."""
    check_failure_injection("get_operation")

    if operation_id not in state.operations:
        raise HTTPException(status_code=404, detail="Operation not found")

    operation = state.operations[operation_id]
    return Operation(
        operation_id=operation.operation_id,
        kind=operation.kind,
        status=operation.status,
        metadata={
            "progress": operation.progress,
            "result": operation.result,
            "error": operation.error,
        },
    )


@app.post("/eval/v1/retrieve")
async def retrieve(request: RetrieveRequest) -> RetrieveResponse:
    """Retrieve relevant items."""
    check_failure_injection("retrieve")

    state.retrieve_count += 1

    query = request.query or ""
    retrieval_result = create_deterministic_retrieval(query)

    return RetrieveResponse(
        request_id=request.request_id,
        retrieval=retrieval_result,
    )


@app.post("/eval/v1/query")
async def query(
    request: QueryRequest,
    idempotency_key: str | None = Header(None, alias="Idempotency-Key"),
) -> QueryResponse:
    """Process a query and return answer."""
    check_failure_injection("query")

    state.query_count += 1

    # Handle idempotency
    # Exclude request_id from hash - idempotency is about the query content, not the request identifier
    request_data = request.model_dump(mode="json")
    request_data.pop("request_id", None)
    request_hash = compute_request_hash(request_data)

    mock_request = get_or_create_request(
        request_id=request.request_id,
        idempotency_key=idempotency_key,
        request_hash=request_hash,
    )

    # Check if already completed (idempotent replay)
    if mock_request.status == "COMPLETED" and mock_request.result:
        # Return cached result without expensive execution
        return QueryResponse(**mock_request.result)

    # Expensive execution (only once per unique request)
    mock_request.expensive_execution_count += 1

    # Generate deterministic answer
    answer_text = f"Answer for query: {request.query or 'unknown'}"

    # Build response
    response_data = {
        "request_id": request.request_id,
        "answer": {
            "text": answer_text,
            "finish_reason": FinishReason.STOP.value,
            "citations": [
                c.model_dump(mode="json")
                for c in create_deterministic_citations(request.request_id, answer_text)
            ],
        },
        "retrieval": create_deterministic_retrieval(request.query or "").model_dump(
            mode="json"
        ),
        "usage": create_deterministic_usage().model_dump(mode="json"),
        "trace": create_deterministic_trace(request.request_id).model_dump(mode="json"),
        "confidence": [],
    }

    # Store result for idempotency
    mock_request.result = response_data
    mock_request.status = "COMPLETED"
    mock_request.completed_at = datetime.now(UTC)

    return QueryResponse(**response_data)


@app.get("/eval/v1/requests/{request_id}")
async def get_request(request_id: str) -> RequestRecoveryResult:
    """Recover a previous request."""
    check_failure_injection("get_request")

    if request_id not in state.requests:
        raise HTTPException(status_code=404, detail="Request not found")

    mock_request = state.requests[request_id]

    if mock_request.status == "RUNNING":
        return RequestRecoveryResult(
            request_id=request_id,
            status="RUNNING",
        )
    elif mock_request.status == "COMPLETED" and mock_request.result:
        return RequestRecoveryResult(
            request_id=request_id,
            status="COMPLETED",
            response=QueryResponse(**mock_request.result),
        )
    else:
        return RequestRecoveryResult(
            request_id=request_id,
            status="FAILED",
            error=ErrorRecord(
                error_id=f"error-{uuid.uuid4()}",
                category=ErrorCategory.ERROR,
                code="REQUEST_FAILED",
                message=mock_request.error or "Unknown error",
            ),
        )


@app.post("/eval/v1/stream-query")
async def stream_query(request: QueryRequest) -> StreamingResponse:
    """Stream query response with SSE."""
    check_failure_injection("stream_query")

    scenario = state.failure_scenario

    async def generate_events():
        request_id = request.request_id

        # Emit deterministic event sequence
        events = [
            {"type": "request.started", "request_id": request_id},
            {"type": "retrieval.started", "stage": "candidate_retrieval"},
            {"type": "retrieval.completed", "items_count": 2},
            {"type": "generation.started"},
            {"type": "token.delta", "text": "Answer"},
            {"type": "token.delta", "text": " for"},
            {"type": "token.delta", "text": " query"},
            {"type": "usage.updated", "tokens": {"input": 100, "output": 50}},
            {"type": "generation.completed", "finish_reason": "stop"},
            {"type": "request.completed", "request_id": request_id},
        ]

        # Check for stream interruption
        interrupt_at = None
        if scenario == FailureScenario.STREAM_INTERRUPT:
            interrupt_at = 5  # Interrupt after 5 events

        for i, event in enumerate(events):
            if interrupt_at is not None and i >= interrupt_at:
                # Simulate stream interruption
                break

            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        generate_events(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        },
    )


# ============================================================================
# Test Configuration Endpoints
# ============================================================================


@app.post("/test/configure-failure")
async def configure_failure(scenario: FailureScenario = Body(...)) -> dict[str, str]:
    """Configure failure injection scenario."""
    state.failure_scenario = scenario
    state.failure_counts.clear()
    return {"status": "configured", "scenario": scenario.value}


@app.get("/test/state")
async def get_state() -> dict[str, Any]:
    """Get current mock target state."""
    return {
        "corpora_count": len(state.corpora),
        "operations_count": len(state.operations),
        "requests_count": len(state.requests),
        "query_count": state.query_count,
        "retrieve_count": state.retrieve_count,
        "failure_scenario": state.failure_scenario.value,
        "failure_counts": dict(state.failure_counts),
        "expensive_executions": sum(
            r.expensive_execution_count for r in state.requests.values()
        ),
    }


@app.delete("/test/state")
async def reset_state() -> dict[str, str]:
    """Reset all mock target state."""
    state.corpora.clear()
    state.operations.clear()
    state.requests.clear()
    state.idempotency_store.clear()
    state.failure_counts.clear()
    state.query_count = 0
    state.retrieve_count = 0
    state.failure_scenario = FailureScenario.NONE
    return {"status": "reset"}
