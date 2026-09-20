"""Unit tests for the transport-independent Python target adapter."""

import importlib

import pytest

from rag_eval.adapters import (
    DocumentUpload,
    PythonTargetAdapter,
    TargetAdapter,
    TargetAdapterError,
    TargetProtocolError,
    UnsupportedCapabilityError,
    create_target_adapter,
    load_python_target,
)
from rag_eval.config.models import CorpusConfig, TargetConfig
from rag_eval.models import (
    Chunk,
    CorpusMode,
    CreateCorpusRequest,
    Document,
    QueryRequest,
    RetrieveRequest,
)


def _adapter(target_name: str) -> PythonTargetAdapter:
    """Load a deterministic test target through the public loader."""
    target_module = importlib.import_module("tests.unit.adapter_targets")
    return PythonTargetAdapter(getattr(target_module, target_name)())


@pytest.mark.anyio
async def test_loader_factory_health_and_query_normalization() -> None:
    """An explicit import path constructs the Python adapter and normalizes I/O."""
    target = load_python_target("tests.unit.adapter_targets:RetrievalTarget")
    config = TargetConfig(
        adapter="python",
        python_target="tests.unit.adapter_targets:RetrievalTarget",
        corpus=CorpusConfig(mode=CorpusMode.EXTERNAL),
    )
    adapter = create_target_adapter(config)

    assert isinstance(adapter, PythonTargetAdapter)
    assert isinstance(adapter, TargetAdapter)
    assert (await adapter.capabilities()).retrieval
    assert (await adapter.health()).status == "READY"
    response = await adapter.query(QueryRequest(request_id="query-1", query="Question"))
    assert response.answer is not None and response.answer.text == "A canonical answer."
    assert target is not None


@pytest.mark.anyio
async def test_retrieve_preserves_multiple_stages_and_optional_fields() -> None:
    """Retrieval stage structure survives dictionary normalization unchanged."""
    adapter = _adapter("RetrievalTarget")
    response = await adapter.retrieve(
        RetrieveRequest(request_id="retrieve-1", query="Q")
    )

    assert response.retrieval is not None
    assert [stage.stage_id for stage in response.retrieval.stages] == [
        "candidates",
        "final",
    ]
    query = await adapter.query(QueryRequest(request_id="query-2", query="Q"))
    assert query.retrieval is None
    assert query.confidence == []
    assert query.trace is None
    assert query.usage is None


@pytest.mark.anyio
async def test_query_only_target_reports_unsupported_retrieval() -> None:
    """Absent capabilities fail before calling a missing target operation."""
    adapter = _adapter("QueryOnlyTarget")
    response = await adapter.query(QueryRequest(request_id="query-3", query="Q"))

    assert response.answer is not None
    with pytest.raises(UnsupportedCapabilityError) as error:
        await adapter.retrieve(RetrieveRequest(request_id="retrieve-2", query="Q"))
    assert error.value.to_error_record().category == "UNSUPPORTED_CAPABILITY"


@pytest.mark.anyio
async def test_malformed_and_exceptional_target_outputs_are_normalized() -> None:
    """Target validation and runtime errors never leak implementation exceptions."""
    malformed = _adapter("MalformedQueryTarget")
    with pytest.raises(TargetProtocolError) as malformed_error:
        await malformed.query(QueryRequest(request_id="query-4", query="Q"))
    assert malformed_error.value.to_error_record().category == "INVALID_RESPONSE"

    exploding = _adapter("ExplodingQueryTarget")
    with pytest.raises(TargetAdapterError) as target_error:
        await exploding.query(QueryRequest(request_id="query-5", query="Q"))
    assert target_error.value.to_error_record().code == "TARGET_OPERATION_ERROR"


@pytest.mark.anyio
async def test_streaming_and_request_recovery_preserve_target_data() -> None:
    """Streaming event order and recovery responses remain canonical observations."""
    adapter = _adapter("RetrievalTarget")
    events = [
        event
        async for event in adapter.stream_query(
            QueryRequest(request_id="query-6", query="Q", stream=True)
        )
    ]
    recovered = await adapter.recover_request("query-6")

    assert [event.sequence for event in events] == [0, 1]
    assert [event.type for event in events] == ["delta", "completed"]
    assert recovered.response is not None
    assert recovered.response.answer is not None
    assert recovered.response.answer.text == "Recovered answer."


@pytest.mark.anyio
async def test_full_capability_target_supports_corpus_and_streamed_ingestion() -> None:
    """Corpus operations pass canonical identities and chunk iterators through."""
    adapter = _adapter("FullCapabilityTarget")
    corpus = await adapter.create_corpus(
        CreateCorpusRequest(request_id="corpus-request", name="corpus", mode=CorpusMode.CHUNKS)
    )
    assert corpus.corpus_id == "corpus-1"
    assert (await adapter.get_corpus("corpus-1")).status == "READY"
    document_operation = await adapter.upload_document(
        "corpus-1",
        DocumentUpload(document=Document(document_id="document-1"), content=b"source"),
    )

    async def chunks():
        yield Chunk(chunk_id="chunk-1", document_id="document-1", text="One")
        yield Chunk(chunk_id="chunk-2", document_id="document-1", text="Two")

    chunk_operation = await adapter.upload_chunks("corpus-1", chunks())
    await adapter.delete_corpus("corpus-1")

    assert document_operation.status == "SUCCEEDED"
    assert chunk_operation.result == {"chunk_count": 2}
    assert (await adapter.get_operation("chunk-op")).operation_id == "chunk-op"


def test_loader_rejects_non_explicit_or_incompatible_targets() -> None:
    """Only explicit import paths with core target operations are accepted."""
    with pytest.raises(TargetAdapterError):
        load_python_target("tests.unit.adapter_targets.RetrievalTarget")
    with pytest.raises(TargetAdapterError):
        load_python_target("rag_eval.adapters.errors:TargetAdapterError")
