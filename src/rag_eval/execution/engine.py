"""Core benchmark execution engine for rag-eval.

Coordinates target execution for an already-persisted test run:

persisted run
→ persisted PENDING case executions
→ mark run RUNNING
→ execute target calls with bounded concurrency
→ persist raw request/response artifacts
→ normalize observations
→ persist outcomes
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
from .requests import RequestIdentityGenerator
from .timing import ClientTiming

logger = logging.getLogger(__name__)

RUN_PENDING = "PENDING"
RUN_RUNNING = "RUNNING"
RUN_COMPLETE = "COMPLETE"
RUN_FAILED = "FAILED"


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
    ) -> None:
        """Bind execution dependencies."""
        self._exec_config = execution_config
        self._adapter = adapter
        self._artifact_store = artifact_store
        self._session_factory = session_factory

        self._corpus_id = corpus_id
        self._target_parameters = dict(target_parameters or {})

        self._request_identity = RequestIdentityGenerator()
        self._normalizer = ObservationNormalizer()

        self._capabilities: TargetCapabilities | None = None

    async def execute(
        self,
        run_id: str,
        benchmark: Benchmark,
    ) -> ExecutionResult:
        """Execute all persisted case executions for one run."""
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
    ) -> dict[str, str]:
        """Map benchmark case IDs to pre-created execution IDs."""
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

        return by_case

    async def _run_workers(
        self,
        run_id: str,
        benchmark: Benchmark,
        case_execution_ids: Mapping[str, str],
    ) -> bool:
        """Execute cases using a bounded worker pool."""
        queue: asyncio.Queue[tuple[BenchmarkCase, str] | None] = asyncio.Queue()

        for case in benchmark.cases:
            await queue.put(
                (
                    case,
                    case_execution_ids[case.case_id],
                )
            )

        worker_count = min(
            self._exec_config.concurrency,
            len(benchmark.cases),
        )

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

                run = await repository.get_run(run_id)

                if run is None:
                    raise KeyError(f"run not found: {run_id}")

                if run.status != RUN_PENDING:
                    raise RuntimeError(
                        f"run {run_id} cannot start from state {run.status}"
                    )

                now = datetime.now(UTC)

                await repository.update_run_lifecycle(
                    run_id,
                    status=RUN_RUNNING,
                    started_at=(run.started_at or now),
                    clear_finished_at=True,
                    clear_status_reason=True,
                )

    async def _execute_case(
        self,
        run_id: str,
        case: BenchmarkCase,
        case_execution_id: str,
    ) -> None:
        """Execute one existing logical case execution."""
        attempt_id = f"attempt-{case_execution_id}-1"

        try:
            request = await self._register_attempt(
                run_id,
                case,
                case_execution_id,
                attempt_id,
            )

            observation = await self._execute_target_call(
                case,
                request,
                attempt_id,
            )

            await self._complete_case_execution(
                observation,
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

    async def _register_attempt(
        self,
        run_id: str,
        case: BenchmarkCase,
        case_execution_id: str,
        attempt_id: str,
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
                    attempt_number=1,
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
        case_execution_id: str,
        attempt_id: str,
    ) -> None:
        """Persist observation and mark target execution complete."""
        async with self._session_factory() as session:
            async with session.begin():
                test_repository = TestRepository(session)

                target_repository = TargetRepository(session)

                await target_repository.persist_observation(
                    observation,
                    case_execution_id,
                    attempt_id,
                )

                now = datetime.now(UTC)

                await test_repository.update_attempt_status(
                    attempt_id,
                    AttemptStatus.RESPONSE_RECEIVED.value,
                    finished_at=now,
                )

                await test_repository.update_case_execution_status(
                    case_execution_id,
                    CaseExecutionStatus.TARGET_COMPLETE.value,
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
                    error_id=(f"error-{case_execution_id}"),
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
        """Mark the run COMPLETE or FAILED."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = TestRepository(session)

                await repository.update_run_lifecycle(
                    run_id,
                    status=(RUN_FAILED if failed else RUN_COMPLETE),
                    status_reason=(
                        "one or more case executions failed" if failed else None
                    ),
                    finished_at=datetime.now(UTC),
                    clear_status_reason=not failed,
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
