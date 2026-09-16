"""Fixtures for Stage 14 E2E tests."""

import pytest
from fastapi.testclient import TestClient

from tests.mock_target import FailureScenario, state
from tests.mock_target.server import app


@pytest.fixture
def mock_target_client() -> TestClient:
    """Create test client for mock target."""
    # Reset state before each test
    state.corpora.clear()
    state.operations.clear()
    state.requests.clear()
    state.idempotency_store.clear()
    state.failure_counts.clear()
    state.query_count = 0
    state.retrieve_count = 0
    state.failure_scenario = FailureScenario.NONE

    return TestClient(app)
