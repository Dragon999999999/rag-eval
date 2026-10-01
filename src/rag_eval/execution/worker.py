"""Resilient case execution worker with retry and recovery support.

This worker implements Stage 10 case-level resilience:

- append-only attempt history
- config-driven bounded retry with backoff
- durable-result-first recovery
- request recovery
- idempotent replay
- target-level circuit-breaker coordination
- strict persistence boundaries around expensive target calls

Persistence ownership:

- TestRepository:
    CaseExecution / Attempt lifecycle and execution errors
- TargetRepository:
    normalized TargetObservation persistence
- PersistenceRepository:
    generic artifact metadata
- ArtifactService:
    artifact bytes plus artifact metadata coordination

The worker never owns a long-lived AsyncSession. Every persistence operation
uses a fresh session/transaction so concurrent cases never share an
AsyncSession.

The logical CaseExecution must already exist. Case executions are registered
by the run/execution coordinator before workers are started.

Critical durability invariant:

    once expensive target output has been durably captured, downstream
    failures must not require regenerating it.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_eval.adapters import TargetAdapter, TargetAdapterError
from rag_eval.artifacts import ArtifactService
from rag_eval.artifacts.base import ArtifactStore
from rag_eval.config import RetryConfig
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.test_models import AttemptRecord, CaseExecutionRecord
from rag_eval.db.test_repository import TestRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.models import (
    BenchmarkCase,
    ContextPolicy,
    ErrorCategory,
    ErrorRecord,
    Message,
    QueryRequest,
    QueryResponse,
    RetrieveRequest,
    RetrieveResponse,
    TargetCapabilities,
    TargetObservation,
)
from rag_eval.models.common import ArtifactRef
from rag_eval.models.enums import (
    ArtifactType,
    AttemptStatus,
    CaseExecutionStatus,
    QueryExecutionMode,
)

from .circuit_breaker import CircuitBreaker
from .observation import ObservationNormalizer
from .recovery import (
    CaseRecoveryService,
    RecoveryAction,
    RecoveryDecision,
)
from .requests import RequestIdentityGenerator
from .retry import RetryPolicy
from .timing import ClientTiming

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CaseExecutionResult:
    """Result of executing or recovering one logical benchmark case."""

    case_id: str
    case_execution_id: str
    success: bool
    observation: TargetObservation | None = None
    error: ErrorRecord | None = None
    attempts_made: int = 0


class ResilientCaseWorker:
    """Execute one persisted logical case with retry and recovery support.

    A worker receives immutable runtime inputs for one case. It does not
    register CaseExecution rows and does not own a database session.

    Every transaction obtains its own AsyncSession from ``session_factory``.
    This is required because multiple workers may execute concurrently.
    """

    def __init__(
        self,
        *,
        case: BenchmarkCase,
        run_id: str,
        adapter: TargetAdapter,
        artifact_store: ArtifactStore,
        session_factory: async_sessionmaker[AsyncSession],
        retry_config: RetryConfig,
        circuit_breaker: CircuitBreaker,
        capabilities: TargetCapabilities,
        case_execution_id: str | None = None,
        corpus_id: str | None = None,
        target_parameters: Mapping[str, Any] | None = None,
        execution_mode: QueryExecutionMode = QueryExecutionMode.QUERY,
        staleness_threshold_seconds: float = 300.0,
    ) -> None:
        """Bind immutable execution dependencies for one case."""
        self._case = case
        self._run_id = run_id
        self._adapter = adapter
        self._artifact_store = artifact_store
        self._session_factory = session_factory
        self._retry_policy = RetryPolicy(retry_config)
        self._circuit_breaker = circuit_breaker
        self._capabilities = capabilities
        self._case_execution_id = case_execution_id
        self._corpus_id = corpus_id
        self._target_parameters = dict(target_parameters or {})
        self._execution_mode = execution_mode
        self._staleness_threshold_seconds = staleness_threshold_seconds

        self._normalizer = ObservationNormalizer()
        self._identity_generator = RequestIdentityGenerator()

    async def execute(self) -> CaseExecutionResult:
        """Execute or recover this case from its durable persisted state."""
        case_execution = await self._load_case_execution()
        case_execution_id = case_execution.case_execution_id

        try:
            latest_attempt = await self._get_latest_attempt(case_execution_id)

            decision = await self._decide_recovery(
                case_execution,
                latest_attempt,
            )

            return await self._execute_with_recovery(
                decision=decision,
                case_execution=case_execution,
                latest_attempt=latest_attempt,
            )

        except TargetAdapterError as exc:
            error = exc.to_error_record()

            logger.warning(
                "Target execution failed for case %s: %s",
                self._case.case_id,
                error.message,
            )

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=False,
                error=error,
                attempts_made=await self._attempt_count(case_execution_id),
            )

        except Exception:
            logger.exception(
                "Unexpected execution failure for case %s",
                self._case.case_id,
            )
            raise

    async def _load_case_execution(
        self,
    ) -> CaseExecutionRecord:
        """Load the already-registered logical case execution."""
        async with self._session_factory() as session:
            repository = TestRepository(session)

            if self._case_execution_id is not None:
                record = await repository.get_case_execution(self._case_execution_id)

                if record is None:
                    raise KeyError(
                        f"case execution not found: {self._case_execution_id}"
                    )

                if record.run_id != self._run_id:
                    raise RuntimeError(
                        "case execution belongs to a different run: "
                        f"{record.case_execution_id}"
                    )

                if record.case_id != self._case.case_id:
                    raise RuntimeError(
                        "case execution belongs to a different case: "
                        f"{record.case_execution_id}"
                    )

                return record

            case_executions = await repository.list_case_executions(self._run_id)

            matching = [
                record
                for record in case_executions
                if record.case_id == self._case.case_id
            ]

            if not matching:
                raise RuntimeError(
                    "case execution was not registered before worker "
                    "execution: "
                    f"run_id={self._run_id}, "
                    f"case_id={self._case.case_id}"
                )

            if len(matching) != 1:
                raise RuntimeError(
                    "multiple case executions exist for one run/case pair: "
                    f"run_id={self._run_id}, "
                    f"case_id={self._case.case_id}"
                )

            return matching[0]

    async def _get_latest_attempt(
        self,
        case_execution_id: str,
    ) -> AttemptRecord | None:
        """Return the latest durable attempt."""
        async with self._session_factory() as session:
            repository = TestRepository(session)
            return await repository.get_latest_attempt(case_execution_id)

    async def _attempt_count(
        self,
        case_execution_id: str,
    ) -> int:
        """Return the number of persisted attempts for this case."""
        async with self._session_factory() as session:
            repository = TestRepository(session)
            attempts = await repository.list_attempts(case_execution_id)
            return len(attempts)

    async def _decide_recovery(
        self,
        case_execution: CaseExecutionRecord,
        latest_attempt: AttemptRecord | None,
    ) -> RecoveryDecision:
        """Evaluate durable state before performing any target request."""
        async with self._session_factory() as session:
            persistence_repository = PersistenceRepository(session)
            test_repository = TestRepository(session)
            target_repository = TargetRepository(session)

            artifact_service = ArtifactService(
                self._artifact_store,
                persistence_repository,
            )

            recovery_service = CaseRecoveryService(
                adapter=self._adapter,
                artifact_service=artifact_service,
                persistence_repository=persistence_repository,
                test_repository=test_repository,
                target_repository=target_repository,
                normalizer=self._normalizer,
                capabilities=self._capabilities,
                staleness_threshold_seconds=(self._staleness_threshold_seconds),
            )

            return await recovery_service.decide_recovery(
                case_execution,
                latest_attempt,
            )

    async def _execute_with_recovery(
        self,
        *,
        decision: RecoveryDecision,
        case_execution: CaseExecutionRecord,
        latest_attempt: AttemptRecord | None,
    ) -> CaseExecutionResult:
        """Execute the action selected by durable-state recovery."""
        case_execution_id = case_execution.case_execution_id
        attempts_made = (
            latest_attempt.attempt_number if latest_attempt is not None else 0
        )

        if decision.action is RecoveryAction.SKIP:
            logger.info(
                "Skipping case %s: %s",
                self._case.case_id,
                decision.reason,
            )

            success = case_execution.status in {
                CaseExecutionStatus.COMPLETE.value,
                CaseExecutionStatus.TARGET_COMPLETE.value,
            }

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=success,
                observation=decision.observation,
                attempts_made=attempts_made,
            )

        if decision.action is RecoveryAction.REUSE_OBSERVATION:
            if decision.observation is None:
                raise RuntimeError(
                    "REUSE_OBSERVATION recovery decision contains no observation"
                )

            await self._repair_target_complete_state(
                case_execution_id=case_execution_id,
                attempt=latest_attempt,
            )

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=True,
                observation=decision.observation,
                attempts_made=attempts_made,
            )

        if decision.action is RecoveryAction.RENORMALIZE_RAW:
            if decision.observation is None:
                raise RuntimeError(
                    "RENORMALIZE_RAW recovery decision contains no observation"
                )

            if latest_attempt is None:
                raise RuntimeError("RENORMALIZE_RAW requires an existing attempt")

            await self._persist_recovered_observation(
                case_execution_id=case_execution_id,
                attempt=latest_attempt,
                observation=decision.observation,
            )

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=True,
                observation=decision.observation,
                attempts_made=attempts_made,
            )

        if decision.action is RecoveryAction.RECOVER_REQUEST:
            if latest_attempt is None:
                await self._mark_unknown(case_execution_id)

                return CaseExecutionResult(
                    case_id=self._case.case_id,
                    case_execution_id=case_execution_id,
                    success=False,
                    attempts_made=attempts_made,
                )

            recovered = await self._execute_request_recovery(
                decision,
                latest_attempt,
            )

            if recovered is not None:
                await self._persist_recovered_observation(
                    case_execution_id=case_execution_id,
                    attempt=latest_attempt,
                    observation=recovered,
                )

                return CaseExecutionResult(
                    case_id=self._case.case_id,
                    case_execution_id=case_execution_id,
                    success=True,
                    observation=recovered,
                    attempts_made=attempts_made,
                )

            if decision.fallback_action is RecoveryAction.IDEMPOTENT_REPLAY:
                return await self._execute_with_retry(
                    case_execution_id=case_execution_id,
                    initial_attempt_number=attempts_made,
                    previous_attempt=latest_attempt,
                    idempotent_replay=True,
                )

            await self._mark_unknown(case_execution_id)

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=False,
                attempts_made=attempts_made,
            )

        if decision.action is RecoveryAction.IDEMPOTENT_REPLAY:
            if latest_attempt is None:
                raise RuntimeError("IDEMPOTENT_REPLAY requires an existing attempt")

            return await self._execute_with_retry(
                case_execution_id=case_execution_id,
                initial_attempt_number=attempts_made,
                previous_attempt=latest_attempt,
                idempotent_replay=True,
            )

        if decision.action is RecoveryAction.EXECUTE_NEW:
            return await self._execute_with_retry(
                case_execution_id=case_execution_id,
                initial_attempt_number=attempts_made,
                previous_attempt=latest_attempt,
                idempotent_replay=False,
            )

        if decision.action is RecoveryAction.MARK_UNKNOWN:
            await self._mark_unknown(case_execution_id)

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=False,
                attempts_made=attempts_made,
            )

        raise RuntimeError(f"unsupported recovery action: {decision.action!r}")

    async def _execute_request_recovery(
        self,
        decision: RecoveryDecision,
        attempt: AttemptRecord,
    ) -> TargetObservation | None:
        """Recover an already-issued target request.

        The adapter request-recovery call happens before any database write.
        If a recovered response is returned, the recovery service durably
        stores its raw response before this method commits.
        """
        async with self._session_factory() as session:
            persistence_repository = PersistenceRepository(session)
            test_repository = TestRepository(session)
            target_repository = TargetRepository(session)

            artifact_service = ArtifactService(
                self._artifact_store,
                persistence_repository,
            )

            recovery_service = CaseRecoveryService(
                adapter=self._adapter,
                artifact_service=artifact_service,
                persistence_repository=persistence_repository,
                test_repository=test_repository,
                target_repository=target_repository,
                normalizer=self._normalizer,
                capabilities=self._capabilities,
                staleness_threshold_seconds=(self._staleness_threshold_seconds),
            )

            observation = await recovery_service.execute_recovery(
                decision,
                attempt,
            )

            # execute_recovery may persist recovered raw-response artifact
            # metadata. Commit it before later normalization/state updates.
            await session.commit()

            return observation

    async def _execute_with_retry(
        self,
        *,
        case_execution_id: str,
        initial_attempt_number: int,
        previous_attempt: AttemptRecord | None,
        idempotent_replay: bool,
    ) -> CaseExecutionResult:
        """Execute attempts until success or retry policy exhaustion."""
        attempt_number = initial_attempt_number
        previous = previous_attempt

        while True:
            attempt_number += 1

            await self._wait_for_circuit_breaker()

            try:
                observation = await self._execute_attempt(
                    case_execution_id=case_execution_id,
                    attempt_number=attempt_number,
                    previous_attempt=previous,
                    idempotent_replay=idempotent_replay,
                )

            except TargetAdapterError as exc:
                error = exc.to_error_record()

                await self._circuit_breaker.record_failure()

                retry_decision = self._retry_policy.evaluate(
                    error,
                    attempt_number,
                )

                await self._persist_failed_attempt(
                    case_execution_id=case_execution_id,
                    attempt_number=attempt_number,
                    error=error,
                    will_retry=retry_decision.should_retry,
                )

                if not retry_decision.should_retry:
                    logger.info(
                        "Case %s permanently failed after attempt %d: %s",
                        self._case.case_id,
                        attempt_number,
                        retry_decision.reason,
                    )

                    return CaseExecutionResult(
                        case_id=self._case.case_id,
                        case_execution_id=case_execution_id,
                        success=False,
                        error=error,
                        attempts_made=attempt_number,
                    )

                logger.info(
                    "Case %s will retry after attempt %d: %s",
                    self._case.case_id,
                    attempt_number,
                    retry_decision.reason,
                )

                if retry_decision.delay_seconds > 0:
                    # No database transaction remains open during backoff.
                    await asyncio.sleep(retry_decision.delay_seconds)

                previous = await self._get_latest_attempt(case_execution_id)

                # Retry attempts of the same logical operation retain their
                # idempotency identity where supported.
                idempotent_replay = self._capabilities.idempotency

                continue

            await self._circuit_breaker.record_success()

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=True,
                observation=observation,
                attempts_made=attempt_number,
            )

    async def _wait_for_circuit_breaker(self) -> None:
        """Wait until shared target-level circuit breaker allows execution."""
        if await self._circuit_breaker.can_execute():
            return

        logger.info(
            "Circuit breaker is open; delaying case %s",
            self._case.case_id,
        )

        await self._circuit_breaker.wait_for_cooldown()

    async def _execute_attempt(
        self,
        *,
        case_execution_id: str,
        attempt_number: int,
        previous_attempt: AttemptRecord | None,
        idempotent_replay: bool,
    ) -> TargetObservation:
        """Execute one attempt using the mandatory persistence ordering.

        Ordering:

        1. construct canonical request
        2. persist raw request + Attempt(RUNNING)
        3. mark CaseExecution RUNNING
        4. COMMIT
        5. perform target call with no DB transaction open
        6. persist raw response and attach it to the attempt
        7. mark response durably received
        8. COMMIT
        9. normalize
        10. persist TargetObservation
        11. mark CaseExecution TARGET_COMPLETE
        12. COMMIT
        """
        base_request = self._build_request()

        attempt_id = f"attempt-{case_execution_id}-{attempt_number}"

        identity = self._identity_generator.generate(
            base_request,
            attempt_id,
        )

        request_id = identity.request_id
        idempotency_key = identity.idempotency_key
        canonical_hash = identity.canonical_request_hash

        if idempotent_replay and previous_attempt is not None:
            if previous_attempt.canonical_request_hash is None:
                raise RuntimeError(
                    "cannot perform idempotent replay without the "
                    "previous canonical request hash"
                )

            if canonical_hash != previous_attempt.canonical_request_hash:
                raise RuntimeError(
                    "refusing idempotent replay because the canonical "
                    "request payload changed"
                )

            if previous_attempt.idempotency_key is None:
                raise RuntimeError(
                    "cannot perform idempotent replay because the "
                    "previous attempt has no idempotency key"
                )

            # A retry/replay is the same logical target operation.
            request_id = previous_attempt.request_id
            idempotency_key = previous_attempt.idempotency_key
            canonical_hash = previous_attempt.canonical_request_hash

        request = base_request.model_copy(
            update={
                "request_id": request_id,
            }
        )

        await self._persist_attempt_before_call(
            case_execution_id=case_execution_id,
            attempt_id=attempt_id,
            attempt_number=attempt_number,
            request=request,
            request_id=request_id,
            idempotency_key=idempotency_key,
            canonical_hash=canonical_hash,
        )

        timing = ClientTiming()
        timing.start()

        try:
            if isinstance(request, RetrieveRequest):
                response = await self._adapter.retrieve(request)
            else:
                response = await self._adapter.query(request)

        except TargetAdapterError:
            timing.end()
            raise

        except Exception as exc:
            timing.end()

            raise TargetAdapterError(
                str(exc),
                category=ErrorCategory.INTERNAL,
                code="EXECUTION_ERROR",
                stage="target_execution",
            ) from exc

        timing.end()

        # From this point onward, the expensive target operation has
        # successfully returned. Do not convert downstream persistence or
        # normalization failures into target retries.
        raw_response_artifact = await self._persist_raw_response(
            response=response,
            request_id=request_id,
            attempt_id=attempt_id,
        )

        observation = self._normalizer.normalize(
            response,
            case_id=self._case.case_id,
            request_id=request_id,
            timing=timing,
            raw_response_artifact=raw_response_artifact,
        )

        await self._persist_completed_observation(
            case_execution_id=case_execution_id,
            attempt_id=attempt_id,
            observation=observation,
        )

        return observation

    async def _persist_attempt_before_call(
        self,
        *,
        case_execution_id: str,
        attempt_id: str,
        attempt_number: int,
        request: QueryRequest | RetrieveRequest,
        request_id: str,
        idempotency_key: str | None,
        canonical_hash: str | None,
    ) -> None:
        """Persist request identity and RUNNING state before target execution."""
        started_at = datetime.now(UTC)

        async with self._session_factory() as session:
            async with session.begin():
                persistence_repository = PersistenceRepository(session)
                test_repository = TestRepository(session)

                artifact_service = ArtifactService(
                    self._artifact_store,
                    persistence_repository,
                )

                raw_request_artifact = await artifact_service.put_json(
                    request.model_dump(mode="json"),
                    ArtifactType.RAW_TARGET_REQUEST,
                    metadata={
                        "request_id": request_id,
                        "run_id": self._run_id,
                        "case_id": self._case.case_id,
                        "case_execution_id": case_execution_id,
                        "attempt_id": attempt_id,
                    },
                )

                attempt = AttemptRecord(
                    attempt_id=attempt_id,
                    case_execution_id=case_execution_id,
                    attempt_number=attempt_number,
                    request_id=request_id,
                    idempotency_key=idempotency_key,
                    canonical_request_hash=canonical_hash,
                    status=AttemptStatus.RUNNING.value,
                    started_at=started_at,
                    retryable=None,
                    error_summary=None,
                    raw_request_artifact_id=(raw_request_artifact.artifact_id),
                    metadata_json={},
                )

                await test_repository.create_attempt(attempt)

                await test_repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.RUNNING.value,
                    started_at=started_at,
                    clear_finished_at=True,
                )

    async def _persist_raw_response(
        self,
        *,
        response: QueryResponse | RetrieveResponse,
        request_id: str,
        attempt_id: str,
    ) -> ArtifactRef:
        """Persist target output before normalization.

        Once this transaction commits, downstream normalization failures can
        recover from the durable raw response instead of querying the target
        again.
        """
        async with self._session_factory() as session:
            async with session.begin():
                persistence_repository = PersistenceRepository(session)
                test_repository = TestRepository(session)

                artifact_service = ArtifactService(
                    self._artifact_store,
                    persistence_repository,
                )

                artifact = await artifact_service.put_json(
                    response.model_dump(mode="json"),
                    ArtifactType.RAW_TARGET_RESPONSE,
                    metadata={
                        "request_id": request_id,
                        "run_id": self._run_id,
                        "case_id": self._case.case_id,
                        "attempt_id": attempt_id,
                    },
                )

                attempt = await test_repository.get_attempt(attempt_id)

                if attempt is None:
                    raise KeyError(f"attempt not found: {attempt_id}")

                attempt.raw_response_artifact_id = artifact.artifact_id

                await test_repository.update_attempt_status(
                    attempt_id,
                    AttemptStatus.RESPONSE_RECEIVED.value,
                    finished_at=datetime.now(UTC),
                    retryable=False,
                    clear_error_summary=True,
                )

                await session.flush()

                return artifact

    async def _persist_completed_observation(
        self,
        *,
        case_execution_id: str,
        attempt_id: str,
        observation: TargetObservation,
    ) -> None:
        """Persist normalized target output and mark target execution complete."""
        finished_at = datetime.now(UTC)

        async with self._session_factory() as session:
            async with session.begin():
                target_repository = TargetRepository(session)
                test_repository = TestRepository(session)

                await target_repository.persist_observation(
                    observation,
                    case_execution_id,
                    attempt_id,
                )

                await test_repository.update_attempt_status(
                    attempt_id,
                    AttemptStatus.RESPONSE_RECEIVED.value,
                    finished_at=finished_at,
                    retryable=False,
                    clear_error_summary=True,
                )

                await test_repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.TARGET_COMPLETE.value,
                    finished_at=finished_at,
                )

    async def _persist_recovered_observation(
        self,
        *,
        case_execution_id: str,
        attempt: AttemptRecord,
        observation: TargetObservation,
    ) -> None:
        """Persist an observation reconstructed from durable recovery state."""
        finished_at = datetime.now(UTC)

        async with self._session_factory() as session:
            async with session.begin():
                target_repository = TargetRepository(session)
                test_repository = TestRepository(session)

                existing = await target_repository.get_observation_for_attempt(
                    attempt.attempt_id
                )

                if existing is None:
                    await target_repository.persist_observation(
                        observation,
                        case_execution_id,
                        attempt.attempt_id,
                    )

                await test_repository.update_attempt_status(
                    attempt.attempt_id,
                    AttemptStatus.RESPONSE_RECEIVED.value,
                    finished_at=finished_at,
                    retryable=False,
                    clear_error_summary=True,
                )

                await test_repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.TARGET_COMPLETE.value,
                    finished_at=finished_at,
                )

    async def _repair_target_complete_state(
        self,
        *,
        case_execution_id: str,
        attempt: AttemptRecord | None,
    ) -> None:
        """Repair stale lifecycle state when an observation already exists."""
        finished_at = datetime.now(UTC)

        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)

                if attempt is not None:
                    await repository.update_attempt_status(
                        attempt.attempt_id,
                        AttemptStatus.RESPONSE_RECEIVED.value,
                        finished_at=finished_at,
                        retryable=False,
                        clear_error_summary=True,
                    )

                await repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.TARGET_COMPLETE.value,
                    finished_at=finished_at,
                )

    async def _persist_failed_attempt(
        self,
        *,
        case_execution_id: str,
        attempt_number: int,
        error: ErrorRecord,
        will_retry: bool,
    ) -> None:
        """Persist a failed attempt before sleeping or returning."""
        attempt_id = f"attempt-{case_execution_id}-{attempt_number}"
        finished_at = datetime.now(UTC)

        attempt_status = (
            AttemptStatus.RETRYABLE_FAILURE.value
            if will_retry
            else AttemptStatus.PERMANENT_FAILURE.value
        )

        case_status = (
            CaseExecutionStatus.RETRY_PENDING.value
            if will_retry
            else CaseExecutionStatus.FAILED.value
        )

        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)

                attempt = await repository.get_attempt(attempt_id)

                if attempt is not None:
                    await repository.update_attempt_status(
                        attempt_id,
                        attempt_status,
                        finished_at=finished_at,
                        retryable=will_retry,
                        error_summary=error.message,
                    )

                await repository.persist_error(
                    error,
                    run_id=self._run_id,
                    case_execution_id=case_execution_id,
                    attempt_id=(attempt_id if attempt is not None else None),
                )

                await repository.update_case_execution_status(
                    case_execution_id,
                    case_status,
                    finished_at=(None if will_retry else finished_at),
                    clear_finished_at=will_retry,
                )

    async def _mark_unknown(
        self,
        case_execution_id: str,
    ) -> None:
        """Mark a case UNKNOWN without issuing another target request."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)

                await repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.UNKNOWN.value,
                )

    def _build_request(
        self,
    ) -> QueryRequest | RetrieveRequest:
        """Construct the canonical target request.

        Only evaluator-visible input is sent:

        - query
        - conversation history
        - corpus identity
        - target parameters

        Benchmark truth such as reference answers and gold evidence is never
        exposed to the evaluated target.
        """
        history: list[Message] = list(self._case.history)

        if self._execution_mode is QueryExecutionMode.RETRIEVAL:
            return RetrieveRequest(
                request_id="",
                corpus_id=self._corpus_id,
                query=self._case.query,
                history=history,
                parameters=dict(self._target_parameters),
            )

        return QueryRequest(
            request_id="",
            corpus_id=self._corpus_id,
            query=self._case.query,
            history=history,
            context_policy=ContextPolicy.TARGET_RETRIEVAL,
            parameters=dict(self._target_parameters),
        )
