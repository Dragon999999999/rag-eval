"""Recovery logic for resilient benchmark execution.

Implements the recovery precedence order:

1. Durable TargetObservation exists -> reuse
2. Durable raw response exists -> renormalize
3. Unknown outcome -> request recovery
4. Idempotent replay fallback
5. New execution only if policy permits

Never regenerate expensive target output if durable state can be reused.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum, auto

from rag_eval.adapters import TargetAdapter
from rag_eval.artifacts import ArtifactService
from rag_eval.db.models import (
    AttemptRecord,
    CaseExecutionRecord,
)
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import (
    QueryRequest,
    QueryResponse,
    RequestRecoveryResult,
    RequestStatus,
    RetrieveRequest,
    RetrieveResponse,
    TargetObservation,
)
from rag_eval.models.enums import CaseExecutionStatus

from .observation import ObservationNormalizer
from .timing import ClientTiming


logger = logging.getLogger(__name__)


class RecoveryAction(Enum):
    """Action to take for case recovery."""

    REUSE_OBSERVATION = auto()
    RENORMALIZE_RAW = auto()
    RECOVER_REQUEST = auto()
    IDEMPOTENT_REPLAY = auto()
    EXECUTE_NEW = auto()
    SKIP = auto()
    MARK_UNKNOWN = auto()


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    """Recovery strategy for one case execution."""

    action: RecoveryAction
    reason: str
    observation: TargetObservation | None = None
    request_to_replay: QueryRequest | RetrieveRequest | None = None


class CaseRecoveryService:
    """Recover case executions from durable state.

    Recovery is intentionally based on persisted evaluator state before any
    attempt is made to contact or re-execute the target.

    General run/attempt/artifact persistence remains in PersistenceRepository.
    TargetObservation persistence belongs to TargetRepository.
    """

    def __init__(
        self,
        adapter: TargetAdapter,
        artifact_service: ArtifactService,
        repository: PersistenceRepository,
        target_repository: TargetRepository,
        normalizer: ObservationNormalizer,
        staleness_threshold_seconds: float = 300.0,
    ) -> None:
        """Initialize the recovery service."""

        self._adapter = adapter
        self._artifact_service = artifact_service
        self._repository = repository
        self._target_repository = target_repository
        self._normalizer = normalizer
        self._staleness_threshold = timedelta(
            seconds=staleness_threshold_seconds
        )

    async def decide_recovery(
        self,
        case_execution: CaseExecutionRecord,
        latest_attempt: AttemptRecord | None,
        run_id: str,
    ) -> RecoveryDecision:
        """Determine the safest recovery action for one case execution."""

        del run_id

        case_id = case_execution.case_id
        status = case_execution.status

        # ------------------------------------------------------------------
        # Already complete
        # ------------------------------------------------------------------

        if status in (
            CaseExecutionStatus.COMPLETE.value,
            CaseExecutionStatus.TARGET_COMPLETE.value,
        ):
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason=f"Case already {status}",
            )

        # ------------------------------------------------------------------
        # 1. Durable normalized observation
        # ------------------------------------------------------------------

        if latest_attempt is not None:
            observation = (
                await self._target_repository.get_observation(
                    latest_attempt.attempt_id
                )
            )

            if observation is not None:
                return RecoveryDecision(
                    action=RecoveryAction.REUSE_OBSERVATION,
                    reason="TargetObservation already exists",
                    observation=observation,
                )

        # ------------------------------------------------------------------
        # 2. Durable raw response
        # ------------------------------------------------------------------

        if (
            latest_attempt is not None
            and latest_attempt.raw_response_artifact_id is not None
        ):
            renormalized = await self._try_renormalize(
                artifact_id=latest_attempt.raw_response_artifact_id,
                case_id=case_id,
                request_id=latest_attempt.request_id,
            )

            if renormalized is not None:
                return RecoveryDecision(
                    action=RecoveryAction.RENORMALIZE_RAW,
                    reason=(
                        "Raw response artifact exists and "
                        "was successfully renormalized"
                    ),
                    observation=renormalized,
                )

        # ------------------------------------------------------------------
        # 3 / 4. Unknown or stale execution outcome
        # ------------------------------------------------------------------

        unknown_or_stale = (
            status == CaseExecutionStatus.UNKNOWN.value
            or (
                status == CaseExecutionStatus.RUNNING.value
                and self._is_attempt_stale(latest_attempt)
            )
        )

        if unknown_or_stale:
            if latest_attempt is None:
                return RecoveryDecision(
                    action=RecoveryAction.MARK_UNKNOWN,
                    reason=(
                        "Execution outcome is unknown and no "
                        "attempt record exists"
                    ),
                )

            capabilities = await self._adapter.capabilities()

            if capabilities.request_recovery:
                return RecoveryDecision(
                    action=RecoveryAction.RECOVER_REQUEST,
                    reason=(
                        "Unknown/stale outcome and target supports "
                        "request recovery"
                    ),
                )

            if capabilities.idempotency:
                return RecoveryDecision(
                    action=RecoveryAction.IDEMPOTENT_REPLAY,
                    reason=(
                        "Unknown/stale outcome and target supports "
                        "idempotent replay"
                    ),
                )

            return RecoveryDecision(
                action=RecoveryAction.MARK_UNKNOWN,
                reason=(
                    "Unknown outcome and target exposes no safe "
                    "recovery mechanism"
                ),
            )

        # ------------------------------------------------------------------
        # Explicit retry
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.RETRY_PENDING.value:
            return RecoveryDecision(
                action=RecoveryAction.EXECUTE_NEW,
                reason="Retry pending",
            )

        # ------------------------------------------------------------------
        # Fresh execution
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.PENDING.value:
            return RecoveryDecision(
                action=RecoveryAction.EXECUTE_NEW,
                reason="Case pending",
            )

        # ------------------------------------------------------------------
        # RUNNING but not stale
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.RUNNING.value:
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason="RUNNING attempt is not yet stale",
            )

        # ------------------------------------------------------------------
        # Permanently failed
        # ------------------------------------------------------------------

        if status == CaseExecutionStatus.FAILED.value:
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason="Case failed and no retry is scheduled",
            )

        return RecoveryDecision(
            action=RecoveryAction.MARK_UNKNOWN,
            reason=f"Unrecognized case state: {status}",
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
            artifact = await self._repository.get_artifact(
                artifact_id
            )

            if artifact is None:
                logger.warning(
                    "Raw response artifact metadata not found: %s",
                    artifact_id,
                )
                return None

            raw_data = await self._artifact_service.get_json(
                artifact
            )

            if not isinstance(raw_data, dict):
                logger.warning(
                    "Raw response artifact %s is not a JSON object",
                    artifact_id,
                )
                return None

            response: QueryResponse | RetrieveResponse

            if "answer" in raw_data:
                response = QueryResponse.model_validate(
                    raw_data
                )

            elif "retrieval" in raw_data:
                response = RetrieveResponse.model_validate(
                    raw_data
                )

            else:
                logger.warning(
                    "Unknown canonical response format for artifact %s",
                    artifact_id,
                )
                return None

            # The original client timing cannot be reconstructed from the raw
            # canonical response alone. The normalizer therefore receives an
            # empty timing object for this recovery path.
            timing = ClientTiming()

            observation = self._normalizer.normalize(
                response,
                case_id=case_id,
                request_id=request_id,
                timing=timing,
                raw_response_artifact=artifact,
            )

            logger.info(
                "Successfully renormalized response artifact %s",
                artifact_id,
            )

            return observation

        except Exception as exc:
            logger.warning(
                "Renormalization failed for artifact %s: %s",
                artifact_id,
                exc,
            )

            return None

    def _is_attempt_stale(
        self,
        attempt: AttemptRecord | None,
    ) -> bool:
        """Return whether the latest attempt can no longer be trusted active."""

        if (
            attempt is None
            or attempt.started_at is None
        ):
            return True

        elapsed = (
            datetime.now(UTC)
            - attempt.started_at
        )

        return (
            elapsed
            > self._staleness_threshold
        )

    async def execute_recovery(
        self,
        decision: RecoveryDecision,
        attempt: AttemptRecord | None,
    ) -> TargetObservation | None:
        """Execute recovery actions that can directly produce an observation.

        IDempotent replay and fresh execution remain responsibilities of the
        benchmark execution/retry coordinator because they create new target
        attempts.
        """

        if decision.action in (
            RecoveryAction.REUSE_OBSERVATION,
            RecoveryAction.RENORMALIZE_RAW,
        ):
            return decision.observation

        if decision.action == RecoveryAction.RECOVER_REQUEST:
            if attempt is None:
                logger.error(
                    "Cannot recover request without an attempt record"
                )
                return None

            await self._recover_via_request_id(
                attempt.request_id
            )

            # Request recovery may return a canonical response, but creating
            # and persisting the resulting observation requires case/attempt
            # context and remains the caller's responsibility.
            return None

        # IDEMPOTENT_REPLAY, EXECUTE_NEW, MARK_UNKNOWN and SKIP are acted upon
        # by the execution/retry coordinator.
        return None

    async def _recover_via_request_id(
        self,
        request_id: str,
    ) -> RequestRecoveryResult | None:
        """Ask the target for the durable outcome of a prior request."""

        try:
            result = await self._adapter.recover_request(
                request_id
            )

        except Exception as exc:
            logger.warning(
                "Request recovery failed for %s: %s",
                request_id,
                exc,
            )
            return None

        if result.status == RequestStatus.COMPLETED:
            logger.info(
                "Recovered completed request %s",
                request_id,
            )

        elif result.status == RequestStatus.RUNNING:
            logger.info(
                "Recovered request %s is still running",
                request_id,
            )

        elif result.status == RequestStatus.FAILED:
            logger.info(
                "Recovered request %s failed",
                request_id,
            )

        else:
            logger.info(
                "Recovered request %s has status %s",
                request_id,
                result.status,
            )

        return result