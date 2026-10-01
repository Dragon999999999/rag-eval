"""Recovery logic for resilient benchmark execution.

Recovery follows a durable-state-first precedence:

1. Reuse an already persisted TargetObservation when discoverable.
2. Renormalize an already persisted raw target response.
3. Recover the original request when the target supports request recovery.
4. Fall back to idempotent replay when it is safe.
5. Execute a new attempt only when the execution/retry coordinator permits it.

The recovery layer never creates attempts and never performs ordinary target
execution. Attempt creation, retry policy, case lifecycle transitions, and
concurrency remain responsibilities of the execution coordinator.

The core invariant is that an expensive target request must never be repeated
when its durable result can be recovered locally.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum, auto
from typing import Any

from rag_eval.adapters import TargetAdapter
from rag_eval.artifacts import ArtifactService
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.test_models import AttemptRecord, CaseExecutionRecord
from rag_eval.db.test_repository import TestRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import (
    ArtifactType,
    QueryRequest,
    QueryResponse,
    RequestRecoveryResult,
    RequestStatus,
    RetrieveRequest,
    RetrieveResponse,
    TargetCapabilities,
    TargetObservation,
)
from rag_eval.models.enums import CaseExecutionStatus

from .observation import ObservationNormalizer
from .timing import ClientTiming

logger = logging.getLogger(__name__)

INTERRUPTED = "INTERRUPTED"


class RecoveryAction(Enum):
    """Action the execution coordinator should take for one case."""

    REUSE_OBSERVATION = auto()
    RENORMALIZE_RAW = auto()
    RECOVER_REQUEST = auto()
    IDEMPOTENT_REPLAY = auto()
    EXECUTE_NEW = auto()
    SKIP = auto()
    MARK_UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """Recovery strategy selected for one logical case execution."""

    action: RecoveryAction
    reason: str
    case_id: str

    observation: TargetObservation | None = None

    # Retained for compatibility with callers that may explicitly construct
    # replay requests. The recovery service itself does not create requests.
    request_to_replay: QueryRequest | RetrieveRequest | None = None

    # Used when request recovery cannot recover the original result.
    fallback_action: RecoveryAction | None = None


class CaseRecoveryService:
    """Determine and execute safe recovery from durable evaluator state.

    Ownership boundaries:

    - TestRepository:
        run/case/attempt lifecycle state
    - TargetRepository:
        normalized TargetObservation persistence
    - PersistenceRepository:
        generic artifact metadata
    - ArtifactService:
        artifact bytes / JSON payloads
    - execution coordinator:
        new attempts, retries, replay, case state transitions

    This service deliberately does not create AttemptRecord objects or send
    ordinary query/retrieve requests.
    """

    def __init__(
        self,
        *,
        adapter: TargetAdapter,
        artifact_service: ArtifactService,
        persistence_repository: PersistenceRepository,
        test_repository: TestRepository,
        target_repository: TargetRepository,
        normalizer: ObservationNormalizer,
        capabilities: TargetCapabilities | None = None,
        staleness_threshold_seconds: float = 300.0,
    ) -> None:
        """Initialize recovery dependencies."""
        if staleness_threshold_seconds <= 0:
            raise ValueError("staleness_threshold_seconds must be greater than zero")

        self._adapter = adapter
        self._artifact_service = artifact_service
        self._persistence_repository = persistence_repository
        self._test_repository = test_repository
        self._target_repository = target_repository
        self._normalizer = normalizer
        self._capabilities = capabilities
        self._staleness_threshold = timedelta(seconds=staleness_threshold_seconds)

    async def decide_recovery(
        self,
        case_execution: CaseExecutionRecord,
        latest_attempt: AttemptRecord | None,
        run_id: str | None = None,
    ) -> RecoveryDecision:
        """Determine the safest recovery action for one case execution.

        The persisted evaluator state is always inspected before any operation
        that could contact the target.

        ``run_id`` is accepted for compatibility with older callers but is not
        required because the CaseExecutionRecord already owns the run identity.
        """
        del run_id

        case_id = case_execution.case_id
        status = case_execution.status

        # ------------------------------------------------------------------
        # Terminal target state
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.COMPLETE.value:
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason=f"Case already {status}",
                case_id=case_id,
            )

        # ------------------------------------------------------------------
        # 1. Durable normalized observation
        # ------------------------------------------------------------------

        if latest_attempt is not None:
            observation = await self._find_observation_for_attempt(latest_attempt)

            if observation is not None:
                return RecoveryDecision(
                    action=RecoveryAction.REUSE_OBSERVATION,
                    reason=(
                        "A durable TargetObservation already exists for the "
                        "latest attempt"
                    ),
                    case_id=case_id,
                    observation=observation,
                )

        # ------------------------------------------------------------------
        # 2. Durable raw response
        # ------------------------------------------------------------------

        if (
            latest_attempt is not None
            and latest_attempt.raw_response_artifact_id is not None
        ):
            observation = await self._try_renormalize(
                artifact_id=latest_attempt.raw_response_artifact_id,
                case_id=case_id,
                request_id=latest_attempt.request_id,
            )

            if observation is not None:
                return RecoveryDecision(
                    action=RecoveryAction.RENORMALIZE_RAW,
                    reason=(
                        "A durable raw target response exists and was "
                        "successfully renormalized"
                    ),
                    case_id=case_id,
                    observation=observation,
                )

        # ------------------------------------------------------------------
        # Fresh case
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.PENDING.value:
            return RecoveryDecision(
                action=RecoveryAction.EXECUTE_NEW,
                reason="Case has not started",
                case_id=case_id,
            )

        # ------------------------------------------------------------------
        # Retry already authorized by coordinator
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.RETRY_PENDING.value:
            return RecoveryDecision(
                action=RecoveryAction.EXECUTE_NEW,
                reason=(
                    "Retry is pending; execution coordinator must enforce "
                    "the configured retry policy before creating the attempt"
                ),
                case_id=case_id,
            )

        # ------------------------------------------------------------------
        # RUNNING but apparently still active
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.RUNNING.value and not self._is_attempt_stale(
            latest_attempt
        ):
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason="RUNNING attempt is not yet considered stale",
                case_id=case_id,
            )

        # ------------------------------------------------------------------
        # Unknown / interrupted / stale target outcome
        # ------------------------------------------------------------------

        recoverable_unknown = (
            status == CaseExecutionStatus.UNKNOWN.value
            or status == INTERRUPTED
            or (
                status == CaseExecutionStatus.RUNNING.value
                and self._is_attempt_stale(latest_attempt)
            )
        )

        if recoverable_unknown:
            if latest_attempt is None:
                return RecoveryDecision(
                    action=RecoveryAction.MARK_UNKNOWN,
                    reason=(
                        "Execution outcome is uncertain but no durable "
                        "attempt record exists"
                    ),
                    case_id=case_id,
                )

            capabilities = await self._get_capabilities()

            if capabilities.request_recovery:
                fallback = (
                    RecoveryAction.IDEMPOTENT_REPLAY
                    if capabilities.idempotency
                    else RecoveryAction.MARK_UNKNOWN
                )

                return RecoveryDecision(
                    action=RecoveryAction.RECOVER_REQUEST,
                    reason=(
                        "Execution outcome is uncertain and the target "
                        "supports request recovery"
                    ),
                    case_id=case_id,
                    fallback_action=fallback,
                )

            if capabilities.idempotency:
                return RecoveryDecision(
                    action=RecoveryAction.IDEMPOTENT_REPLAY,
                    reason=(
                        "Execution outcome is uncertain, request recovery is "
                        "unavailable, and idempotent replay is supported"
                    ),
                    case_id=case_id,
                )

            return RecoveryDecision(
                action=RecoveryAction.MARK_UNKNOWN,
                reason=(
                    "Execution outcome is uncertain and the target exposes "
                    "no safe recovery or idempotency mechanism"
                ),
                case_id=case_id,
            )

        # ------------------------------------------------------------------
        # Permanent failure
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.FAILED.value:
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason="Case failed and no retry is currently scheduled",
                case_id=case_id,
            )

        # ------------------------------------------------------------------
        # Unknown lifecycle state
        # ------------------------------------------------------------------

        return RecoveryDecision(
            action=RecoveryAction.MARK_UNKNOWN,
            reason=f"Unrecognized case execution state: {status}",
            case_id=case_id,
        )

    async def execute_recovery(
        self,
        decision: RecoveryDecision,
        attempt: AttemptRecord | None,
    ) -> TargetObservation | None:
        """Execute recovery actions that can produce an observation.

        This method never creates a new attempt.

        REUSE_OBSERVATION and RENORMALIZE_RAW already carry an observation.

        RECOVER_REQUEST may contact the target's recovery endpoint for an
        already-issued request. It does not issue a new generation request.

        IDEMPOTENT_REPLAY and EXECUTE_NEW remain the responsibility of the
        execution/retry coordinator.
        """
        if decision.action in {
            RecoveryAction.REUSE_OBSERVATION,
            RecoveryAction.RENORMALIZE_RAW,
        }:
            return decision.observation

        if decision.action != RecoveryAction.RECOVER_REQUEST:
            return None

        if attempt is None:
            logger.error("Cannot recover a target request without an AttemptRecord")
            return None

        result = await self._recover_via_request_id(attempt.request_id)

        if result is None:
            return None

        if result.status != RequestStatus.COMPLETED:
            return None

        if result.response is None:
            logger.warning(
                "Target reports request %s as COMPLETED but returned no "
                "recoverable response",
                attempt.request_id,
            )
            return None

        return await self._normalize_recovered_response(
            response=result.response,
            case_id=decision.case_id,
            request_id=attempt.request_id,
        )

    async def _find_observation_for_attempt(
        self,
        attempt: AttemptRecord,
    ) -> TargetObservation | None:
        """Find the durable observation belonging to one attempt."""
        return await self._target_repository.get_observation_for_attempt(
            attempt.attempt_id
        )

    async def _try_renormalize(
        self,
        *,
        artifact_id: str,
        case_id: str,
        request_id: str,
    ) -> TargetObservation | None:
        """Renormalize one durably persisted canonical raw response."""
        try:
            artifact = await self._persistence_repository.get_artifact(artifact_id)

            if artifact is None:
                logger.warning(
                    "Raw response artifact metadata not found: %s",
                    artifact_id,
                )
                return None

            raw_data = await self._artifact_service.get_json(artifact)

            if not isinstance(raw_data, dict):
                logger.warning(
                    "Raw response artifact %s is not a JSON object",
                    artifact_id,
                )
                return None

            response = self._parse_raw_response(raw_data)

            if response is None:
                logger.warning(
                    "Raw response artifact %s does not match a known "
                    "canonical target response",
                    artifact_id,
                )
                return None

            # Timing from the original target request cannot be reconstructed
            # from the response artifact. An empty timing object intentionally
            # represents unavailable client-side timing for this recovery path.
            timing = ClientTiming()

            observation = self._normalizer.normalize(
                response,
                case_id=case_id,
                request_id=request_id,
                timing=timing,
                raw_response_artifact=artifact,
            )

            logger.info(
                "Renormalized durable response artifact %s",
                artifact_id,
            )

            return observation

        except Exception as exc:
            logger.warning(
                "Could not renormalize response artifact %s: %s",
                artifact_id,
                exc,
            )
            return None

    async def _normalize_recovered_response(
        self,
        *,
        response: QueryResponse,
        case_id: str,
        request_id: str,
    ) -> TargetObservation:
        """Persist and normalize a response obtained by request recovery.

        The recovered response is persisted as a raw target response before
        normalization so the normal execution durability guarantees are
        preserved.
        """
        artifact = await self._artifact_service.put_json(
            response.model_dump(mode="json"),
            ArtifactType.RAW_TARGET_RESPONSE,
            metadata={
                "request_id": request_id,
                "recovered": True,
            },
        )

        timing = ClientTiming()

        return self._normalizer.normalize(
            response,
            case_id=case_id,
            request_id=request_id,
            timing=timing,
            raw_response_artifact=artifact,
        )

    @staticmethod
    def _parse_raw_response(
        raw_data: dict[str, Any],
    ) -> QueryResponse | RetrieveResponse | None:
        """Parse persisted canonical response JSON without guessing format."""
        # QueryResponse always carries status and may contain answer and/or
        # retrieval. RetrieveResponse requires a retrieval result and does not
        # expose the query-response status field.
        if "status" in raw_data or "answer" in raw_data:
            try:
                return QueryResponse.model_validate(raw_data)
            except Exception:
                pass

        if "retrieval" in raw_data:
            try:
                return RetrieveResponse.model_validate(raw_data)
            except Exception:
                pass

        return None

    async def _recover_via_request_id(
        self,
        request_id: str,
    ) -> RequestRecoveryResult | None:
        """Ask the target for the durable outcome of a previous request."""
        try:
            result = await self._adapter.recover_request(request_id)

        except Exception as exc:
            logger.warning(
                "Request recovery failed for %s: %s",
                request_id,
                exc,
            )
            return None

        status = result.status

        if status == RequestStatus.COMPLETED:
            logger.info(
                "Recovered completed request %s",
                request_id,
            )

        elif status == RequestStatus.RUNNING:
            logger.info(
                "Recovered request %s is still running",
                request_id,
            )

        elif status == RequestStatus.PENDING:
            logger.info(
                "Recovered request %s is still pending",
                request_id,
            )

        elif status == RequestStatus.FAILED:
            logger.info(
                "Recovered request %s failed",
                request_id,
            )

        else:
            logger.info(
                "Recovered request %s has status %s",
                request_id,
                status.value,
            )

        return result

    async def _get_capabilities(
        self,
    ) -> TargetCapabilities:
        """Return cached target capabilities."""
        if self._capabilities is None:
            self._capabilities = await self._adapter.capabilities()

        return self._capabilities

    def _is_attempt_stale(
        self,
        attempt: AttemptRecord | None,
    ) -> bool:
        """Return whether a RUNNING attempt can no longer be trusted active."""
        if attempt is None:
            return True

        timestamp = self._latest_attempt_activity(attempt)

        if timestamp is None:
            return True

        return datetime.now(UTC) - timestamp > self._staleness_threshold

    @staticmethod
    def _latest_attempt_activity(
        attempt: AttemptRecord,
    ) -> datetime | None:
        """Return the best available durable activity timestamp.

        ``updated_at`` acts as a lightweight heartbeat when the model exposes
        it. Otherwise the attempt start time is used.
        """
        updated_at = getattr(
            attempt,
            "updated_at",
            None,
        )

        if isinstance(updated_at, datetime):
            return updated_at

        return attempt.started_at
