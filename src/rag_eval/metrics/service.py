"""Scoring service for run-level metric execution and aggregation.

This service:
1. Iterates persisted cases/observations
2. Scores each with MetricExecutionEngine
3. Persists results incrementally
4. Aggregates at run level

Critical: No TargetAdapter dependency. Scoring operates on persisted data only.
"""

import logging
from dataclasses import dataclass
from typing import Any

from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import BenchmarkCase, TargetObservation
from rag_eval.models.enums import MetricStatus

from .aggregation import compute_aggregations, convert_to_canonical
from .engine import MetricExecutionEngine, ScoringConfig
from .registry import MetricRegistry

logger = logging.getLogger(__name__)


@dataclass
class ScoringResult:
    """Summary of scoring a run."""

    run_id: str
    total_cases: int
    scored_cases: int
    total_metrics_computed: int
    total_metrics_unavailable: int
    total_metrics_failed: int
    aggregates_persisted: int


class ScoringService:
    """Service for scoring runs with registered metrics.

    This service coordinates metric execution across all cases in a run.
    It has NO TargetAdapter dependency - operates on persisted data only.
    """

    def __init__(
        self,
        registry: MetricRegistry,
        repository: PersistenceRepository,
        config: ScoringConfig | None = None,
    ) -> None:
        """Initialize scoring service.

        Args:
            registry: Metric registry with available implementations.
            repository: Repository for data access and persistence.
            config: Scoring configuration.
        """
        self._registry = registry
        self._repository = repository
        self._config = config or ScoringConfig()
        self._engine = MetricExecutionEngine(registry, repository, config)

    async def score_run(
        self,
        run_id: str,
        run_metadata: dict[str, Any] | None = None,
        judge: Any | None = None,
    ) -> ScoringResult:
        """Score all cases in a run and aggregate results.

        Args:
            run_id: Run identifier to score.
            run_metadata: Optional run metadata.
            judge: Optional judge adapter for semantic metrics.

        Returns:
            Scoring result summary.
        """
        logger.info("Starting scoring for run %s", run_id)

        # Load run to verify exists
        run = await self._repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")

        # Load case executions for this run
        case_executions = await self._repository.list_case_executions(run_id)

        total_cases = len(case_executions)
        scored_cases = 0
        total_computed = 0
        total_unavailable = 0
        total_failed = 0

        # Collect values for aggregation
        # Key: (metric_id, version) -> list of (value, status)
        metric_values: dict[
            tuple[str, str], list[tuple[float | int | None, MetricStatus]]
        ] = {}

        # Score each case
        for case_execution in case_executions:
            try:
                # Load benchmark case
                case_record = await self._repository._session.get(
                    type("BenchmarkCaseRecord", (), {}),  # type: ignore[arg-type]
                    case_execution.case_id,
                )

                if case_record is None:
                    logger.warning(
                        "Case %s not found, skipping", case_execution.case_id
                    )
                    continue

                # Convert to canonical model
                case = self._convert_to_benchmark_case(case_record)

                # Load target observation
                observation = await self._load_observation(
                    case_execution.case_execution_id
                )

                # Score this case
                results = await self._engine.score_case(
                    case=case,
                    observation=observation,
                    run_id=run_id,
                    run_metadata=run_metadata,
                    judge=judge,
                )

                scored_cases += 1

                # Collect values for aggregation
                for result in results:
                    key = (result.metric_id, result.metric_version)
                    if key not in metric_values:
                        metric_values[key] = []

                    # Convert status from result
                    status = result.status

                    # Only numeric COMPUTED values contribute to aggregation
                    if (
                        status == MetricStatus.COMPUTED
                        and result.value is not None
                        and isinstance(result.value, (int, float))
                    ):
                        metric_values[key].append((result.value, status))
                    else:
                        metric_values[key].append((None, status))

                    # Count statuses
                    if status == MetricStatus.COMPUTED:
                        total_computed += 1
                    elif status == MetricStatus.UNAVAILABLE_MISSING_INPUT:
                        total_unavailable += 1
                    elif status == MetricStatus.FAILED:
                        total_failed += 1

            except Exception as exc:
                logger.exception(
                    "Failed to score case %s: %s", case_execution.case_id, exc
                )
                # Continue with next case - don't abort entire run

        # Aggregate results
        aggregates_persisted = await self._aggregate_and_persist(run_id, metric_values)

        logger.info(
            "Completed scoring for run %s: %d/%d cases, %d computed, "
            "%d unavailable, %d failed, %d aggregates",
            run_id,
            scored_cases,
            total_cases,
            total_computed,
            total_unavailable,
            total_failed,
            aggregates_persisted,
        )

        return ScoringResult(
            run_id=run_id,
            total_cases=total_cases,
            scored_cases=scored_cases,
            total_metrics_computed=total_computed,
            total_metrics_unavailable=total_unavailable,
            total_metrics_failed=total_failed,
            aggregates_persisted=aggregates_persisted,
        )

    async def _load_observation(
        self, case_execution_id: str
    ) -> TargetObservation | None:
        """Load target observation for a case execution.

        Args:
            case_execution_id: Case execution identifier.

        Returns:
            Target observation if available, None otherwise.
        """
        # Get attempts for this case execution
        attempts = await self._repository.list_attempts(case_execution_id)

        if not attempts:
            return None

        # Get latest attempt
        latest_attempt = attempts[-1]

        # Try to load observation
        return await self._repository.get_observation(latest_attempt.attempt_id)

    def _convert_to_benchmark_case(self, record: Any) -> BenchmarkCase:
        """Convert ORM record to canonical BenchmarkCase model.

        Args:
            record: BenchmarkCaseRecord ORM entity.

        Returns:
            Canonical BenchmarkCase model.
        """
        from rag_eval.models import EvidenceSpan, Message, MessageRole

        # Convert history
        history = []
        for item in record.history:
            history.append(
                Message(
                    role=MessageRole(item["role"]),
                    content=item["content"],
                    name=item.get("name"),
                    metadata=item.get("metadata", {}),
                )
            )

        # Convert gold evidence
        gold_evidence = []
        for item in record.gold_evidence:
            gold_evidence.append(
                EvidenceSpan(
                    evidence_id=item["evidence_id"],
                    document_id=item["document_id"],
                    page=item.get("page"),
                    start_char=item.get("start_char"),
                    end_char=item.get("end_char"),
                    text=item.get("text"),
                    relevance=item.get("relevance"),
                    metadata=item.get("metadata", {}),
                )
            )

        # Convert answerability
        from rag_eval.models.enums import Answerability

        answerability = None
        if record.answerability:
            answerability = Answerability(record.answerability)

        # Extract metadata
        metadata = dict(record.metadata_json or {})
        difficulty = metadata.pop("difficulty", None)
        language = metadata.pop("language", None)

        return BenchmarkCase(
            case_id=record.case_id,
            query=record.query,
            history=history,
            reference_answer=record.reference_answer,
            gold_evidence=gold_evidence,
            answerability=answerability,
            tags=record.tags,
            difficulty=difficulty,
            language=language,
            metadata=metadata,
        )

    async def _aggregate_and_persist(
        self,
        run_id: str,
        metric_values: dict[
            tuple[str, str], list[tuple[float | int | None, MetricStatus]]
        ],
    ) -> int:
        """Aggregate metric results and persist aggregates.

        Args:
            run_id: Run identifier.
            metric_values: Collected metric values by (metric_id, version).

        Returns:
            Number of aggregates persisted.
        """
        persisted = 0

        for (metric_id, metric_version), values_statuses in metric_values.items():
            # Separate values and statuses
            values = [
                v
                for v, s in values_statuses
                if v is not None and isinstance(v, (int, float))
            ]
            statuses = [s for _, s in values_statuses]

            # Compute aggregations
            aggregations = compute_aggregations(
                metric_id=metric_id,
                metric_version=metric_version,
                values=values,
                statuses=statuses,
            )

            # Persist each aggregation
            for agg in aggregations:
                try:
                    canonical = convert_to_canonical(agg, run_id)
                    await self._repository.persist_aggregate(canonical)
                    persisted += 1
                except Exception as exc:
                    logger.error(
                        "Failed to persist aggregate %s.%s: %s",
                        metric_id,
                        agg.aggregation_name,
                        exc,
                    )

        return persisted
