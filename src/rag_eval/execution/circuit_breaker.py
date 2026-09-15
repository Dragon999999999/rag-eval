"""Simple circuit breaker for target-level failure coordination.

Prevents retry storms by coordinating concurrent workers when a target
shows repeated transient failures.

States:
- CLOSED: Normal operation
- OPEN: Blocking new expensive requests
- HALF_OPEN: Testing with limited probe requests
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum, auto

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker lifecycle states."""

    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker behavior."""

    # Number of consecutive failures before opening circuit
    failure_threshold: int = 5
    # Time to wait in OPEN state before trying half-open
    cooldown_seconds: float = 30.0
    # Number of successful probes needed to close circuit
    success_threshold: int = 2
    # Timeout for probe requests in half-open state
    probe_timeout_seconds: float = 10.0


@dataclass
class CircuitBreaker:
    """Circuit breaker for one target endpoint.

    Prevents hammering an unhealthy target with concurrent retry attempts.
    All workers share the same circuit state.
    """

    config: CircuitBreakerConfig = field(default_factory=CircuitBreakerConfig)
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: datetime | None = field(default=None, init=False)
    _opened_at: datetime | None = field(default=None, init=False)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Return current circuit state."""
        return self._state

    @property
    def is_closed(self) -> bool:
        """Check if circuit allows normal requests."""
        return self._state == CircuitState.CLOSED

    @property
    def is_open(self) -> bool:
        """Check if circuit is blocking requests."""
        return self._state == CircuitState.OPEN

    @property
    def is_half_open(self) -> bool:
        """Check if circuit is testing with probe requests."""
        return self._state == CircuitState.HALF_OPEN

    async def can_execute(self) -> bool:
        """Check if a request can proceed without blocking.

        Returns:
            True if request can proceed immediately.
            False if circuit is open and caller should wait/skip.
        """
        async with self._lock:
            if self._state == CircuitState.CLOSED:
                return True

            if self._state == CircuitState.HALF_OPEN:
                # Allow limited probe requests
                return True

            # OPEN state - check if cooldown elapsed
            if self._opened_at is not None:
                elapsed = datetime.now(UTC) - self._opened_at
                if elapsed.total_seconds() >= self.config.cooldown_seconds:
                    # Transition to half-open
                    self._state = CircuitState.HALF_OPEN
                    self._success_count = 0
                    logger.info("Circuit breaker transitioning to HALF_OPEN")
                    return True

            return False

    async def record_success(self) -> None:
        """Record a successful request completion."""
        async with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.config.success_threshold:
                    self._close_circuit()
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    async def record_failure(self) -> None:
        """Record a failed request."""
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = datetime.now(UTC)

            if self._state == CircuitState.HALF_OPEN:
                # Failure during probe - reopen immediately
                self._open_circuit()
                logger.warning(
                    "Circuit breaker reopened after probe failure (failures: %d)",
                    self._failure_count,
                )
            elif self._state == CircuitState.CLOSED:
                if self._failure_count >= self.config.failure_threshold:
                    self._open_circuit()
                    logger.warning(
                        "Circuit breaker opened after %d consecutive failures",
                        self._failure_count,
                    )

    def _open_circuit(self) -> None:
        """Transition to OPEN state."""
        self._state = CircuitState.OPEN
        self._opened_at = datetime.now(UTC)
        self._success_count = 0

    def _close_circuit(self) -> None:
        """Transition to CLOSED state."""
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._opened_at = None
        logger.info("Circuit breaker closed after successful probes")

    async def wait_for_cooldown(self) -> bool:
        """Wait for circuit to transition from OPEN to HALF_OPEN.

        Returns:
            True if cooldown completed successfully.
            False if circuit was already closed or shutdown requested.
        """
        if self._state != CircuitState.OPEN:
            return True

        async with self._lock:
            if self._opened_at is None:
                return True

            elapsed = datetime.now(UTC) - self._opened_at
            remaining = self.config.cooldown_seconds - elapsed.total_seconds()

            if remaining <= 0:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")
                return True

        # Wait outside lock
        await asyncio.sleep(remaining)

        async with self._lock:
            if self._state == CircuitState.OPEN:
                self._state = CircuitState.HALF_OPEN
                self._success_count = 0
                logger.info("Circuit breaker transitioning to HALF_OPEN")

        return True

    def reset(self) -> None:
        """Reset circuit breaker to initial state.

        Use only for testing or explicit operator intervention.
        """
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._opened_at = None
