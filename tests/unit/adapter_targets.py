"""Deterministic Python targets imported by adapter unit tests."""

from datetime import UTC, datetime


class RetrievalTarget:
    """Target exposing query, retrieval, streaming, and recovery operations."""

    async def capabilities(self) -> dict[str, object]:
        """Advertise the operations exercised by the adapter tests."""
        return {
            "target": {"name": "test-target", "version": "1"},
            "query": True,
            "retrieval": True,
            "streaming": True,
            "request_recovery": True,
        }

    async def health(self) -> dict[str, object]:
        """Return a ready health response."""
        return {"status": "READY", "target": {"name": "test-target"}}

    async def retrieve(self, request: object) -> dict[str, object]:
        """Return two distinct retrieval stages."""
        request_id = request.request_id
        item = {"retrieval_id": "item-1", "rank": 1, "text": "Evidence"}
        return {
            "request_id": request_id,
            "retrieval": {
                "stages": [
                    {
                        "stage_id": "candidates",
                        "type": "CANDIDATE_RETRIEVAL",
                        "items": [item],
                    },
                    {
                        "stage_id": "final",
                        "type": "FINAL_CONTEXT",
                        "items": [item],
                    },
                ]
            },
        }

    async def query(self, request: object) -> dict[str, object]:
        """Return a query response without unadvertised optional observations."""
        return {
            "request_id": request.request_id,
            "answer": {"text": "A canonical answer."},
        }

    async def stream_query(self, request: object):
        """Yield target-produced events in their original sequence."""
        request_id = request.request_id
        for sequence, event_type in enumerate(("delta", "completed")):
            yield {
                "event_id": f"event-{sequence}",
                "request_id": request_id,
                "sequence": sequence,
                "type": event_type,
                "timestamp": datetime(2026, 9, 14, tzinfo=UTC),
            }

    async def recover_request(self, request_id: str) -> dict[str, object]:
        """Return a completed recovered query result."""
        return {
            "request_id": request_id,
            "status": "COMPLETED",
            "response": {
                "request_id": request_id,
                "answer": {"text": "Recovered answer."},
            },
        }


class QueryOnlyTarget:
    """Target deliberately advertising only the minimum query capability."""

    async def capabilities(self) -> dict[str, object]:
        """Advertise query only."""
        return {"target": {"name": "query-only"}, "query": True}

    async def health(self) -> dict[str, object]:
        """Return a ready health response."""
        return {"status": "READY", "target": {"name": "query-only"}}

    async def query(self, request: object) -> dict[str, object]:
        """Return the smallest valid query result."""
        return {
            "request_id": request.request_id,
            "answer": {"text": "Query-only answer."},
        }


class FullCapabilityTarget(RetrievalTarget):
    """Target exercising corpus and ingestion operations without fake defaults."""

    async def capabilities(self) -> dict[str, object]:
        """Advertise the concrete ingestion operations implemented below."""
        capabilities = await super().capabilities()
        capabilities["document_ingestion"] = True
        capabilities["chunk_ingestion"] = True
        return capabilities

    async def create_corpus(self, request: object) -> dict[str, object]:
        """Create an empty corpus with its evaluator-provided configuration."""
        return {"corpus_id": "corpus-1", "status": "EMPTY"}

    async def get_corpus(self, corpus_id: str) -> dict[str, object]:
        """Return the corpus state."""
        return {"corpus_id": corpus_id, "status": "READY"}

    async def delete_corpus(self, corpus_id: str) -> None:
        """Accept deletion of the test corpus."""

    async def upload_document(
        self, corpus_id: str, document: object
    ) -> dict[str, object]:
        """Return a canonical asynchronous document-ingestion operation."""
        return {
            "operation_id": "document-op",
            "kind": "DOCUMENT_INGESTION",
            "status": "SUCCEEDED",
        }

    async def upload_chunks(self, corpus_id: str, chunks: object) -> dict[str, object]:
        """Consume the provided async iterator only within the target boundary."""
        chunk_count = 0
        async for _ in chunks:
            chunk_count += 1
        return {
            "operation_id": "chunk-op",
            "kind": "CHUNK_INGESTION",
            "status": "SUCCEEDED",
            "result": {"chunk_count": chunk_count},
        }

    async def get_operation(self, operation_id: str) -> dict[str, object]:
        """Return terminal operation state."""
        return {
            "operation_id": operation_id,
            "kind": "INGESTION",
            "status": "SUCCEEDED",
        }


class MalformedQueryTarget(QueryOnlyTarget):
    """Target whose query output does not satisfy the canonical model."""

    async def query(self, request: object) -> dict[str, object]:
        """Return invalid data for normalization coverage."""
        return {"answer": {"text": "Missing request identity"}}


class ExplodingQueryTarget(QueryOnlyTarget):
    """Target that raises an arbitrary implementation exception."""

    async def query(self, request: object) -> dict[str, object]:
        """Raise a target implementation failure."""
        raise RuntimeError("target exploded")
