"""Recovery logic for resilient benchmark execution.

Implements the recovery precedence order:

1. Durable TargetObservation exists → reuse
2. Durable raw response exists → renormalize
3. Unknown outcome → request recovery
4. Idempotent replay fallback
5. New execution only if policy permits

Never regenerate expensive target output if durable state can be reused.
"""

import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum, auto

from rag_eval.adapters import TargetAdapter
from rag_eval.artifacts import ArtifactService
from rag_eval.db.models import AttemptRecord, CaseExecutionRecord
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import (
    QueryRequest,
    QueryResponse,
    RequestRecoveryResult,
    RequestStatus,
    RetrieveRequest,
    RetrieveResponse,
    TargetObservation,
)
from rag_eval.models.common import ArtifactRef
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

    This service implements the recovery precedence order to minimize
    duplicate expensive target execution after interruptions.
    """

    def __init__(
        self,
        adapter: TargetAdapter,
        artifact_service: ArtifactService,
        repository: PersistenceRepository,
        normalizer: ObservationNormalizer,
        staleness_threshold_seconds: float = 300.0,  # 5 minutes
    ) -> None:
        """Initialize recovery service.

        Args:
            adapter: Target adapter for recovery operations.
            artifact_service: Service for loading raw artifacts.
            repository: Repository for accessing persisted state.
            normalizer: Normalizer for raw response renormalization.
            staleness_threshold_seconds: Age after which RUNNING is considered stale.
        """
        self._adapter = adapter
        self._artifact_service = artifact_service
        self._repository = repository
        self._normalizer = normalizer
        self._staleness_threshold = timedelta(seconds=staleness_threshold_seconds)

    async def decide_recovery(
        self,
        case_execution: CaseExecutionRecord,
        latest_attempt: AttemptRecord | None,
        run_id: str,
    ) -> RecoveryDecision:
        """Determine recovery action for one case execution.

        Args:
            case_execution: Persisted case execution record.
            latest_attempt: Most recent attempt if any exist.
            run_id: Run identifier for error context.

        Returns:
            Recovery decision with action and reason.
        """
        case_id = case_execution.case_id
        status = case_execution.status

        # Case already complete - skip
        if status in (
            CaseExecutionStatus.COMPLETE.value,
            CaseExecutionStatus.TARGET_COMPLETE.value,
        ):
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason=f"Case already {status}",
            )

        # Check if TargetObservation already exists
        if latest_attempt:
            observation = await self._repository.get_observation(
                latest_attempt.attempt_id
            )
            if observation:
                return RecoveryDecision(
                    action=RecoveryAction.REUSE_OBSERVATION,
                    reason="TargetObservation already exists",
                    observation=observation,
                )

        # Check if raw response artifact exists
        if latest_attempt and latest_attempt.raw_response_artifact_id is not None:
            renormalized = await self._try_renormalize(
                latest_attempt.raw_response_artifact_id,
                case_id,
                latest_attempt.request_id,
                latest_attempt.attempt_id,
            )
            if renormalized:
                return RecoveryDecision(
                    action=RecoveryAction.RENORMALIZE_RAW,
                    reason="Raw response artifact exists, renormalized",
                    observation=renormalized,
                )

        # Unknown outcome recovery
        if status == CaseExecutionStatus.UNKNOWN.value or (
            status == CaseExecutionStatus.RUNNING.value
            and self._is_attempt_stale(latest_attempt)
        ):
            if latest_attempt:
                # Try request recovery if supported
                capabilities = await self._adapter.capabilities()
                if capabilities.request_recovery:
                    return RecoveryDecision(
                        action=RecoveryAction.RECOVER_REQUEST,
                        reason="Unknown/stale outcome, request recovery supported",
                    )

                # Check idempotency support
                if capabilities.idempotency:
                    return RecoveryDecision(
                        action=RecoveryAction.IDEMPOTENT_REPLAY,
                        reason="Unknown/stale outcome, idempotency supported",
                    )

                # No recovery mechanism available
                return RecoveryDecision(
                    action=RecoveryAction.MARK_UNKNOWN,
                    reason="Unknown outcome, no recovery mechanism available",
                )

        # Retry pending - continue retry flow
        if status == CaseExecutionStatus.RETRY_PENDING.value:
            return RecoveryDecision(
                action=RecoveryAction.EXECUTE_NEW,
                reason="Retry pending, continue retry flow",
            )

        # Pending case - execute normally
        if status == CaseExecutionStatus.PENDING.value:
            return RecoveryDecision(
                action=RecoveryAction.EXECUTE_NEW,
                reason="Case pending, execute normally",
            )

        # Stale RUNNING attempt
        if status == CaseExecutionStatus.RUNNING.value:
            if self._is_attempt_stale(latest_attempt):
                return RecoveryDecision(
                    action=RecoveryAction.RECOVER_REQUEST,
                    reason="Stale RUNNING attempt, attempting recovery",
                )
            else:
                # Still within threshold, wait
                return RecoveryDecision(
                    action=RecoveryAction.SKIP,
                    reason="RUNNING attempt not yet stale",
                )

        # Failed cases - skip by default
        if status == CaseExecutionStatus.FAILED.value:
            return RecoveryDecision(
                action=RecoveryAction.SKIP,
                reason="Case failed, skip by default",
            )

        # Default: mark unknown
        return RecoveryDecision(
            action=RecoveryAction.MARK_UNKNOWN,
            reason=f"Unrecognized case state: {status}",
        )

    async def _verify_observation_exists(
        self, case_execution_id: str
    ) -> TargetObservation | None:
        """Verify a valid observation exists for case execution."""
        # This would need a repository method to query by case_execution_id
        # For now, return None to indicate verification not implemented
        return None

    async def _try_renormalize(
        self,
        artifact_id: str,
        case_id: str,
        request_id: str,
        attempt_id: str,
    ) -> TargetObservation | None:
        """Attempt to renormalize a raw response artifact."""
        try:
            # Load raw response
            raw_data = await self._artifact_service.get_json(
                ArtifactRef(artifact_id=artifact_id, uri="")
            )

            if not isinstance(raw_data, dict):
                logger.warning(
                    "Raw response artifact %s is not a JSON object",
                    artifact_id,
                )
                return None

            # Validate as QueryResponse or RetrieveResponse
            if "answer" in raw_data:
                response = QueryResponse.model_validate(raw_data)
            elif "retrieval" in raw_data:
                response = RetrieveResponse.model_validate(raw_data)
            else:
                logger.warning("Unknown response format for artifact %s", artifact_id)
                return None

            # Renormalize
            timing = ClientTiming()  # No timing available for renormalization
            dummy_artifact = ArtifactRef(artifact_id=artifact_id, uri="")

            observation = self._normalizer.normalize(
                response,
                case_id=case_id,
                request_id=request_id,
                timing=timing,
                raw_response_artifact=dummy_artifact,
            )

            logger.info("Successfully renormalized artifact %s", artifact_id)
            return observation

        except Exception as exc:
            logger.warning(
                "Renormalization failed for artifact %s: %s", artifact_id, exc
            )
            return None

    def _is_attempt_stale(self, attempt: AttemptRecord | None) -> bool:
        """Check if an attempt is stale based on timing."""
        if attempt is None or attempt.started_at is None:
            return True

        elapsed = datetime.now(UTC) - attempt.started_at
        return elapsed > self._staleness_threshold

    async def execute_recovery(
        self, decision: RecoveryDecision, attempt: AttemptRecord | None
    ) -> TargetObservation | None:
        """Execute the recovery action.

        Args:
            decision: Recovery decision from decide_recovery().
            attempt: Latest attempt record if available.

        Returns:
            TargetObservation if recovery succeeded, None otherwise.
        """
        if decision.action == RecoveryAction.REUSE_OBSERVATION:
            return decision.observation

        if decision.action == RecoveryAction.RENORMALIZE_RAW:
            return decision.observation

        if decision.action == RecoveryAction.RECOVER_REQUEST:
            if attempt is None:
                logger.error("Cannot recover request without attempt record")
                return None

            return await self._recover_via_request_id(attempt.request_id)

        if decision.action == RecoveryAction.IDEMPOTENT_REPLAY:
            # Replay would be handled by execution engine
            return None

        if decision.action == RecoveryAction.MARK_UNKNOWN:
            # Marking handled by execution engine
            return None

        return None

    async def _recover_via_request_id(
        self, request_id: str
    ) -> TargetObservation | None:
        """Recover a completed request via request_id."""
        try:
            result: RequestRecoveryResult = await self._adapter.recover_request(
                request_id
            )

            if result.status == RequestStatus.COMPLETED and result.response:
                # Persist recovered response
                # This would be called by the execution engine
                logger.info("Successfully recovered request %s", request_id)
                return None  # Observation persistence handled by caller

            elif result.status == RequestStatus.RUNNING:
                logger.info("Request %s still running", request_id)
                return None

            elif result.status == RequestStatus.FAILED:
                logger.info("Request %s failed", request_id)
                return None

            else:
                logger.info("Request %s not found or cancelled", request_id)
                return None

        except Exception as exc:
            logger.warning("Request recovery failed for %s: %s", request_id, exc)
            return None
