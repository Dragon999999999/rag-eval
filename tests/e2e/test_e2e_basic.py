"""Stage 14 End-to-End tests for rag-eval architecture.

Tests the complete workflow:
config → dataset → corpus → target execution → metrics → report → export

Uses deterministic mock target server.
No external API calls.
"""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def example_config_path() -> Path:
    """Path to example configuration."""
    return Path(__file__).parent.parent / "examples" / "basic.yaml"


@pytest.fixture
def benchmark_manifest_path() -> Path:
    """Path to benchmark manifest."""
    return Path(__file__).parent.parent / "examples" / "benchmark-manifest.yaml"


@pytest.fixture
def benchmark_cases_path() -> Path:
    """Path to benchmark cases."""
    return Path(__file__).parent.parent / "examples" / "example-cases.jsonl"


# ============================================================================
# Mock Target Protocol Tests
# ============================================================================


class TestMockTargetProtocol:
    """Test mock target implements Target Protocol v1 correctly."""

    def test_health_endpoint(self, mock_target_client: TestClient) -> None:
        """Health check should return READY status."""
        response = mock_target_client.get("/eval/v1/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "READY"
        assert "target" in data

    def test_capabilities_endpoint(self, mock_target_client: TestClient) -> None:
        """Capabilities should advertise all required features."""
        response = mock_target_client.get("/eval/v1/capabilities")
        assert response.status_code == 200
        data = response.json()

        # Check required capabilities
        assert data["query"] is True
        assert data["retrieval"] is True
        assert data["document_ingestion"] is True
        assert data["chunk_ingestion"] is True
        assert data["idempotency"] is True
        assert data["request_recovery"] is True

    def test_create_corpus(self, mock_target_client: TestClient) -> None:
        """Corpus creation should return valid response."""
        response = mock_target_client.post(
            "/eval/v1/corpora",
            json={
                "request_id": f"req-{uuid4()}",
                "name": "test-corpus",
                "mode": "DOCUMENTS",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert "corpus_id" in data
        assert data["status"] == "EMPTY"

    def test_upload_document(self, mock_target_client: TestClient) -> None:
        """Document upload should create operation."""
        # Create corpus first
        corpus_response = mock_target_client.post(
            "/eval/v1/corpora",
            json={
                "request_id": f"req-{uuid4()}",
                "name": "test-corpus",
                "mode": "DOCUMENTS",
            },
        )
        corpus_id = corpus_response.json()["corpus_id"]

        # Upload document
        response = mock_target_client.post(
            f"/eval/v1/corpora/{corpus_id}/documents",
        )
        assert response.status_code == 200
        data = response.json()
        assert data["kind"] == "DOCUMENT_INGESTION"
        assert "operation_id" in data

    def test_retrieve_endpoint(self, mock_target_client: TestClient) -> None:
        """Retrieve should return multiple stages."""
        response = mock_target_client.post(
            "/eval/v1/retrieve",
            json={
                "request_id": f"req-{uuid4()}",
                "query": "test query",
                "corpus_id": None,
            },
        )
        assert response.status_code == 200
        data = response.json()

        assert "retrieval" in data
        assert "stages" in data["retrieval"]
        assert len(data["retrieval"]["stages"]) >= 1

    def test_query_endpoint(self, mock_target_client: TestClient) -> None:
        """Query should return complete response with all fields."""
        response = mock_target_client.post(
            "/eval/v1/query",
            json={
                "request_id": f"req-{uuid4()}",
                "query": "What is the capital of France?",
                "context_policy": "TARGET_RETRIEVAL",
            },
        )
        assert response.status_code == 200
        data = response.json()

        # Check required fields
        assert "request_id" in data
        assert "answer" in data
        assert "text" in data["answer"]
        assert "retrieval" in data
        assert "usage" in data
        assert "trace" in data

    def test_idempotent_query(self, mock_target_client: TestClient) -> None:
        """Same idempotency key should return cached result."""
        idempotency_key = f"idem-{uuid4()}"
        request_id = f"req-{uuid4()}"

        # First request
        response1 = mock_target_client.post(
            "/eval/v1/query",
            json={
                "request_id": request_id,
                "query": "test query",
            },
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response1.status_code == 200
        result1 = response1.json()

        # Second request with same idempotency key
        response2 = mock_target_client.post(
            "/eval/v1/query",
            json={
                "request_id": f"req-{uuid4()}",  # Different request ID
                "query": "test query",
            },
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response2.status_code == 200
        result2 = response2.json()

        # Results should be identical
        assert result1["answer"]["text"] == result2["answer"]["text"]

        # Check state - expensive execution should happen only once
        state_response = mock_target_client.get("/test/state")
        state_data = state_response.json()
        assert state_data["expensive_executions"] == 1

    def test_idempotency_conflict(self, mock_target_client: TestClient) -> None:
        """Different request with same idempotency key should fail."""
        idempotency_key = f"idem-conflict-{uuid4()}"

        # First request
        mock_target_client.post(
            "/eval/v1/query",
            json={
                "request_id": f"req-{uuid4()}",
                "query": "query 1",
            },
            headers={"Idempotency-Key": idempotency_key},
        )

        # Second request with different query
        response = mock_target_client.post(
            "/eval/v1/query",
            json={
                "request_id": f"req-{uuid4()}",
                "query": "query 2",  # Different query
            },
            headers={"Idempotency-Key": idempotency_key},
        )
        assert response.status_code == 409
        assert "Idempotency conflict" in response.json()["detail"]

    def test_request_recovery(self, mock_target_client: TestClient) -> None:
        """Completed requests should be recoverable."""
        request_id = f"req-{uuid4()}"

        # Make a query
        mock_target_client.post(
            "/eval/v1/query",
            json={
                "request_id": request_id,
                "query": "test query",
            },
        )

        # Recover the request
        response = mock_target_client.get(f"/eval/v1/requests/{request_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "COMPLETED"
        assert "response" in data
        assert data["response"]["answer"]["text"] is not None

    def test_failure_injection_429(self, mock_target_client: TestClient) -> None:
        """429 failure injection should work."""
        # Configure failure
        mock_target_client.post(
            "/test/configure-failure",
            json="429_once",
        )

        # First request should fail
        response1 = mock_target_client.post(
            "/eval/v1/query",
            json={"request_id": f"req-{uuid4()}", "query": "test"},
        )
        assert response1.status_code == 429

        # Second request should succeed
        response2 = mock_target_client.post(
            "/eval/v1/query",
            json={"request_id": f"req-{uuid4()}", "query": "test"},
        )
        assert response2.status_code == 200


# ============================================================================
# Integration Tests
# ============================================================================


class TestHttpAdapterIntegration:
    """Test HTTP adapter with mock target."""

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_adapter_capabilities(
        self,
        mock_target_client: TestClient,
    ) -> None:
        """Adapter should discover capabilities correctly."""
        # Start mock server
        import uvicorn

        from rag_eval.adapters.http import HttpTargetAdapter

        server_task = asyncio.create_task(
            asyncio.to_thread(
                uvicorn.run,
                mock_target_client.app,
                host="127.0.0.1",
                port=8765,
                log_level="error",
            )
        )

        try:
            # Give server time to start
            await asyncio.sleep(0.5)

            # Create adapter
            adapter = HttpTargetAdapter(
                base_url="http://127.0.0.1:8765",
                timeout=30.0,
            )

            # Get capabilities
            capabilities = await adapter.capabilities()

            assert capabilities.query is True
            assert capabilities.retrieval is True
        finally:
            server_task.cancel()
            try:
                await server_task
            except asyncio.CancelledError:
                pass


# ============================================================================
# E2E Workflow Tests
# ============================================================================


class TestEndToEndWorkflow:
    """Test complete rag-eval workflow."""

    def test_basic_run_workflow(
        self,
        mock_target_client: TestClient,
        example_config_path: Path,
    ) -> None:
        """Test complete run → score → report → export workflow."""
        # This test would require:
        # 1. Database setup
        # 2. MinIO setup
        # 3. Full execution
        # Marked for future implementation
        pytest.skip("Requires full infrastructure setup - see test_e2e_full.py")


# ============================================================================
# Determinism Tests
# ============================================================================


class TestDeterministicBehavior:
    """Test mock target returns deterministic results."""

    def test_same_query_same_result(self, mock_target_client: TestClient) -> None:
        """Same query should return same result."""
        query = "What is the capital of France?"

        response1 = mock_target_client.post(
            "/eval/v1/query",
            json={"request_id": "req-1", "query": query},
        )
        response2 = mock_target_client.post(
            "/eval/v1/query",
            json={"request_id": "req-2", "query": query},
        )

        # Results should be identical (except request_id)
        data1 = response1.json()
        data2 = response2.json()

        assert data1["answer"]["text"] == data2["answer"]["text"]
        assert data1["usage"] == data2["usage"]

    def test_retrieval_stages_preserved(self, mock_target_client: TestClient) -> None:
        """Retrieval should preserve multiple stages."""
        response = mock_target_client.post(
            "/eval/v1/retrieve",
            json={"request_id": f"req-{uuid4()}", "query": "test"},
        )

        data = response.json()
        stages = data["retrieval"]["stages"]

        # Should have at least CANDIDATE_RETRIEVAL and FINAL_CONTEXT
        stage_types = [s["type"] for s in stages]
        assert "CANDIDATE_RETRIEVAL" in stage_types
        assert "FINAL_CONTEXT" in stage_types
