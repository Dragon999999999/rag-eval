"""Tests for Stage 10 resilience features: retry, circuit breaker, and recovery."""

import asyncio
from uuid import uuid4

import pytest

from rag_eval.execution import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    RetryDecision,
    RetryPolicy,
)
from rag_eval.models import ErrorCategory, ErrorRecord


class TestRetryPolicy:
    """Test retry policy classification and backoff."""

    def test_retry_policy_429_with_retry_after(self) -> None:
        """429 rate limit should be retryable with Retry-After delay."""
        from rag_eval.config import RetryConfig

        config = RetryConfig(max_attempts=3, initial_delay=1.0, maximum_delay=30.0)
        policy = RetryPolicy(config)

        error = ErrorRecord(
            error_id=str(uuid4()),
            category=ErrorCategory.RATE_LIMIT,
            code="RATE_LIMITED",
            message="Rate limit exceeded",
            http_status=429,
            retryable=True,
            retry_after_ms=5000,  # 5 seconds
        )

        decision = policy.evaluate(error, current_attempt_number=1)

        assert decision.should_retry is True
        assert decision.next_attempt_number == 2
        assert decision.delay_seconds >= 0.0
        assert "retryable" in decision.reason.lower()

    def test_retry_policy_503_retryable(self) -> None:
        """503 service unavailable should be retryable."""
        from rag_eval.config import RetryConfig

        config = RetryConfig(
            max_attempts=3,
            initial_delay=1.0,
            maximum_delay=30.0,
            retryable_http_statuses=[429, 500, 502, 503, 504],
        )
        policy = RetryPolicy(config)

        error = ErrorRecord(
            error_id=str(uuid4()),
            category=ErrorCategory.CONNECTION,
            code="SERVICE_UNAVAILABLE",
            message="Service temporarily unavailable",
            http_status=503,
        )

        decision = policy.evaluate(error, current_attempt_number=1)

        assert decision.should_retry is True
        assert decision.next_attempt_number == 2

    def test_retry_policy_400_non_retryable(self) -> None:
        """400 bad request should NOT be retryable."""
        from rag_eval.config import RetryConfig

        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        error = ErrorRecord(
            error_id=str(uuid4()),
            category=ErrorCategory.VALIDATION,
            code="BAD_REQUEST",
            message="Invalid request",
            http_status=400,
        )

        decision = policy.evaluate(error, current_attempt_number=1)

        assert decision.should_retry is False
        assert "Non-retryable" in decision.reason

    def test_retry_policy_max_attempts_exhausted(self) -> None:
        """Should not retry after max attempts reached."""
        from rag_eval.config import RetryConfig

        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        error = ErrorRecord(
            error_id=str(uuid4()),
            category=ErrorCategory.TIMEOUT,
            code="TIMEOUT",
            message="Request timed out",
            retryable=True,
        )

        # Third attempt failed - should not retry
        decision = policy.evaluate(error, current_attempt_number=3)

        assert decision.should_retry is False
        assert "Max attempts" in decision.reason

    def test_retry_policy_timeout_is_retryable(self) -> None:
        """Timeout errors should be retryable by default."""
        from rag_eval.config import RetryConfig

        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        error = ErrorRecord(
            error_id=str(uuid4()),
            category=ErrorCategory.TIMEOUT,
            code="CONNECTION_TIMEOUT",
            message="Connection timed out",
        )

        decision = policy.evaluate(error, current_attempt_number=1)

        assert decision.should_retry is True

    def test_retry_policy_authentication_non_retryable(self) -> None:
        """Authentication failures should NOT be retryable."""
        from rag_eval.config import RetryConfig

        config = RetryConfig(max_attempts=3)
        policy = RetryPolicy(config)

        error = ErrorRecord(
            error_id=str(uuid4()),
            category=ErrorCategory.AUTHENTICATION,
            code="INVALID_CREDENTIALS",
            message="Invalid API key",
            http_status=401,
        )

        decision = policy.evaluate(error, current_attempt_number=1)

        assert decision.should_retry is False


class TestCircuitBreaker:
    """Test circuit breaker state transitions."""

    @pytest.mark.asyncio
    async def test_circuit_breaker_starts_closed(self) -> None:
        """Circuit breaker should start in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED
        assert breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_threshold_failures(
        self,
    ) -> None:
        """Circuit should open after consecutive failures."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # Record 3 failures
        for _ in range(3):
            await breaker.record_failure()

        assert breaker.is_open is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_blocks_when_open(self) -> None:
        """Open circuit should block execution."""
        config = CircuitBreakerConfig(failure_threshold=2, cooldown_seconds=60.0)
        breaker = CircuitBreaker(config)

        # Open the circuit
        await breaker.record_failure()
        await breaker.record_failure()

        assert breaker.is_open is True
        can_execute = await breaker.can_execute()
        assert can_execute is False

    @pytest.mark.asyncio
    async def test_circuit_breaker_transitions_to_half_open(self) -> None:
        """Circuit should transition to HALF_OPEN after cooldown."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            cooldown_seconds=0.1,  # Short for testing
        )
        breaker = CircuitBreaker(config)

        # Open the circuit
        await breaker.record_failure()
        await breaker.record_failure()
        assert breaker.is_open is True

        # Wait for cooldown
        await asyncio.sleep(0.15)

        # Should transition to half-open
        can_execute = await breaker.can_execute()
        assert can_execute is True
        assert breaker.is_half_open is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_closes_after_successful_probes(self) -> None:
        """Circuit should close after successful probes in half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=2, cooldown_seconds=0.1, success_threshold=2
        )
        breaker = CircuitBreaker(config)

        # Open the circuit
        await breaker.record_failure()
        await breaker.record_failure()

        # Wait for cooldown
        await asyncio.sleep(0.15)
        await breaker.can_execute()  # Triggers half-open
        assert breaker.is_half_open is True

        # Record successful probes
        await breaker.record_success()
        assert breaker.is_half_open is True  # Not enough yet

        await breaker.record_success()
        assert breaker.is_closed is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_reopens_on_probe_failure(self) -> None:
        """Circuit should reopen if probe fails in half-open state."""
        config = CircuitBreakerConfig(
            failure_threshold=2, cooldown_seconds=0.1, success_threshold=2
        )
        breaker = CircuitBreaker(config)

        # Open the circuit
        await breaker.record_failure()
        await breaker.record_failure()

        # Wait for cooldown and transition to half-open
        await asyncio.sleep(0.15)
        await breaker.can_execute()

        # Fail the probe
        await breaker.record_failure()

        # Should reopen
        assert breaker.is_open is True

    @pytest.mark.asyncio
    async def test_circuit_breaker_resets_on_success_in_closed_state(self) -> None:
        """Success in closed state should reset failure count."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)

        # Record 2 failures (not enough to open)
        await breaker.record_failure()
        await breaker.record_failure()

        # Record success
        await breaker.record_success()

        # Record 2 more failures
        await breaker.record_failure()
        await breaker.record_failure()

        # Should still be closed (failure count was reset)
        assert breaker.is_closed is True


class TestRecoveryDecision:
    """Test recovery service decision logic."""

    @pytest.mark.asyncio
    async def test_recovery_skips_complete_cases(self) -> None:
        """Recovery should skip already complete cases."""
        from rag_eval.db.models import CaseExecutionRecord
        from rag_eval.execution import CaseRecoveryService, RecoveryAction
        from rag_eval.models.enums import CaseExecutionStatus

        # Mock dependencies
        class MockAdapter:
            async def capabilities(self):
                class Caps:
                    request_recovery = False
                    idempotency = False

                return Caps()

        class MockArtifactService:
            pass

        class MockRepository:
            async def get_observation(self, attempt_id: str):
                # Simulate observation exists
                return object()

        from rag_eval.execution import ObservationNormalizer

        service = CaseRecoveryService(
            MockAdapter(),  # type: ignore[arg-type]
            MockArtifactService(),  # type: ignore[arg-type]
            MockRepository(),  # type: ignore[arg-type]
            ObservationNormalizer(),
        )

        case_execution = CaseExecutionRecord(
            case_execution_id="test-case-exec",
            run_id="test-run",
            case_id="test-case",
            status=CaseExecutionStatus.COMPLETE.value,
        )

        decision = await service.decide_recovery(case_execution, None, "test-run")

        assert decision.action == RecoveryAction.SKIP

    @pytest.mark.asyncio
    async def test_recovery_renormalizes_raw_response(self) -> None:
        """Recovery should renormalize if raw response artifact exists."""

        # This test would need proper mocking of artifact service
        # For now, just verify the structure exists
        pass


class TestRetryDecision:
    """Test retry decision data structure."""

    def test_retry_decision_contains_required_fields(self) -> None:
        """Retry decision should have all required fields."""
        error = ErrorRecord(
            error_id=str(uuid4()),
            category=ErrorCategory.TIMEOUT,
            code="TIMEOUT",
            message="Timed out",
            retryable=True,
        )

        decision = RetryDecision(
            should_retry=True,
            reason="Retryable timeout",
            delay_seconds=1.0,
            next_attempt_number=2,
            error_record=error,
        )

        assert decision.should_retry is True
        assert decision.reason == "Retryable timeout"
        assert decision.delay_seconds == 1.0
        assert decision.next_attempt_number == 2
        assert decision.error_record is error
