"""Resilient case execution worker with retry and recovery support.

This worker implements the Stage 10 resilience features:
- Append-only retry with bounded backoff
- Request recovery and idempotent replay
- Circuit breaker coordination
- Durable-result-first recovery
"""

import asyncio
import logging
from dataclasses import dataclass

from rag_eval.adapters import TargetAdapter, TargetAdapterError
from rag_eval.artifacts import ArtifactService
from rag_eval.config import RetryConfig
from rag_eval.db.models import AttemptRecord, CaseExecutionRecord
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.session import AsyncSession
from rag_eval.models import (
    BenchmarkCase,
    ErrorCategory,
    ErrorRecord,
    QueryRequest,
    QueryResponse,
    RetrieveRequest,
    RetrieveResponse,
    TargetCapabilities,
    TargetObservation,
)
from rag_eval.models.common import ArtifactRef
from rag_eval.models.enums import AttemptStatus, CaseExecutionStatus

from .circuit_breaker import CircuitBreaker
from .observation import ObservationNormalizer
from .recovery import CaseRecoveryService, RecoveryAction, RecoveryDecision
from .requests import RequestIdentityGenerator
from .retry import RetryPolicy
from .timing import ClientTiming

logger = logging.getLogger(__name__)


@dataclass
class CaseExecutionResult:
    """Result of executing one case with resilience."""

    case_id: str
    case_execution_id: str
    success: bool
    observation: TargetObservation | None = None
    error: ErrorRecord | None = None
    attempts_made: int = 0


class ResilientCaseWorker:
    """Execute one benchmark case with retry and recovery support."""

    def __init__(
        self,
        case: BenchmarkCase,
        run_id: str,
        adapter: TargetAdapter,
        artifact_service: ArtifactService,
        repository: PersistenceRepository,
        session: AsyncSession,
        retry_config: RetryConfig,
        circuit_breaker: CircuitBreaker,
        capabilities: TargetCapabilities,
    ) -> None:
        """Initialize worker for one case execution.

        Args:
            case: Benchmark case to execute.
            run_id: Run identifier.
            adapter: Target adapter.
            artifact_service: Artifact storage service.
            repository: Persistence repository.
            session: Database session (caller manages transactions).
            retry_config: Retry policy configuration.
            circuit_breaker: Shared circuit breaker for target.
            capabilities: Target capabilities.
        """
        self._case = case
        self._run_id = run_id
        self._adapter = adapter
        self._artifact_service = artifact_service
        self._repository = repository
        self._session = session
        self._retry_policy = RetryPolicy(retry_config)
        self._circuit_breaker = circuit_breaker
        self._capabilities = capabilities
        self._normalizer = ObservationNormalizer()
        self._identity_generator = RequestIdentityGenerator()
        self._recovery_service = CaseRecoveryService(
            adapter, artifact_service, repository, self._normalizer
        )

    async def execute(self) -> CaseExecutionResult:
        """Execute the case with full resilience.

        Returns:
            Execution result with outcome and attempt history.
        """
        case_execution_id = f"case-exec-{self._case.case_id}-{self._run_id}"

        try:
            # Check circuit breaker before starting
            if not await self._circuit_breaker.can_execute():
                logger.info(
                    "Circuit breaker open, waiting for case %s", self._case.case_id
                )
                await self._circuit_breaker.wait_for_cooldown()

            # Load existing case execution if any
            case_executions = await self._repository.list_case_executions(self._run_id)
            existing = next(
                (ce for ce in case_executions if ce.case_id == self._case.case_id),
                None,
            )

            if existing:
                # Recovery path
                latest_attempt = await self._get_latest_attempt(
                    existing.case_execution_id
                )
                decision = await self._recovery_service.decide_recovery(
                    existing, latest_attempt, self._run_id
                )
                return await self._execute_with_recovery(
                    decision, existing, latest_attempt, case_execution_id
                )
            else:
                # New execution path
                return await self._execute_new(case_execution_id)

        except TargetAdapterError as exc:
            error = exc.to_error_record()
            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution_id,
                success=False,
                error=error,
                attempts_made=0,
            )

    async def _get_latest_attempt(self, case_execution_id: str) -> AttemptRecord | None:
        """Get the most recent attempt for a case execution."""
        attempts = await self._repository.list_attempts(case_execution_id)
        return attempts[-1] if attempts else None

    async def _execute_with_recovery(
        self,
        decision: RecoveryDecision,
        case_execution: CaseExecutionRecord,
        latest_attempt: AttemptRecord | None,
        case_execution_id: str,
    ) -> CaseExecutionResult:
        """Execute case according to recovery decision."""
        if decision.action == RecoveryAction.SKIP:
            logger.info("Skipping case %s: %s", self._case.case_id, decision.reason)
            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution.case_execution_id,
                success=True,
                attempts_made=0,
            )

        if decision.action == RecoveryAction.REUSE_OBSERVATION:
            logger.info("Reusing existing observation for %s", self._case.case_id)
            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution.case_execution_id,
                success=True,
                observation=decision.observation,
                attempts_made=0,
            )

        if decision.action == RecoveryAction.RENORMALIZE_RAW:
            logger.info("Renormalized raw response for %s", self._case.case_id)
            # Persist the renormalized observation
            async with self._session.begin():
                await self._repository.persist_observation(
                    decision.observation,  # type: ignore[arg-type]
                    case_execution.case_execution_id,
                    latest_attempt.attempt_id if latest_attempt else "",
                )
                case_execution.status = CaseExecutionStatus.TARGET_COMPLETE.value
                await self._session.flush()

            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution.case_execution_id,
                success=True,
                observation=decision.observation,
                attempts_made=0,
            )

        if decision.action == RecoveryAction.RECOVER_REQUEST:
            if latest_attempt:
                recovered = await self._recovery_service.execute_recovery(
                    decision, latest_attempt
                )
                if recovered:
                    logger.info("Request recovery succeeded for %s", self._case.case_id)
                    return CaseExecutionResult(
                        case_id=self._case.case_id,
                        case_execution_id=case_execution.case_execution_id,
                        success=True,
                        observation=recovered,
                        attempts_made=1,
                    )

        if decision.action in (
            RecoveryAction.EXECUTE_NEW,
            RecoveryAction.IDEMPOTENT_REPLAY,
        ):
            # Continue with normal execution with retry
            attempt_number = latest_attempt.attempt_number if latest_attempt else 0
            return await self._execute_with_retry(
                case_execution_id, attempt_number, latest_attempt
            )

        if decision.action == RecoveryAction.MARK_UNKNOWN:
            logger.info("Marking case %s as UNKNOWN", self._case.case_id)
            async with self._session.begin():
                case_execution.status = CaseExecutionStatus.UNKNOWN.value
                await self._session.flush()
            return CaseExecutionResult(
                case_id=self._case.case_id,
                case_execution_id=case_execution.case_execution_id,
                success=False,
                attempts_made=0,
            )

        # Fallback
        return await self._execute_new(case_execution_id)

    async def _execute_new(self, case_execution_id: str) -> CaseExecutionResult:
        """Execute a new case (not recovery)."""
        return await self._execute_with_retry(case_execution_id, 0, None)

    async def _execute_with_retry(
        self,
        case_execution_id: str,
        initial_attempt_number: int,
        latest_attempt: AttemptRecord | None,
    ) -> CaseExecutionResult:
        """Execute case with bounded retry loop."""
        attempt_number = initial_attempt_number
        last_error: ErrorRecord | None = None

        while True:
            attempt_number += 1

            # Check circuit breaker
            if not await self._circuit_breaker.can_execute():
                await self._circuit_breaker.wait_for_cooldown()

            try:
                # Execute attempt
                observation = await self._execute_attempt(
                    case_execution_id, attempt_number, latest_attempt
                )

                # Record success
                await self._circuit_breaker.record_success()

                return CaseExecutionResult(
                    case_id=self._case.case_id,
                    case_execution_id=case_execution_id,
                    success=True,
                    observation=observation,
                    attempts_made=attempt_number,
                )

            except TargetAdapterError as exc:
                error = exc.to_error_record()

                # Record failure in circuit breaker
                await self._circuit_breaker.record_failure()

                # Persist failed attempt
                async with self._session.begin():
                    await self._persist_failed_attempt(
                        case_execution_id, attempt_number, error
                    )

                    # Set case to RETRY_PENDING if retrying
                    case_execution = await self._session.get(
                        CaseExecutionRecord, case_execution_id
                    )
                    if case_execution:
                        case_execution.status = CaseExecutionStatus.RETRY_PENDING.value
                        await self._session.flush()

                # Check retry policy
                retry_decision = self._retry_policy.evaluate(error, attempt_number)

                if not retry_decision.should_retry:
                    logger.info(
                        "Not retrying case %s: %s",
                        self._case.case_id,
                        retry_decision.reason,
                    )
                    # Mark as failed
                    async with self._session.begin():
                        case_execution = await self._session.get(
                            CaseExecutionRecord, case_execution_id
                        )
                        if case_execution:
                            case_execution.status = CaseExecutionStatus.FAILED.value
                            await self._session.flush()

                    return CaseExecutionResult(
                        case_id=self._case.case_id,
                        case_execution_id=case_execution_id,
                        success=False,
                        error=error,
                        attempts_made=attempt_number,
                    )

                # Wait for backoff (NO DB transaction open)
                if retry_decision.delay_seconds > 0:
                    logger.info(
                        "Retrying case %s in %.1fs (attempt %d/%d)",
                        self._case.case_id,
                        retry_decision.delay_seconds,
                        attempt_number,
                        self._retry_policy._config.max_attempts,
                    )
                    await asyncio.sleep(retry_decision.delay_seconds)

                # Prepare for next attempt
                latest_attempt = await self._get_latest_attempt(case_execution_id)

    async def _execute_attempt(
        self,
        case_execution_id: str,
        attempt_number: int,
        previous_attempt: AttemptRecord | None,
    ) -> TargetObservation:
        """Execute one target attempt with proper persistence ordering."""
        # Build request
        request = self._build_request()

        # Generate or reuse request identity
        if previous_attempt and self._capabilities.idempotency:
            # Reuse identity for idempotent retry
            request_id = previous_attempt.request_id
            idempotency_key = previous_attempt.idempotency_key
            canonical_hash = previous_attempt.canonical_request_hash
        else:
            identity = self._identity_generator.generate(request, case_execution_id)
            request_id = identity.request_id
            idempotency_key = identity.idempotency_key
            canonical_hash = identity.canonical_request_hash

        # Persist attempt BEFORE target call
        async with self._session.begin():
            attempt = AttemptRecord(
                attempt_id=f"attempt-{case_execution_id}-{attempt_number}",
                case_execution_id=case_execution_id,
                attempt_number=attempt_number,
                request_id=request_id,
                idempotency_key=idempotency_key,
                canonical_request_hash=canonical_hash,
                status=AttemptStatus.RUNNING.value,
            )
            await self._repository.create_attempt(attempt)

            # Update case execution
            case_execution = await self._session.get(
                CaseExecutionRecord, case_execution_id
            )
            if case_execution:
                case_execution.status = CaseExecutionStatus.RUNNING.value
                await self._session.flush()

        # Execute target call (NO DB transaction)
        timing = ClientTiming()
        timing.start()

        try:
            if isinstance(request, RetrieveRequest):
                response = await self._adapter.retrieve(request)
            else:
                response = await self._adapter.query(request)

            timing.end()

            # Persist raw response
            raw_artifact = await self._persist_raw_response(response, request_id)

            # Update attempt with artifact reference
            async with self._session.begin():
                attempt = await self._session.get(AttemptRecord, attempt.attempt_id)
                if attempt:
                    attempt.raw_response_artifact_id = raw_artifact.artifact_id
                    await self._session.flush()

            # Normalize
            observation = self._normalizer.normalize(
                response,
                self._case.case_id,
                request_id,
                timing,
                raw_artifact,
            )

            # Persist observation and mark complete
            async with self._session.begin():
                await self._repository.persist_observation(
                    observation, case_execution_id, attempt.attempt_id
                )

                await self._repository.update_attempt_status(
                    attempt.attempt_id, AttemptStatus.RESPONSE_RECEIVED.value
                )

                case_execution = await self._session.get(
                    CaseExecutionRecord, case_execution_id
                )
                if case_execution:
                    case_execution.status = CaseExecutionStatus.TARGET_COMPLETE.value
                    await self._session.flush()

            return observation

        except Exception as exc:
            timing.end()
            raise TargetAdapterError(
                str(exc),
                category=ErrorCategory.INTERNAL,
                code="EXECUTION_ERROR",
                stage="target_execution",
            ) from exc

    def _build_request(self) -> QueryRequest | RetrieveRequest:
        """Build canonical request from benchmark case."""
        from rag_eval.models import ContextPolicy, Message

        history: list[Message] = list(self._case.history)

        # For now, always use QUERY mode
        return QueryRequest(
            request_id="",  # Will be set by identity generator
            corpus_id=None,  # Would come from config
            query=self._case.query,
            history=history,
            context_policy=ContextPolicy.TARGET_RETRIEVAL,
            parameters={},
        )

    async def _persist_raw_response(
        self, response: QueryResponse | RetrieveResponse, request_id: str
    ) -> ArtifactRef:
        """Persist raw target response."""
        from rag_eval.models import ArtifactType

        response_dict = response.model_dump(mode="json")
        return await self._artifact_service.put_json(
            response_dict,
            ArtifactType.RAW_TARGET_RESPONSE,
            metadata={"request_id": request_id},
        )

    async def _persist_failed_attempt(
        self,
        case_execution_id: str,
        attempt_number: int,
        error: ErrorRecord,
    ) -> None:
        """Persist failed attempt and error record."""
        # Update attempt status
        attempt_id = f"attempt-{case_execution_id}-{attempt_number}"
        await self._repository.update_attempt_status(
            attempt_id, AttemptStatus.RETRYABLE_FAILURE.value
        )

        # Persist error
        await self._repository.persist_error(
            error,
            run_id=self._run_id,
            case_execution_id=case_execution_id,
            attempt_id=attempt_id,
        )
