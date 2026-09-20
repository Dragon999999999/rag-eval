"""Normalize raw target responses into canonical TargetObservation.

This module handles the transformation:

```text
QueryResponse | RetrieveResponse
    → TargetObservation
```

Preserving all target-provided information while adding evaluator-side
timing and artifact references.
"""

import uuid
from datetime import UTC, datetime

from rag_eval.models import (
    Answer,
    QueryResponse,
    RetrieveResponse,
    TargetObservation,
    Trace,
    Usage,
)
from rag_eval.models.common import ArtifactRef
from rag_eval.models.retrieval import RetrievalResult
from rag_eval.models.target import Configuration

from .timing import ClientTiming


class ObservationNormalizer:
    """Normalize raw target responses into immutable observations."""

    def normalize(
        self,
        response: QueryResponse | RetrieveResponse,
        case_id: str,
        request_id: str,
        timing: ClientTiming,
        raw_response_artifact: ArtifactRef,
    ) -> TargetObservation:
        """Normalize a successful target response.

        Args:
            response: Raw target response (QueryResponse or RetrieveResponse).
            case_id: Benchmark case identifier.
            request_id: Request identity from request construction.
            timing: Client-side timing captured during execution.
            raw_response_artifact: Reference to persisted raw response.

        Returns:
            Canonical TargetObservation for persistence.

        Note:
            Does not fabricate fields the target did not return.
            Optional fields remain None/empty if unsupported.
        """
        observation_id = str(uuid.uuid4())

        # Extract common fields
        answer = self._extract_answer(response)
        retrieval = self._extract_retrieval(response)
        confidence = self._extract_confidence(response)
        trace = self._extract_trace(response)
        usage = self._extract_usage(response)
        configuration = self._extract_configuration(response)
        warnings = getattr(response, "warnings", [])
        errors = getattr(response, "errors", [])

        # Add timing metadata
        metadata = {
            "client_timing": {
                "started_at": (
                    timing.started_at.isoformat() if timing.started_at else None
                ),
                "finished_at": (
                    timing.finished_at.isoformat() if timing.finished_at else None
                ),
                "duration_ms": timing.duration_ms,
            },
        }

        return TargetObservation(
            observation_id=observation_id,
            case_id=case_id,
            request_id=request_id,
            answer=answer,
            retrieval=retrieval,
            confidence=confidence,
            trace=trace,
            usage=usage,
            warnings=warnings,
            errors=errors,
            configuration=configuration or Configuration(),
            raw_request_artifact=None,  # Already linked via Attempt
            raw_response_artifact=raw_response_artifact,
            normalization_version="1.0",
            created_at=datetime.now(UTC),
            metadata=metadata,
        )

    def _extract_answer(
        self, response: QueryResponse | RetrieveResponse
    ) -> Answer | None:
        """Extract answer from response if available."""
        if isinstance(response, QueryResponse):
            return response.answer
        return None

    def _extract_retrieval(
        self, response: QueryResponse | RetrieveResponse
    ) -> RetrievalResult | None:
        """Extract retrieval stages from response."""
        return response.retrieval

    def _extract_confidence(self, response: QueryResponse | RetrieveResponse) -> list:
        """Extract confidence signals from response."""
        if isinstance(response, QueryResponse):
            return response.confidence
        return []

    def _extract_trace(
        self, response: QueryResponse | RetrieveResponse
    ) -> Trace | None:
        """Extract execution trace from response."""
        if isinstance(response, QueryResponse):
            return response.trace
        if isinstance(response, RetrieveResponse):
            return response.trace
        return None

    def _extract_usage(
        self, response: QueryResponse | RetrieveResponse
    ) -> Usage | None:
        """Extract usage information from response."""
        if isinstance(response, QueryResponse):
            return response.usage
        if isinstance(response, RetrieveResponse):
            return response.usage
        return None

    def _extract_configuration(
        self, response: QueryResponse | RetrieveResponse
    ) -> Configuration | None:
        """Extract requested/effective configuration from response."""
        if isinstance(response, QueryResponse):
            return response.configuration
        if isinstance(response, RetrieveResponse):
            return response.configuration
        return None
