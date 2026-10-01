"""Core benchmark execution engine for rag-eval.

Coordinates target execution for an already-persisted test run:

persisted run
→ persisted PENDING case executions
→ mark run RUNNING
→ execute target calls with bounded concurrency
→ persist raw request/response artifacts
→ normalize observations
→ score and complete each case in its own transaction
→ finish run

CaseExecutionRecords are created by TestService.start_run().  The executor
consumes those existing records; it does not create duplicate logical case
executions.

Retry/resume/circuit-breaker behavior belongs to the recovery layer.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_eval.adapters import TargetAdapter
from rag_eval.artifacts import ArtifactService
from rag_eval.artifacts.base import ArtifactStore
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.db.test_models import AttemptRecord
from rag_eval.db.test_repository import TestRepository
from rag_eval.metrics import ScoringConfig, ScoringService
from rag_eval.metrics.registry import MetricRegistry
from rag_eval.models import (
    ArtifactType,
    Benchmark,
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
    AttemptStatus,
    CaseExecutionStatus,
    QueryExecutionMode,
)

from .observation import ObservationNormalizer
from .recovery import CaseRecoveryService, RecoveryAction, RecoveryDecision
from .requests import RequestIdentityGenerator
from .timing import ClientTiming

logger = logging.getLogger(__name__)

RUN_PENDING = "PENDING"
RUN_RUNNING = "RUNNING"
RUN_COMPLETE = "COMPLETE"
RUN_FAILED = "FAILED"
RUN_INTERRUPTED = "INTERRUPTED"
RUN_COMPLETED_WITH_ERRORS = "COMPLETED_WITH_ERRORS"


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    """Summary of one benchmark execution."""

    run_id: str
    total_cases: int
    completed: int
    failed: int
    target_complete: int
    pending: int


@dataclass(frozen=True, slots=True)
class ExecutionConfig:
    """Execution settings for one persisted test run."""

    concurrency: int
    connect_timeout: float
    request_timeout: float
    total_timeout: float
    execution_mode: QueryExecutionMode

    @classmethod
    def from_mapping(
        cls,
        config: Mapping[str, Any],
    ) -> ExecutionConfig:
        """Build validated execution settings from a run snapshot."""
        concurrency = int(config.get("concurrency", 1))
        connect_timeout = float(config.get("connect_timeout", 10.0))
        request_timeout = float(config.get("request_timeout", 60.0))
        total_timeout = float(config.get("total_timeout", 120.0))

        if concurrency < 1:
            raise ValueError("execution concurrency must be >= 1")

        if connect_timeout <= 0:
            raise ValueError("connect_timeout must be > 0")

        if request_timeout <= 0:
            raise ValueError("request_timeout must be > 0")

        if total_timeout <= 0:
            raise ValueError("total_timeout must be > 0")

        raw_mode = config.get(
            "execution_mode",
            QueryExecutionMode.QUERY.value,
        )

        if isinstance(
            raw_mode,
            QueryExecutionMode,
        ):
            execution_mode = raw_mode
        else:
            value = str(raw_mode)

            try:
                execution_mode = QueryExecutionMode(value)
            except ValueError:
                try:
                    execution_mode = QueryExecutionMode[value.upper()]
                except KeyError as exc:
                    raise ValueError(f"invalid execution_mode: {raw_mode}") from exc

        return cls(
            concurrency=concurrency,
            connect_timeout=connect_timeout,
            request_timeout=request_timeout,
            total_timeout=total_timeout,
            execution_mode=execution_mode,
        )


class BenchmarkExecutor:
    """Execute canonical benchmark cases against one target.

    The TestService owns creation of the run and logical CaseExecutionRecords.

    This executor owns execution attempts and target observations.

    Database sessions are intentionally created per short transaction.
    Concurrent cases never share one SQLAlchemy AsyncSession.
    """

    def __init__(
        self,
        *,
        execution_config: ExecutionConfig,
        adapter: TargetAdapter,
        artifact_store: ArtifactStore,
        session_factory: async_sessionmaker[AsyncSession],
        corpus_id: str | None,
        target_parameters: Mapping[str, Any] | None = None,
        case_execution_ids: set[str] | None = None,
        metric_registry: MetricRegistry | None = None,
        scoring_config: ScoringConfig | None = None,
        run_metadata: Mapping[str, Any] | None = None,
        judge: Any | None = None,
    ) -> None:
        """Bind execution dependencies."""
        self._exec_config = execution_config
        self._adapter = adapter
        self._artifact_store = artifact_store
        self._session_factory = session_factory

        self._corpus_id = corpus_id
        self._target_parameters = dict(target_parameters or {})
        self._case_execution_ids = (
            set(case_execution_ids) if case_execution_ids is not None else None
        )
        self._metric_registry = metric_registry
        self._scoring_config = scoring_config or ScoringConfig()
        self._run_metadata = dict(run_metadata or {})
        self._judge = judge

        self._request_identity = RequestIdentityGenerator()
        self._normalizer = ObservationNormalizer()

        self._capabilities: TargetCapabilities | None = None

    async def execute(
        self,
        run_id: str,
        benchmark: Benchmark,
        case_execution_ids: set[str] | None = None,
    ) -> ExecutionResult:
        """Execute the selected, durable case executions for one run."""
        if not benchmark.is_complete:
            raise ValueError(
                f"benchmark {benchmark.manifest.benchmark_id} has no cases"
            )

        logger.info(
            "Starting benchmark %s for run %s",
            benchmark.manifest.benchmark_id,
            run_id,
        )

        self._capabilities = await self._adapter.capabilities()

        logger.info(
            "Target capabilities: query=%s retrieval=%s",
            self._capabilities.query,
            self._capabilities.retrieval,
        )

        case_execution_ids = await self._load_case_execution_ids(
            run_id,
            benchmark,
            requested_case_execution_ids=(
                self._case_execution_ids
                if case_execution_ids is None
                else case_execution_ids
            ),
        )

        await self._set_run_running(run_id)

        failed = await self._run_workers(
            run_id,
            benchmark,
            case_execution_ids,
        )

        await self._finish_run(
            run_id,
            failed=failed,
        )

        return await self._summarize_execution(run_id)

    async def _load_case_execution_ids(
        self,
        run_id: str,
        benchmark: Benchmark,
        requested_case_execution_ids: set[str] | None = None,
    ) -> dict[str, str]:
        """Map selected benchmark case IDs to pre-created execution IDs."""
        async with self._session_factory() as session:
            repository = TestRepository(session)

            records = await repository.list_case_executions(run_id)

        by_case: dict[str, str] = {}

        for record in records:
            if record.case_id in by_case:
                raise ValueError(
                    "multiple case executions exist "
                    f"for run {run_id}, "
                    f"case {record.case_id}"
                )

            by_case[record.case_id] = record.case_execution_id

        expected_case_ids = {case.case_id for case in benchmark.cases}

        persisted_case_ids = set(by_case)

        missing = expected_case_ids - persisted_case_ids

        unexpected = persisted_case_ids - expected_case_ids

        if missing:
            raise ValueError(
                "run is missing case executions for: " + ", ".join(sorted(missing))
            )

        if unexpected:
            raise ValueError(
                "run contains case executions not "
                "present in the benchmark: " + ", ".join(sorted(unexpected))
            )

        if requested_case_execution_ids is None:
            return by_case

        persisted_ids = set(by_case.values())
        missing_requested = requested_case_execution_ids - persisted_ids
        if missing_requested:
            raise ValueError(
                "requested case executions do not belong to run "
                f"{run_id}: "
                + ", ".join(sorted(missing_requested))
            )

        return {
            case_id: case_execution_id
            for case_id, case_execution_id in by_case.items()
            if case_execution_id in requested_case_execution_ids
        }

    async def _run_workers(
        self,
        run_id: str,
        benchmark: Benchmark,
        case_execution_ids: Mapping[str, str],
    ) -> bool:
        """Execute cases using a bounded worker pool."""
        queue: asyncio.Queue[tuple[BenchmarkCase, str] | None] = asyncio.Queue()

        async with self._session_factory() as session:
            repository = TestRepository(session)
            records = await repository.list_case_executions(run_id)

        statuses = {
            record.case_execution_id: record.status for record in records
        }
        selected_cases = [
            case
            for case in benchmark.cases
            if case.case_id in case_execution_ids
            and statuses.get(case_execution_ids[case.case_id])
            != CaseExecutionStatus.COMPLETE.value
        ]

        for case in selected_cases:
            await queue.put((case, case_execution_ids[case.case_id]))

        worker_count = min(
            self._exec_config.concurrency,
            len(selected_cases),
        )

        if worker_count == 0:
            return False

        for _ in range(worker_count):
            await queue.put(None)

        workers = [
            asyncio.create_task(
                self._worker(
                    run_id,
                    queue,
                )
            )
            for _ in range(worker_count)
        ]

        failure_counts = await asyncio.gather(*workers)

        return sum(failure_counts) > 0

    async def _worker(
        self,
        run_id: str,
        queue: asyncio.Queue[tuple[BenchmarkCase, str] | None],
    ) -> int:
        """Consume case executions until the worker sentinel."""
        failures = 0

        while True:
            item = await queue.get()

            try:
                if item is None:
                    return failures

                case, case_execution_id = item

                try:
                    await self._execute_case(
                        run_id,
                        case,
                        case_execution_id,
                    )
                except Exception:
                    failures += 1

            finally:
                queue.task_done()

    async def _set_run_running(
        self,
        run_id: str,
    ) -> None:
        """Mark the persisted run as active."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)
                await repository.claim_run_running(
                    run_id,
                    allowed_statuses=[
                        RUN_PENDING,
                        RUN_FAILED,
                        RUN_INTERRUPTED,
                        RUN_COMPLETED_WITH_ERRORS,
                    ],
                )

    async def _execute_case(
        self,
        run_id: str,
        case: BenchmarkCase,
        case_execution_id: str,
    ) -> None:
        """Execute one existing logical case execution."""
        attempt_id = f"attempt-{case_execution_id}-pending"
        try:
            decision, latest_attempt = await self._decide_recovery(
                run_id,
                case_execution_id,
            )

            if decision.action is RecoveryAction.SKIP:
                return

            if decision.observation is not None:
                observation = decision.observation
                if latest_attempt is None:
                    raise RuntimeError(
                        "recovered observation has no owning attempt"
                    )
                attempt_id = latest_attempt.attempt_id
            else:
                await self._reset_case_for_new_attempt(case_execution_id)
                attempt_id, attempt_number = await self._next_attempt_id(
                    case_execution_id
                )
                request = await self._register_attempt(
                    run_id,
                    case,
                    case_execution_id,
                    attempt_id,
                    attempt_number,
                )

                observation = await self._execute_target_call(
                    case,
                    request,
                    attempt_id,
                )

            await self._complete_case_execution(
                observation,
                case,
                run_id,
                case_execution_id,
                attempt_id,
            )

        except Exception as exc:
            logger.exception(
                "Case %s failed: %s",
                case.case_id,
                exc,
            )

            await self._fail_case_execution(
                case_execution_id,
                attempt_id,
                run_id,
                exc,
            )

            raise

    async def _decide_recovery(
        self,
        run_id: str,
        case_execution_id: str,
    ) -> tuple[RecoveryDecision, AttemptRecord | None]:
        """Inspect durable case state before issuing a target request."""
        async with self._session_factory() as session:
            test_repository = TestRepository(session)
            target_repository = TargetRepository(session)
            persistence_repository = PersistenceRepository(session)
            artifact_service = ArtifactService(
                self._artifact_store,
                persistence_repository,
            )
            case_execution = await test_repository.get_case_execution(
                case_execution_id
            )
            if case_execution is None or case_execution.run_id != run_id:
                raise KeyError(f"case execution not found: {case_execution_id}")

            latest_attempt = await test_repository.get_latest_attempt(
                case_execution_id
            )
            recovery_service = CaseRecoveryService(
                adapter=self._adapter,
                artifact_service=artifact_service,
                persistence_repository=persistence_repository,
                test_repository=test_repository,
                target_repository=target_repository,
                normalizer=self._normalizer,
                capabilities=self._capabilities,
            )
            decision = await recovery_service.decide_recovery(
                case_execution,
                latest_attempt,
                run_id=run_id,
            )

            if decision.action is RecoveryAction.RECOVER_REQUEST:
                recovered = await recovery_service.execute_recovery(
                    decision,
                    latest_attempt,
                )
                if recovered is not None:
                    decision = RecoveryDecision(
                        action=decision.action,
                        reason=decision.reason,
                        case_id=decision.case_id,
                        observation=recovered,
                        request_to_replay=decision.request_to_replay,
                        fallback_action=decision.fallback_action,
                    )
                elif decision.fallback_action is not None:
                    decision = RecoveryDecision(
                        action=decision.fallback_action,
                        reason=(
                            f"{decision.reason}; recovery response was not "
                            "available, using the safe fallback"
                        ),
                        case_id=decision.case_id,
                    )

            return decision, latest_attempt

    async def _next_attempt_id(self, case_execution_id: str) -> tuple[str, int]:
        """Return a unique monotonic attempt identifier for a case."""
        async with self._session_factory() as session:
            repository = TestRepository(session)
            attempts = await repository.list_attempts(case_execution_id)

        attempt_number = max(
            (attempt.attempt_number for attempt in attempts),
            default=0,
        ) + 1
        return f"attempt-{case_execution_id}-{attempt_number}", attempt_number

    async def _reset_case_for_new_attempt(self, case_execution_id: str) -> None:
        """Move a recoverable case back to PENDING without deleting history."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)
                case_execution = await repository.get_case_execution(
                    case_execution_id
                )
                if case_execution is None:
                    raise KeyError(f"case execution not found: {case_execution_id}")
                if case_execution.status != CaseExecutionStatus.PENDING.value:
                    await repository.update_case_execution_status(
                        case_execution_id,
                        CaseExecutionStatus.PENDING.value,
                        clear_finished_at=True,
                    )

    async def _register_attempt(
        self,
        run_id: str,
        case: BenchmarkCase,
        case_execution_id: str,
        attempt_id: str,
        attempt_number: int = 1,
    ) -> QueryRequest | RetrieveRequest:
        """Persist RUNNING case/attempt state before target I/O."""
        base_request = self._build_request(case)

        identity = self._request_identity.generate(
            base_request,
            attempt_id,
        )

        request = base_request.model_copy(
            update={
                "request_id": identity.request_id,
            }
        )

        async with self._session_factory() as session:
            async with session.begin():
                test_repository = TestRepository(session)

                persistence_repository = PersistenceRepository(session)

                case_execution = await test_repository.get_case_execution(
                    case_execution_id
                )

                if case_execution is None:
                    raise KeyError(f"case execution not found: {case_execution_id}")

                if case_execution.run_id != run_id:
                    raise ValueError(
                        "case execution does not "
                        f"belong to run {run_id}: "
                        f"{case_execution_id}"
                    )

                if case_execution.case_id != case.case_id:
                    raise ValueError(
                        "case execution case_id does not match benchmark case"
                    )

                if case_execution.status != CaseExecutionStatus.PENDING.value:
                    raise RuntimeError(
                        f"case execution "
                        f"{case_execution_id} "
                        "cannot start from state "
                        f"{case_execution.status}"
                    )

                now = datetime.now(UTC)

                await test_repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.RUNNING.value,
                    started_at=now,
                    clear_finished_at=True,
                )

                existing_attempt = await test_repository.get_attempt(attempt_id)

                if existing_attempt is not None:
                    raise RuntimeError(f"attempt already exists: {attempt_id}")

                attempt = AttemptRecord(
                    attempt_id=attempt_id,
                    case_execution_id=(case_execution_id),
                    attempt_number=attempt_number,
                    request_id=(identity.request_id),
                    idempotency_key=(identity.idempotency_key),
                    canonical_request_hash=(identity.canonical_request_hash),
                    status=(AttemptStatus.RUNNING.value),
                    started_at=now,
                )

                await test_repository.create_attempt(attempt)

                artifact_service = ArtifactService(
                    self._artifact_store,
                    persistence_repository,
                )

                raw_request_artifact = await self._persist_raw_request(
                    artifact_service,
                    request,
                    identity.request_id,
                )

                attempt.raw_request_artifact_id = raw_request_artifact.artifact_id

                await session.flush()

        return request

    def _build_request(
        self,
        case: BenchmarkCase,
    ) -> QueryRequest | RetrieveRequest:
        """Construct request without benchmark gold truth."""
        history: list[Message] = list(case.history)

        if self._exec_config.execution_mode is QueryExecutionMode.RETRIEVAL:
            return RetrieveRequest(
                request_id="",
                corpus_id=self._corpus_id,
                query=case.query,
                history=history,
                parameters=dict(self._target_parameters),
            )

        return QueryRequest(
            request_id="",
            corpus_id=self._corpus_id,
            query=case.query,
            history=history,
            context_policy=(ContextPolicy.TARGET_RETRIEVAL),
            parameters=dict(self._target_parameters),
        )

    async def _persist_raw_request(
        self,
        artifact_service: ArtifactService,
        request: QueryRequest | RetrieveRequest,
        request_id: str,
    ) -> ArtifactRef:
        """Persist the canonical request."""
        return await artifact_service.put_json(
            request.model_dump(mode="json"),
            ArtifactType.RAW_TARGET_REQUEST,
            metadata={
                "request_id": request_id,
            },
        )

    async def _execute_target_call(
        self,
        case: BenchmarkCase,
        request: QueryRequest | RetrieveRequest,
        attempt_id: str,
    ) -> TargetObservation:
        """Perform target I/O outside database transactions."""
        timing = ClientTiming()
        timing.start()

        try:
            async with asyncio.timeout(self._exec_config.total_timeout):
                if isinstance(
                    request,
                    RetrieveRequest,
                ):
                    response = await self._adapter.retrieve(request)
                else:
                    response = await self._adapter.query(request)

            timing.end()

        except Exception:
            timing.end()
            raise

        raw_response_artifact = await self._persist_raw_response(
            response,
            request.request_id,
            attempt_id,
        )

        return self._normalizer.normalize(
            response,
            case.case_id,
            request.request_id,
            timing,
            raw_response_artifact,
        )

    async def _persist_raw_response(
        self,
        response: QueryResponse | RetrieveResponse,
        request_id: str,
        attempt_id: str,
    ) -> ArtifactRef:
        """Persist raw response before observation normalization."""
        async with self._session_factory() as session:
            async with session.begin():
                test_repository = TestRepository(session)

                persistence_repository = PersistenceRepository(session)

                artifact_service = ArtifactService(
                    self._artifact_store,
                    persistence_repository,
                )

                attempt = await test_repository.get_attempt(attempt_id)

                if attempt is None:
                    raise KeyError(f"attempt not found: {attempt_id}")

                artifact = await artifact_service.put_json(
                    response.model_dump(mode="json"),
                    ArtifactType.RAW_TARGET_RESPONSE,
                    metadata={
                        "request_id": request_id,
                    },
                )

                attempt.raw_response_artifact_id = artifact.artifact_id

                await session.flush()

                return artifact

    async def _complete_case_execution(
        self,
        observation: TargetObservation,
        case: BenchmarkCase,
        run_id: str,
        case_execution_id: str,
        attempt_id: str,
    ) -> None:
        """Persist one case's observation, metrics, and terminal state.

        The transaction intentionally contains the complete durable success
        boundary. A committed ``COMPLETE`` case therefore always has its
        observation and per-case metric results committed with it.
        """
        async with self._session_factory() as session:
            async with session.begin():
                test_repository = TestRepository(session)

                target_repository = TargetRepository(session)

                existing_observation = (
                    await target_repository.get_observation_for_attempt(attempt_id)
                )
                if existing_observation is None:
                    await target_repository.persist_observation(
                        observation,
                        case_execution_id,
                        attempt_id,
                    )

                if self._metric_registry is not None:
                    scorer = ScoringService(
                        self._metric_registry,
                        test_repository,
                        target_repository,
                        config=self._scoring_config,
                    )
                    await scorer.score_case(
                        run_id=run_id,
                        case_execution_id=case_execution_id,
                        case=case,
                        observation=observation,
                        run_metadata=self._run_metadata,
                        judge=self._judge,
                    )

                now = datetime.now(UTC)

                await test_repository.update_attempt_status(
                    attempt_id,
                    AttemptStatus.RESPONSE_RECEIVED.value,
                    finished_at=now,
                )

                await test_repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.COMPLETE.value,
                    finished_at=now,
                )

    async def _fail_case_execution(
        self,
        case_execution_id: str,
        attempt_id: str,
        run_id: str,
        exc: Exception,
    ) -> None:
        """Persist execution failure without destroying prior progress."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)

                case_execution = await repository.get_case_execution(case_execution_id)

                attempt = await repository.get_attempt(attempt_id)

                error = ErrorRecord(
                    error_id=(f"error-{case_execution_id}-{attempt_id}"),
                    category=(ErrorCategory.INTERNAL),
                    code="EXECUTION_ERROR",
                    message=str(exc),
                    stage="target_execution",
                    retryable=False,
                    timestamp=datetime.now(UTC),
                )

                await repository.persist_error(
                    error,
                    run_id=run_id,
                    case_execution_id=(
                        case_execution_id if case_execution is not None else None
                    ),
                    attempt_id=(attempt_id if attempt is not None else None),
                )

                now = datetime.now(UTC)

                if attempt is not None:
                    await repository.update_attempt_status(
                        attempt_id,
                        AttemptStatus.PERMANENT_FAILURE.value,
                        finished_at=now,
                        retryable=False,
                        error_summary=str(exc),
                    )

                if case_execution is not None:
                    await repository.update_case_execution_status(
                        case_execution_id,
                        CaseExecutionStatus.FAILED.value,
                        finished_at=now,
                    )

    async def _finish_run(
        self,
        run_id: str,
        *,
        failed: bool,
    ) -> None:
        """Mark the run based on the durable states of all its cases."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)

                case_executions = await repository.list_case_executions(run_id)
                complete_count = sum(
                    case.status == CaseExecutionStatus.COMPLETE.value
                    for case in case_executions
                )
                failed_count = sum(
                    case.status == CaseExecutionStatus.FAILED.value
                    for case in case_executions
                )
                unfinished_count = sum(
                    case.status
                    not in {
                        CaseExecutionStatus.COMPLETE.value,
                        CaseExecutionStatus.FAILED.value,
                    }
                    for case in case_executions
                )
                has_partial_success = complete_count > 0 and failed_count > 0

                if unfinished_count:
                    status = RUN_RUNNING
                elif has_partial_success:
                    status = RUN_COMPLETED_WITH_ERRORS
                elif failed or failed_count:
                    status = RUN_FAILED
                elif complete_count == len(case_executions):
                    status = RUN_COMPLETE
                else:
                    status = RUN_RUNNING

                await repository.update_run_lifecycle(
                    run_id,
                    status=status,
                    status_reason=(
                        "one or more case executions failed"
                        if failed_count
                        else None
                    ),
                    finished_at=(
                        None if status == RUN_RUNNING else datetime.now(UTC)
                    ),
                    clear_finished_at=status == RUN_RUNNING,
                    clear_status_reason=not failed_count,
                )

    async def _summarize_execution(
        self,
        run_id: str,
    ) -> ExecutionResult:
        """Summarize persisted case-execution states."""
        async with self._session_factory() as session:
            repository = TestRepository(session)

            case_executions = await repository.list_case_executions(run_id)

        completed = 0
        failed = 0
        target_complete = 0
        pending = 0

        for case_execution in case_executions:
            status = case_execution.status

            if status == CaseExecutionStatus.COMPLETE.value:
                completed += 1

            elif status == CaseExecutionStatus.FAILED.value:
                failed += 1

            elif status == CaseExecutionStatus.TARGET_COMPLETE.value:
                target_complete += 1

            elif status == CaseExecutionStatus.PENDING.value:
                pending += 1

        return ExecutionResult(
            run_id=run_id,
            total_cases=len(case_executions),
            completed=completed,
            failed=failed,
            target_complete=target_complete,
            pending=pending,
        )
