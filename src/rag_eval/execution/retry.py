"""Central retry policy for resilient benchmark execution.

This module implements retry classification and backoff decisions in one
location. Adapters normalize errors; execution decides whether to retry.

Retry is NOT implemented inside adapters to avoid duplicated logic.
"""

import random
from dataclasses import dataclass

from rag_eval.config import RetryConfig
from rag_eval.models import ErrorCategory, ErrorRecord


@dataclass(frozen=True, slots=True)
class RetryDecision:
    """Outcome of retry policy evaluation for one failed attempt."""

    should_retry: bool
    reason: str
    delay_seconds: float
    next_attempt_number: int
    error_record: ErrorRecord


class RetryPolicy:
    """Central retry policy for all target execution failures.

    This policy is applied uniformly across:
    - Normal execution
    - Resume execution
    - Recovery scenarios

    It does not perform retries itself; it only decides whether retry is
    appropriate and calculates backoff delays.
    """

    def __init__(self, config: RetryConfig) -> None:
        """Initialize retry policy with validated configuration.

        Args:
            config: Retry configuration from experiment YAML.
        """
        self._config = config

    def evaluate(
        self,
        error: ErrorRecord,
        current_attempt_number: int,
    ) -> RetryDecision:
        """Evaluate whether a failed attempt should be retried.

        Args:
            error: Normalized error record from failed attempt.
            current_attempt_number: The attempt number that just failed (1-indexed).

        Returns:
            Retry decision with delay and reason.
        """
        # Check if max attempts exceeded
        if current_attempt_number >= self._config.max_attempts:
            return RetryDecision(
                should_retry=False,
                reason=f"Max attempts ({self._config.max_attempts}) reached",
                delay_seconds=0.0,
                next_attempt_number=current_attempt_number + 1,
                error_record=error,
            )

        # Check explicit retryable flag first
        if error.retryable:
            delay = self._calculate_delay(current_attempt_number, error.retry_after_ms)
            return RetryDecision(
                should_retry=True,
                reason=f"Explicitly retryable: {error.category.value}",
                delay_seconds=delay,
                next_attempt_number=current_attempt_number + 1,
                error_record=error,
            )

        # Check HTTP status codes
        if error.http_status is not None:
            if error.http_status in self._config.retryable_http_statuses:
                delay = self._calculate_delay(current_attempt_number)
                return RetryDecision(
                    should_retry=True,
                    reason=f"Retryable HTTP status: {error.http_status}",
                    delay_seconds=delay,
                    next_attempt_number=current_attempt_number + 1,
                    error_record=error,
                )
            else:
                # Non-retryable HTTP status (4xx except 429, etc.)
                return RetryDecision(
                    should_retry=False,
                    reason=f"Non-retryable HTTP status: {error.http_status}",
                    delay_seconds=0.0,
                    next_attempt_number=current_attempt_number + 1,
                    error_record=error,
                )

        # Check error category
        if self._is_retryable_category(error.category):
            delay = self._calculate_delay(current_attempt_number)
            return RetryDecision(
                should_retry=True,
                reason=f"Retryable error category: {error.category.value}",
                delay_seconds=delay,
                next_attempt_number=current_attempt_number + 1,
                error_record=error,
            )

        # Default: do not retry
        return RetryDecision(
            should_retry=False,
            reason=f"Non-retryable error: {error.category.value} - {error.code}",
            delay_seconds=0.0,
            next_attempt_number=current_attempt_number + 1,
            error_record=error,
        )

    def _is_retryable_category(self, category: ErrorCategory) -> bool:
        """Check if an error category is retryable by policy."""
        # Explicitly configured categories
        if category in self._config.retryable_categories:
            return True

        # Default retryable categories (cannot be overridden to non-retryable)
        default_retryable = {
            ErrorCategory.NETWORK,
            ErrorCategory.CONNECTION,
            ErrorCategory.TIMEOUT,
            ErrorCategory.RATE_LIMIT,
            ErrorCategory.RESOURCE_EXHAUSTED,
        }

        return category in default_retryable

    def _calculate_delay(
        self, attempt_number: int, retry_after_ms: int | None = None
    ) -> float:
        """Calculate backoff delay for next retry attempt.

        Args:
            attempt_number: The attempt number that just failed.
            retry_after_ms: Optional Retry-After from server (milliseconds).

        Returns:
            Delay in seconds.
        """
        # Honor Retry-After header if present and larger than computed delay
        if retry_after_ms is not None and retry_after_ms > 0:
            retry_after_seconds = retry_after_ms / 1000.0
            # Use Retry-After but cap at maximum delay
            return min(retry_after_seconds, self._config.maximum_delay)

        # Calculate exponential backoff with jitter
        if self._config.strategy == "exponential_jitter":
            # Base delay * 2^(attempt-1)
            base_delay = self._config.initial_delay * (2 ** (attempt_number - 1))
            # Cap at maximum
            capped_delay = min(base_delay, self._config.maximum_delay)
            # Add jitter (±25%)
            jitter_range = capped_delay * 0.25
            delay = capped_delay + random.uniform(-jitter_range, jitter_range)
            return max(0.0, delay)

        # Linear backoff fallback
        elif self._config.strategy == "linear":
            base_delay = self._config.initial_delay * attempt_number
            return min(base_delay, self._config.maximum_delay)

        # Fixed delay fallback
        else:
            return self._config.initial_delay

    def get_retryable_http_statuses(self) -> list[int]:
        """Return configured retryable HTTP status codes."""
        return list(self._config.retryable_http_statuses)
