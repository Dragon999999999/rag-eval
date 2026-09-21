"""Core benchmark execution engine for rag-eval.

Coordinates target execution for a persisted canonical benchmark:

benchmark
→ mark run RUNNING
→ register case executions
→ execute target calls with bounded concurrency
→ persist raw request/response artifacts
→ normalize observations
→ persist outcomes
→ finish run

Retry/resume/circuit-breaker behavior belongs to the recovery layer.
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_eval.adapters import TargetAdapter
from rag_eval.artifacts import ArtifactService
from rag_eval.artifacts.base import ArtifactStore
from rag_eval.config import ExperimentConfig, ExperimentTargetConfig
from rag_eval.db.models import AttemptRecord, CaseExecutionRecord
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.target_repository import TargetRepository
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
    RunStatus,
)

from .observation import ObservationNormalizer
from .requests import RequestIdentityGenerator
from .timing import ClientTiming

logger = logging.getLogger(__name__)


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
    """Execution settings derived from validated experiment configuration."""

    concurrency: int
    connect_timeout: float
    request_timeout: float
    total_timeout: float
    execution_mode: QueryExecutionMode


class BenchmarkExecutor:
    """Execute canonical benchmark cases against one target.

    Database sessions are intentionally created per transaction. Concurrent
    cases must never share one SQLAlchemy AsyncSession.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        adapter: TargetAdapter,
        artifact_store: ArtifactStore,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        """Bind execution dependencies."""
        self._config = config
        self._adapter = adapter
        self._artifact_store = artifact_store
        self._session_factory = session_factory

        self._exec_config = self._build_execution_config(config)
        self._request_identity = RequestIdentityGenerator()
        self._normalizer = ObservationNormalizer()
        self._capabilities: TargetCapabilities | None = None

    @staticmethod
    def _build_execution_config(
        config: ExperimentConfig,
    ) -> ExecutionConfig:
        """Extract execution settings from validated configuration."""
        return ExecutionConfig(
            concurrency=config.execution.concurrency,
            connect_timeout=config.execution.connect_timeout,
            request_timeout=config.execution.request_timeout,
            total_timeout=config.execution.total_timeout,
            execution_mode=BenchmarkExecutor._resolve_execution_mode(
                config.target
            ),
        )

    @staticmethod
    def _resolve_execution_mode(
        target_config: ExperimentTargetConfig,
    ) -> QueryExecutionMode:
        """Resolve how benchmark cases should be sent to the target.

        Current experiment semantics execute benchmark cases as full queries.
        Retrieval-only execution can be added when explicitly represented by
        configuration rather than inferred from corpus mode.
        """
        _ = target_config
        return QueryExecutionMode.QUERY

    async def execute(
        self,
        run_id: str,
        benchmark: Benchmark,
    ) -> ExecutionResult:
        """Execute all benchmark cases with bounded concurrency."""
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

        await self._set_run_running(run_id)

        semaphore = asyncio.Semaphore(
            self._exec_config.concurrency
        )

        tasks = [
            asyncio.create_task(
                self._execute_case(
                    run_id,
                    case,
                    semaphore,
                )
            )
            for case in benchmark.cases
        ]

        results = await asyncio.gather(
            *tasks,
            return_exceptions=True,
        )

        failed = any(
            isinstance(result, BaseException)
            for result in results
        )

        await self._finish_run(
            run_id,
            failed=failed,
        )

        return await self._summarize_execution(run_id)

    async def _set_run_running(
        self,
        run_id: str,
    ) -> None:
        """Mark the run as active."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = PersistenceRepository(session)

                await repository.update_run_status(
                    run_id,
                    RunStatus.RUNNING.value,
                )

                run = await repository.get_run(run_id)

                if run is not None and run.started_at is None:
                    run.started_at = datetime.now(UTC)

    async def _execute_case(
        self,
        run_id: str,
        case: BenchmarkCase,
        semaphore: asyncio.Semaphore,
    ) -> None:
        """Execute one benchmark case.

        Database transactions are deliberately separated from the network
        target call.
        """
        async with semaphore:
            case_execution_id = (
                f"case-exec-{case.case_id}-{run_id}"
            )
            attempt_id = (
                f"attempt-{case_execution_id}-1"
            )

            try:
                request = await self._register_case_execution(
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

                # Preserve failure information for asyncio.gather(), allowing
                # the run to be marked FAILED.
                raise

    async def _register_case_execution(
        self,
        run_id: str,
        case: BenchmarkCase,
        case_execution_id: str,
        attempt_id: str,
    ) -> QueryRequest | RetrieveRequest:
        """Persist execution identity before making the target call."""
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
                repository = PersistenceRepository(session)

                artifact_service = ArtifactService(
                    self._artifact_store,
                    repository,
                )

                case_execution = CaseExecutionRecord(
                    case_execution_id=case_execution_id,
                    run_id=run_id,
                    case_id=case.case_id,
                    status=CaseExecutionStatus.RUNNING.value,
                    started_at=datetime.now(UTC),
                )

                await repository.create_case_execution(
                    case_execution
                )

                attempt = AttemptRecord(
                    attempt_id=attempt_id,
                    case_execution_id=case_execution_id,
                    attempt_number=1,
                    request_id=identity.request_id,
                    idempotency_key=identity.idempotency_key,
                    canonical_request_hash=(
                        identity.canonical_request_hash
                    ),
                    status=AttemptStatus.RUNNING.value,
                    started_at=datetime.now(UTC),
                )

                await repository.create_attempt(attempt)

                raw_request_artifact = (
                    await self._persist_raw_request(
                        artifact_service,
                        request,
                        identity.request_id,
                    )
                )

                attempt.raw_request_artifact_id = (
                    raw_request_artifact.artifact_id
                )

                await session.flush()

        return request

    def _build_request(
        self,
        case: BenchmarkCase,
    ) -> QueryRequest | RetrieveRequest:
        """Construct target request without exposing benchmark gold truth."""
        history: list[Message] = list(case.history)

        corpus_id = self._config.target.corpus.corpus_id

        if (
            self._exec_config.execution_mode
            is QueryExecutionMode.RETRIEVAL
        ):
            return RetrieveRequest(
                request_id="",
                corpus_id=corpus_id,
                query=case.query,
                history=history,
                parameters=self._config.target.parameters,
            )

        return QueryRequest(
            request_id="",
            corpus_id=corpus_id,
            query=case.query,
            history=history,
            context_policy=ContextPolicy.TARGET_RETRIEVAL,
            parameters=self._config.target.parameters,
        )

    async def _persist_raw_request(
        self,
        artifact_service: ArtifactService,
        request: QueryRequest | RetrieveRequest,
        request_id: str,
    ) -> ArtifactRef:
        """Persist canonical target request without benchmark gold truth."""
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
        """Perform target call outside database transactions."""
        timing = ClientTiming()
        timing.start()

        try:
            if isinstance(request, RetrieveRequest):
                response = await self._adapter.retrieve(
                    request
                )
            else:
                response = await self._adapter.query(
                    request
                )

            timing.end()

        except Exception:
            timing.end()
            raise

        raw_response_artifact = (
            await self._persist_raw_response(
                response,
                request.request_id,
                attempt_id,
            )
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
        """Persist raw target response and link it to the attempt."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = PersistenceRepository(session)

                artifact_service = ArtifactService(
                    self._artifact_store,
                    repository,
                )

                artifact = await artifact_service.put_json(
                    response.model_dump(mode="json"),
                    ArtifactType.RAW_TARGET_RESPONSE,
                    metadata={
                        "request_id": request_id,
                    },
                )

                attempt = await session.get(
                    AttemptRecord,
                    attempt_id,
                )

                if attempt is None:
                    raise KeyError(
                        f"attempt not found: {attempt_id}"
                    )

                attempt.raw_response_artifact_id = (
                    artifact.artifact_id
                )

                await session.flush()

                return artifact

    async def _complete_case_execution(
        self,
        observation: TargetObservation,
        case_execution_id: str,
        attempt_id: str,
    ) -> None:
        """Persist normalized result and mark target execution complete."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = PersistenceRepository(session)
                target_repository = TargetRepository(session)

                await target_repository.persist_observation(
                    observation,
                    case_execution_id,
                    attempt_id,
                )

                await repository.update_attempt_status(
                    attempt_id,
                    AttemptStatus.RESPONSE_RECEIVED.value,
                )

                case_execution = await session.get(
                    CaseExecutionRecord,
                    case_execution_id,
                )

                if case_execution is None:
                    raise KeyError(
                        "case execution not found: "
                        f"{case_execution_id}"
                    )

                case_execution.status = (
                    CaseExecutionStatus.TARGET_COMPLETE.value
                )
                case_execution.finished_at = datetime.now(UTC)

                await session.flush()

    async def _fail_case_execution(
        self,
        case_execution_id: str,
        attempt_id: str,
        run_id: str,
        exc: Exception,
    ) -> None:
        """Persist execution failure where corresponding records exist."""
        async with self._session_factory() as session:
            async with session.begin():
                repository = PersistenceRepository(session)

                case_execution = await session.get(
                    CaseExecutionRecord,
                    case_execution_id,
                )

                attempt = await session.get(
                    AttemptRecord,
                    attempt_id,
                )

                error = ErrorRecord(
                    error_id=f"error-{case_execution_id}",
                    category=ErrorCategory.INTERNAL,
                    code="EXECUTION_ERROR",
                    message=str(exc),
                    stage="target_execution",
                    retryable=False,
                    timestamp=datetime.now(UTC),
                )

                relations: dict[str, str | None] = {
                    "run_id": run_id,
                    "case_execution_id": (
                        case_execution_id
                        if case_execution is not None
                        else None
                    ),
                    "attempt_id": (
                        attempt_id
                        if attempt is not None
                        else None
                    ),
                }

                await repository.persist_error(
                    error,
                    **relations,
                )

                if attempt is not None:
                    attempt.status = (
                        AttemptStatus.PERMANENT_FAILURE.value
                    )
                    attempt.finished_at = datetime.now(UTC)

                if case_execution is not None:
                    case_execution.status = (
                        CaseExecutionStatus.FAILED.value
                    )
                    case_execution.finished_at = datetime.now(UTC)

                await session.flush()

    async def _finish_run(
        self,
        run_id: str,
        *,
        failed: bool,
    ) -> None:
        """Mark the run COMPLETE or FAILED."""
        status = (
            RunStatus.FAILED
            if failed
            else RunStatus.COMPLETE
        )

        async with self._session_factory() as session:
            async with session.begin():
                repository = PersistenceRepository(session)

                await repository.update_run_status(
                    run_id,
                    status.value,
                )

                run = await repository.get_run(run_id)

                if run is not None:
                    run.finished_at = datetime.now(UTC)

                await session.flush()

    async def _summarize_execution(
        self,
        run_id: str,
    ) -> ExecutionResult:
        """Summarize persisted case execution states."""
        async with self._session_factory() as session:
            repository = PersistenceRepository(session)

            case_executions = (
                await repository.list_case_executions(
                    run_id
                )
            )

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

            elif (
                status
                == CaseExecutionStatus.TARGET_COMPLETE.value
            ):
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