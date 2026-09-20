"""Core benchmark execution engine for rag-eval.

This module coordinates the end-to-end execution of a benchmark run:

```text
load configuration
→ create/load run
→ resolve benchmark
→ resolve target adapter
→ ensure corpus READY
→ register case executions
→ execute with bounded concurrency
→ persist every result durably
→ finish run
```

It does NOT implement retry/resume/circuit-breaker logic (Stage 10).
"""

import asyncio
import logging
from dataclasses import dataclass
from datetime import UTC, datetime

from rag_eval.adapters import TargetAdapter
from rag_eval.artifacts import ArtifactService
from rag_eval.config import ExperimentConfig, TargetConfig
from rag_eval.datasets.base import BenchmarkDataset
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.session import AsyncSession
from rag_eval.models import (
    ArtifactType,
    BenchmarkCase,
    BenchmarkManifest,
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


@dataclass
class ExecutionResult:
    """Summary of a completed benchmark execution."""

    run_id: str
    total_cases: int
    completed: int
    failed: int
    target_complete: int
    pending: int


@dataclass
class ExecutionConfig:
    """Execution-time configuration extracted from validated experiment config."""

    concurrency: int
    connect_timeout: float
    request_timeout: float
    total_timeout: float
    execution_mode: QueryExecutionMode


class BenchmarkExecutor:
    """Execute a benchmark run with bounded concurrency and durable persistence.

    This executor implements the Stage 9 execution path without retry/resume
    logic. Every successful target result is persisted immediately before
    moving to the next case.
    """

    def __init__(
        self,
        config: ExperimentConfig,
        adapter: TargetAdapter,
        artifact_service: ArtifactService,
        repository: PersistenceRepository,
        session: AsyncSession,
    ) -> None:
        """Bind execution dependencies for one benchmark run.

        Args:
            config: Validated experiment configuration.
            adapter: Target adapter for HTTP or Python targets.
            artifact_service: Service for persisting large artifacts.
            repository: Repository for transactional state persistence.
            session: Async session caller controls transaction boundaries.
        """
        self._config = config
        self._adapter = adapter
        self._artifact_service = artifact_service
        self._repository = repository
        self._session = session
        self._exec_config = self._build_execution_config(config)
        self._request_identity = RequestIdentityGenerator()
        self._normalizer = ObservationNormalizer()
        self._capabilities: TargetCapabilities | None = None

    def _build_execution_config(self, config: ExperimentConfig) -> ExecutionConfig:
        """Extract execution-time configuration from validated experiment."""
        return ExecutionConfig(
            concurrency=config.execution.concurrency,
            connect_timeout=config.execution.connect_timeout,
            request_timeout=config.execution.request_timeout,
            total_timeout=config.execution.total_timeout,
            execution_mode=self._resolve_execution_mode(config.target),
        )

    def _resolve_execution_mode(
        self, target_config: TargetConfig
    ) -> QueryExecutionMode:
        """Determine execution mode from target configuration."""
        corpus_mode = target_config.corpus.mode
        if corpus_mode.value == "EXTERNAL":
            return QueryExecutionMode.QUERY
        return QueryExecutionMode.QUERY

    async def execute(
        self, run_id: str, dataset: BenchmarkDataset
    ) -> ExecutionResult:
        """Execute all benchmark cases with bounded concurrency.

        Args:
            run_id: Unique identifier for this run.
            manifest: Benchmark manifest defining cases to execute.

        Returns:
            Execution result summarizing case outcomes.
        """
        logger.info("Starting benchmark execution for run %s", run_id)

        self._capabilities = await self._adapter.capabilities()
        logger.info(
            "Target capabilities: query=%s, retrieval=%s",
            self._capabilities.query,
            self._capabilities.retrieval,
        )

        await self._repository.update_run_status(run_id, RunStatus.RUNNING.value)

        semaphore = asyncio.Semaphore(self._exec_config.concurrency)
        tasks: list[asyncio.Task[None]] = []

        try:
            async for case in self._load_cases(dataset):
                task = asyncio.create_task(self._execute_case(run_id, case, semaphore))
                tasks.append(task)

            await asyncio.gather(*tasks, return_exceptions=True)
        finally:
            await self._finish_run(run_id, tasks)

        return await self._summarize_execution(run_id)

    async def _load_cases(self, dataset: BenchmarkDataset):
        """Load validated benchmark cases from the dataset."""
        dataset.validate()

        for case in dataset.iter_cases():
            yield case

    async def _execute_case(
        self, run_id: str, case: BenchmarkCase, semaphore: asyncio.Semaphore
    ) -> None:
        """Execute one benchmark case with proper persistence ordering.

        Persistence ordering (mandatory):
        1. Create CaseExecution
        2. Create Attempt (RUNNING)
        3. Persist request identity/hash
        4. COMMIT
        5. Perform target call (NO DB transaction open)
        6. Capture raw response
        7. Persist raw response artifact
        8. COMMIT
        9. Normalize TargetObservation
        10. Persist TargetObservation
        11. Update Attempt/CaseExecution to TARGET_COMPLETE
        12. COMMIT
        """
        async with semaphore:
            case_execution_id = f"case-exec-{case.case_id}-{run_id}"
            attempt_id = f"attempt-{case_execution_id}-1"

            try:
                # Step 1-4: Persist case execution and attempt BEFORE target call
                await self._register_case_execution(
                    run_id, case, case_execution_id, attempt_id
                )

                # Step 5-8: Execute target and persist raw response
                observation = await self._execute_target_call(
                    case, case_execution_id, attempt_id
                )

                # Step 9-12: Persist observation and mark complete
                await self._complete_case_execution(
                    observation, case_execution_id, attempt_id, run_id
                )

            except Exception as exc:
                logger.exception("Case %s failed: %s", case.case_id, exc)
                await self._fail_case_execution(
                    case_execution_id, attempt_id, run_id, case.case_id, exc
                )

    async def _register_case_execution(
        self, run_id: str, case: BenchmarkCase, case_execution_id: str, attempt_id: str
    ) -> None:
        """Register case execution and initial attempt with request identity."""
        from rag_eval.db.models import AttemptRecord, CaseExecutionRecord

        async with self._session.begin():
            # Create case execution
            case_execution = CaseExecutionRecord(
                case_execution_id=case_execution_id,
                run_id=run_id,
                case_id=case.case_id,
                status=CaseExecutionStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
            await self._repository.create_case_execution(case_execution)

            # Generate request identity
            request = self._build_request(case)
            identity = self._request_identity.generate(request, attempt_id)

            # Create attempt with request identity
            attempt = AttemptRecord(
                attempt_id=attempt_id,
                case_execution_id=case_execution_id,
                attempt_number=1,
                request_id=identity.request_id,
                idempotency_key=identity.idempotency_key,
                canonical_request_hash=identity.canonical_request_hash,
                status=AttemptStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
            await self._repository.create_attempt(attempt)

            # Persist raw request artifact if configured
            raw_request_artifact = await self._persist_raw_request(
                request, identity.request_id
            )
            attempt.raw_request_artifact_id = raw_request_artifact.artifact_id
            await self._session.flush()

    def _build_request(self, case: BenchmarkCase) -> QueryRequest | RetrieveRequest:
        """Build canonical request from benchmark case.

        CRITICAL: Gold truth (reference_answer, gold_evidence) NEVER sent to target.
        """
        # Build history from case
        history: list[Message] = list(case.history)

        # Determine execution mode
        if self._exec_config.execution_mode == QueryExecutionMode.RETRIEVAL:
            return RetrieveRequest(
                request_id="",  # Will be set by identity generator
                corpus_id=self._config.target.corpus.corpus_id,
                query=case.query,
                history=history,
                parameters=self._config.target.parameters,
            )
        else:
            return QueryRequest(
                request_id="",  # Will be set by identity generator
                corpus_id=self._config.target.corpus.corpus_id,
                query=case.query,
                history=history,
                context_policy=ContextPolicy.TARGET_RETRIEVAL,
                parameters=self._config.target.parameters,
            )

    async def _persist_raw_request(
        self, request: QueryRequest | RetrieveRequest, request_id: str
    ) -> ArtifactRef:
        """Persist canonical semantic request (no secrets)."""
        # Remove any potential secrets from request before persisting
        request_dict = request.model_dump(mode="json")

        return await self._artifact_service.put_json(
            request_dict,
            ArtifactType.RAW_TARGET_REQUEST,
            metadata={"request_id": request_id},
        )

    async def _execute_target_call(
        self, case: BenchmarkCase, case_execution_id: str, attempt_id: str
    ) -> TargetObservation:
        """Execute target call and persist raw response.

        This method performs the target call OUTSIDE any database transaction.
        """
        # Build the actual request with identity already set
        request = self._build_request(case)

        # Capture timing
        timing = ClientTiming()
        timing.start()

        try:
            # Execute target call (NO DB transaction open)
            if isinstance(request, RetrieveRequest):
                response = await self._adapter.retrieve(request)
            else:
                response = await self._adapter.query(request)

            timing.end()

            # Persist raw response artifact BEFORE normalization
            raw_response_artifact = await self._persist_raw_response(
                response, request.request_id
            )

            # Persist artifact reference to attempt
            async with self._session.begin():
                from rag_eval.db.repositories import AttemptRecord

                attempt = await self._session.get(AttemptRecord, attempt_id)
                if attempt:
                    attempt.raw_response_artifact_id = raw_response_artifact.artifact_id
                    await self._session.flush()

            # Normalize to TargetObservation
            observation = self._normalizer.normalize(
                response,
                case.case_id,
                request.request_id,
                timing,
                raw_response_artifact,
            )

            return observation

        except Exception:
            timing.end()
            raise

    async def _persist_raw_response(
        self, response: QueryResponse | RetrieveResponse, request_id: str
    ) -> ArtifactRef:
        """Persist raw target response before normalization."""
        response_dict = response.model_dump(mode="json")

        return await self._artifact_service.put_json(
            response_dict,
            ArtifactType.RAW_TARGET_RESPONSE,
            metadata={"request_id": request_id},
        )

    async def _complete_case_execution(
        self,
        observation: TargetObservation,
        case_execution_id: str,
        attempt_id: str,
        run_id: str,
    ) -> None:
        """Persist observation and mark case as TARGET_COMPLETE."""
        async with self._session.begin():
            # Persist observation
            await self._repository.persist_observation(
                observation, case_execution_id, attempt_id
            )

            # Update attempt status
            await self._repository.update_attempt_status(
                attempt_id, AttemptStatus.RESPONSE_RECEIVED.value
            )

            # Update case execution status
            from rag_eval.db.models import CaseExecutionRecord

            case_execution = await self._session.get(
                CaseExecutionRecord, case_execution_id
            )
            if case_execution:
                case_execution.status = CaseExecutionStatus.TARGET_COMPLETE.value
                case_execution.finished_at = datetime.now(UTC)
                await self._session.flush()

    async def _fail_case_execution(
        self,
        case_execution_id: str,
        attempt_id: str,
        run_id: str,
        case_id: str,
        exc: Exception,
    ) -> None:
        """Persist error and mark case as FAILED."""
        async with self._session.begin():
            # Create error record
            error = ErrorRecord(
                error_id=f"error-{case_execution_id}",
                category=ErrorCategory.INTERNAL,
                code="EXECUTION_ERROR",
                message=str(exc),
                stage="target_execution",
                retryable=False,
                timestamp=datetime.now(UTC),
            )
            await self._repository.persist_error(
                error,
                run_id=run_id,
                case_execution_id=case_execution_id,
                attempt_id=attempt_id,
            )

            # Update attempt status
            await self._repository.update_attempt_status(
                attempt_id, AttemptStatus.PERMANENT_FAILURE.value
            )

            # Update case execution status
            from rag_eval.db.models import CaseExecutionRecord

            case_execution = await self._session.get(
                CaseExecutionRecord, case_execution_id
            )
            if case_execution:
                case_execution.status = CaseExecutionStatus.FAILED.value
                case_execution.finished_at = datetime.now(UTC)
                await self._session.flush()

    async def _finish_run(self, run_id: str, tasks: list[asyncio.Task[None]]) -> None:
        """Mark run as COMPLETE or FAILED based on case outcomes."""
        # Count outcomes
        _ = sum(1 for t in tasks if not t.exception())
        failed = sum(1 for t in tasks if t.exception())

        status = RunStatus.COMPLETE if failed == 0 else RunStatus.FAILED

        async with self._session.begin():
            await self._repository.update_run_status(run_id, status.value)

            run = await self._repository.get_run(run_id)
            if run:
                run.finished_at = datetime.now(UTC)
                await self._session.flush()

    async def _summarize_execution(self, run_id: str) -> ExecutionResult:
        """Count case outcomes for execution summary."""
        case_executions = await self._repository.list_case_executions(run_id)

        completed = 0
        failed = 0
        target_complete = 0
        pending = 0

        for case_exec in case_executions:
            if case_exec.status == CaseExecutionStatus.COMPLETE.value:
                completed += 1
            elif case_exec.status == CaseExecutionStatus.FAILED.value:
                failed += 1
            elif case_exec.status == CaseExecutionStatus.TARGET_COMPLETE.value:
                target_complete += 1
            elif case_exec.status == CaseExecutionStatus.PENDING.value:
                pending += 1

        return ExecutionResult(
            run_id=run_id,
            total_cases=len(case_executions),
            completed=completed,
            failed=failed,
            target_complete=target_complete,
            pending=pending,
        )
