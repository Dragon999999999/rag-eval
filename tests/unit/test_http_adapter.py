"""Deterministic protocol coverage for the async HTTP target adapter."""

import json
from collections.abc import AsyncIterator

import httpx
from pydantic import HttpUrl
import pytest

from rag_eval.adapters import (
    DocumentUpload,
    HttpTargetAdapter,
    TargetAdapterError,
    TargetProtocolError,
    create_target_adapter,
)
from rag_eval.config.models import CorpusConfig, ExperimentTargetConfig
from rag_eval.models import (
    Chunk,
    CorpusMode,
    CreateCorpusRequest,
    Document,
    QueryRequest,
    RetrieveRequest,
    SuppliedContext,
)
from rag_eval.models.enums import ContextPolicy


def _capabilities() -> dict[str, object]:
    """Return the documented nested capability envelope used by mock targets."""
    return {
        "protocol_version": "1.0",
        "target": {"name": "http-test"},
        "capabilities": {
            "query": True,
            "retrieval": True,
            "streaming": True,
            "request_recovery": True,
            "document_ingestion": True,
            "chunk_ingestion": True,
        },
        "limits": {"max_chunks_per_request": 2},
    }


def _adapter(handler: httpx.MockTransport) -> HttpTargetAdapter:
    """Create an adapter backed by one deterministic mock transport."""
    client = httpx.AsyncClient(transport=handler, base_url="https://ignored.test")
    return HttpTargetAdapter("https://target.test/", client=client, api_key="secret")


@pytest.mark.anyio
async def test_health_capabilities_config_and_authentication_headers() -> None:
    """Health, capabilities, config schema, protocol headers, and API key work."""
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_capabilities())
        if request.url.path.endswith("/health"):
            return httpx.Response(
                200, json={"status": "READY", "target": {"name": "http-test"}}
            )
        return httpx.Response(200, json={"type": "object", "properties": {}})

    adapter = _adapter(httpx.MockTransport(handler))
    assert (await adapter.capabilities()).target.name == "http-test"
    assert (await adapter.health()).status == "READY"
    assert await adapter.config_schema() == {"type": "object", "properties": {}}
    assert all(request.headers["X-Rag-Eval-Protocol"] == "1" for request in requests)
    assert requests[0].headers["X-API-Key"] == "secret"


@pytest.mark.anyio
async def test_corpus_document_and_bounded_chunk_upload_flow() -> None:
    """Corpus ingestion uses protocol paths, multipart fields, and bounded batches."""
    chunk_batches: list[list[object]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_capabilities())
        if request.url.path.endswith("/corpora") and request.method == "POST":
            return httpx.Response(
                200, json={"corpus_id": "corpus-1", "status": "EMPTY"}
            )
        if request.url.path.endswith("/corpora/corpus-1") and request.method == "GET":
            return httpx.Response(
                200, json={"corpus_id": "corpus-1", "status": "READY"}
            )
        if request.url.path.endswith("/documents"):
            assert b'name="file"' in request.content
            assert b'"document_id": "document-1"' in request.content
            return httpx.Response(
                200,
                json={
                    "operation_id": "document-op",
                    "kind": "DOCUMENT_INGESTION",
                    "status": "SUCCEEDED",
                },
            )
        if request.url.path.endswith("/chunks"):
            payload = json.loads(request.content)
            chunk_batches.append(payload["chunks"])
            return httpx.Response(
                200,
                json={
                    "operation_id": f"chunk-{len(chunk_batches)}",
                    "kind": "CHUNK_INGESTION",
                    "status": "SUCCEEDED",
                },
            )
        if request.url.path.endswith("/operations/chunk-2"):
            return httpx.Response(
                200,
                json={
                    "operation_id": "chunk-2",
                    "kind": "INGESTION",
                    "status": "SUCCEEDED",
                },
            )
        return httpx.Response(204)

    adapter = _adapter(httpx.MockTransport(handler))
    corpus = await adapter.create_corpus(
        CreateCorpusRequest(
            request_id="create-1", name="corpus", mode=CorpusMode.CHUNKS
        )
    )
    assert corpus.corpus_id == "corpus-1"
    assert (await adapter.get_corpus("corpus-1")).status == "READY"
    document_operation = await adapter.upload_document(
        "corpus-1",
        DocumentUpload(
            Document(document_id="document-1", filename="source.txt"), b"source"
        ),
    )

    async def chunks() -> AsyncIterator[Chunk]:
        for index in range(3):
            yield Chunk(
                chunk_id=f"chunk-{index}", document_id="document-1", text="text"
            )

    chunk_operation = await adapter.upload_chunks("corpus-1", chunks())
    await adapter.delete_corpus("corpus-1")
    assert document_operation.operation_id == "document-op"
    assert chunk_operation.operation_id == "chunk-2"
    assert [len(batch) for batch in chunk_batches] == [2, 1]
    assert (await adapter.get_operation("chunk-2")).status == "SUCCEEDED"


@pytest.mark.anyio
async def test_retrieve_query_context_and_recovery_preserve_canonical_models() -> None:
    """Retrieval stages and optional query observations survive HTTP normalization."""
    received_query: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_capabilities())
        if request.url.path.endswith("/retrieve"):
            return httpx.Response(
                200,
                json={
                    "request_id": "retrieve-1",
                    "retrieval": {
                        "stages": [
                            {"stage_id": "dense", "type": "CANDIDATE_RETRIEVAL"},
                            {"stage_id": "final", "type": "FINAL_CONTEXT"},
                        ]
                    },
                },
            )
        if request.url.path.endswith("/query"):
            assert request.headers["X-Request-ID"] == "query-1"
            assert request.headers["Idempotency-Key"] == "query-1"
            received_query.update(json.loads(request.content))
            return httpx.Response(
                200,
                headers={"Idempotency-Replayed": "true"},
                json={
                    "request_id": "query-1",
                    "answer": {
                        "text": "No answer provided.",
                        "finish_reason": "REFUSAL",
                        "citations": [],
                    },
                    "confidence": [{"name": "confidence", "value": 0.8}],
                    "usage": {"tokens": {"input": 3}},
                },
            )
        return httpx.Response(
            200,
            json={
                "request_id": "query-1",
                "status": "COMPLETED",
                "response": {"request_id": "query-1", "answer": {"text": "Recovered"}},
            },
        )

    adapter = _adapter(httpx.MockTransport(handler))
    retrieval = await adapter.retrieve(
        RetrieveRequest(request_id="retrieve-1", query="Q")
    )
    response = await adapter.query(
        QueryRequest(
            request_id="query-1",
            query="Q",
            context_policy=ContextPolicy.SUPPLIED_CONTEXT,
            supplied_contexts=[
                SuppliedContext(context_id="context-1", text="Evidence")
            ],
        )
    )
    assert [stage.stage_id for stage in retrieval.retrieval.stages] == [
        "dense",
        "final",
    ]
    assert response.answer is not None and response.answer.finish_reason == "REFUSAL"
    assert response.confidence[0].name == "confidence"
    assert received_query["context_policy"] == "SUPPLIED_CONTEXT"
    assert (
        adapter.last_transport is not None
        and adapter.last_transport.idempotency_replayed
    )
    recovery = await adapter.recover_request("query-1")
    assert recovery.response is not None


@pytest.mark.anyio
async def test_protocol_errors_throttling_and_invalid_responses_are_normalized() -> (
    None
):
    """Normalize HTTP envelopes, throttling, invalid JSON, and version mismatch."""

    def rate_limited(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            headers={"Retry-After": "2"},
            json={
                "error": {
                    "error_id": "error-1",
                    "category": "RATE_LIMIT",
                    "code": "RATE_LIMITED",
                    "message": "Slow down",
                    "retryable": True,
                }
            },
        )

    with pytest.raises(TargetAdapterError) as error:
        await _adapter(httpx.MockTransport(rate_limited)).health()
    assert error.value.to_error_record().retry_after_ms == 2000
    assert error.value.to_error_record().http_status == 429

    malformed = _adapter(
        httpx.MockTransport(lambda request: httpx.Response(200, text="nope"))
    )
    with pytest.raises(TargetProtocolError):
        await malformed.health()

    incompatible = _adapter(
        httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"target": {"name": "old"}, "protocol_version": "2.0"}
            )
        )
    )
    with pytest.raises(TargetProtocolError):
        await incompatible.capabilities()

    unavailable = _adapter(
        httpx.MockTransport(
            lambda request: (_ for _ in ()).throw(httpx.ConnectError("refused"))
        )
    )
    with pytest.raises(TargetAdapterError) as network_error:
        await unavailable.health()
    assert network_error.value.to_error_record().category == "CONNECTION"


@pytest.mark.anyio
async def test_sse_streaming_preserves_events_and_rejects_sequence_regression() -> None:
    """SSE data is parsed as events without a non-streaming fallback."""
    stream = (
        'data: {"event_id":"one","request_id":"query-2","sequence":0,'
        '"type":"token.delta","timestamp":"2026-09-14T00:00:00Z",'
        '"data":{"text":"Hello"}}\n\n'
        'data: {"event_id":"two","request_id":"query-2","sequence":1,'
        '"type":"request.completed","timestamp":"2026-09-14T00:00:01Z","data":{}}\n\n'
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path.endswith("/capabilities"):
            return httpx.Response(200, json=_capabilities())
        return httpx.Response(
            200, headers={"Content-Type": "text/event-stream"}, content=stream
        )

    adapter = _adapter(httpx.MockTransport(handler))
    events = [
        event
        async for event in adapter.stream_query(
            QueryRequest(request_id="query-2", query="Q", stream=True)
        )
    ]
    assert [event.type for event in events] == ["token.delta", "request.completed"]

    regressing = _adapter(
        httpx.MockTransport(
            lambda request: (
                httpx.Response(
                    200,
                    json=_capabilities(),
                )
                if request.url.path.endswith("/capabilities")
                else httpx.Response(
                    200,
                    content=(
                        'data: {"event_id":"a","request_id":"query-3","sequence":1,'
                        '"type":"token.delta","timestamp":"2026-09-14T00:00:00Z"}\n\n'
                        'data: {"event_id":"b","request_id":"query-3","sequence":1,'
                        '"type":"request.completed","timestamp":"2026-09-14T00:00:01Z"}\n\n'
                    ),
                )
            )
        )
    )
    with pytest.raises(TargetProtocolError):
        async for _ in regressing.stream_query(
            QueryRequest(request_id="query-3", query="Q", stream=True)
        ):
            pass


def test_http_factory_uses_bearer_token_from_config_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The common factory constructs HTTP adapters without execution branching."""
    monkeypatch.setenv("TARGET_TOKEN", "token-value")
    config = ExperimentTargetConfig(
        adapter="http",
        base_url=HttpUrl("https://target.test"),
        authentication_env="TARGET_TOKEN",
        corpus=CorpusConfig(mode=CorpusMode.EXTERNAL),
    )
    adapter = create_target_adapter(config)
    assert isinstance(adapter, HttpTargetAdapter)
    assert adapter._client.headers["Authorization"] == "Bearer token-value"
