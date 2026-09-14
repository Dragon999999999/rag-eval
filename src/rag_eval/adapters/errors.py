"""Normalized failures raised at the evaluated-target boundary.

The adapter layer converts target and protocol failures into a small exception
hierarchy.  Callers can retain the accompanying canonical ``ErrorRecord``
without depending on a transport or target implementation.
"""

from uuid import uuid4

from rag_eval.models import ErrorCategory, ErrorRecord


class TargetAdapterError(Exception):
    """A normalized failure while invoking or normalizing a target operation."""

    def __init__(
        self,
        message: str,
        *,
        category: ErrorCategory = ErrorCategory.INTERNAL,
        code: str = "TARGET_ADAPTER_ERROR",
        stage: str | None = None,
        details: dict[str, object] | None = None,
        retryable: bool = False,
        retry_after_ms: int | None = None,
        http_status: int | None = None,
        provider: dict[str, object] | None = None,
    ) -> None:
        """Create an error with a serializable canonical representation."""
        super().__init__(message)
        self.record = ErrorRecord(
            error_id=str(uuid4()),
            category=category,
            code=code,
            message=message,
            stage=stage,
            retryable=retryable,
            retry_after_ms=retry_after_ms,
            http_status=http_status,
            provider=provider or {},
            details=details or {},
        )

    def to_error_record(self) -> ErrorRecord:
        """Return the canonical record describing this adapter failure."""
        return self.record


class UnsupportedCapabilityError(TargetAdapterError):
    """Raised when a target has not advertised an attempted operation."""

    def __init__(self, capability: str, operation: str) -> None:
        """Create the canonical unsupported-capability failure."""
        super().__init__(
            f"Target does not advertise capability '{capability}' required for "
            f"'{operation}'.",
            category=ErrorCategory.UNSUPPORTED_CAPABILITY,
            code="UNSUPPORTED_CAPABILITY",
            stage=operation,
            details={"capability": capability, "operation": operation},
        )


class TargetProtocolError(TargetAdapterError):
    """Raised when a target violates the canonical Python protocol."""

    def __init__(
        self,
        message: str,
        *,
        operation: str,
        details: dict[str, object] | None = None,
    ) -> None:
        """Create a normalized invalid-response protocol failure."""
        super().__init__(
            message,
            category=ErrorCategory.INVALID_RESPONSE,
            code="TARGET_PROTOCOL_ERROR",
            stage=operation,
            details=details,
        )


class TargetUnavailableError(TargetAdapterError):
    """Raised when a target cannot be loaded or invoked."""

    def __init__(self, message: str, *, operation: str | None = None) -> None:
        """Create a normalized target-availability failure."""
        super().__init__(
            message,
            category=ErrorCategory.CONNECTION,
            code="TARGET_UNAVAILABLE",
            stage=operation,
        )
