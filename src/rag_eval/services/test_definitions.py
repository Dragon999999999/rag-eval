"""Service for managing test definitions.

Handles creation, validation, and resolution of TestDefinition into
canonical experiment configuration for execution.
"""

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.models import (
    BenchmarkRecord,
    MetricConfigRecord,
    TargetRecord,
    TestDefinitionRecord,
)
from rag_eval.services.metric_configs import MetricConfigService


class TestDefinitionService:
    """Service for managing test definitions.

    A TestDefinition represents reusable evaluation intent:
    "Evaluate this Target against this Benchmark using this MetricConfig
    under these execution settings."

    It does NOT contain execution state - that belongs to EvaluationRun.
    """

    def __init__(self, session: AsyncSession) -> None:
        """Initialize with database session.

        Args:
            session: Async database session.
        """
        self._session = session
        self._metric_config_service = MetricConfigService(session)

    def _compute_definition_hash(
        self,
        target_id: str,
        benchmark_id: str,
        metric_config_id: str,
        execution_config: dict[str, Any],
        seed: int | None,
    ) -> str:
        """Compute deterministic hash of test definition.

        Args:
            target_id: Target identifier.
            benchmark_id: Benchmark identifier.
            metric_config_id: Metric configuration identifier.
            execution_config: Execution parameters.
            seed: Random seed.

        Returns:
            SHA-256 hex digest of canonical JSON representation.
        """
        canonical = {
            "target_id": target_id,
            "benchmark_id": benchmark_id,
            "metric_config_id": metric_config_id,
            "execution_config": execution_config,
            "seed": seed,
        }
        canonical_json = json.dumps(canonical, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical_json.encode()).hexdigest()

    async def create(
        self,
        name: str,
        target_id: str,
        benchmark_id: str,
        metric_config_id: str,
        description: str | None = None,
        execution_config: dict[str, Any] | None = None,
        seed: int | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TestDefinitionRecord:
        """Create a new test definition.

        Args:
            name: Human-readable name.
            target_id: Reference to target configuration.
            benchmark_id: Reference to benchmark definition.
            metric_config_id: Reference to metric configuration.
            description: Optional description.
            execution_config: Execution parameters (concurrency, timeouts, etc.).
            seed: Random seed for reproducibility.
            tags: Organizational tags.
            metadata: Additional metadata.

        Returns:
            Created TestDefinitionRecord.

        Raises:
            ValueError: If referenced resources don't exist.
        """
        # Validate references exist
        await self._validate_references(target_id, benchmark_id, metric_config_id)

        # Compute hash
        definition_hash = self._compute_definition_hash(
            target_id,
            benchmark_id,
            metric_config_id,
            execution_config or {},
            seed,
        )

        # Create record
        record = TestDefinitionRecord(
            test_definition_id=f"td-{name.lower().replace(' ', '-')}",
            name=name,
            description=description,
            target_id=target_id,
            benchmark_id=benchmark_id,
            metric_config_id=metric_config_id,
            execution_config=execution_config or {},
            seed=seed,
            tags=tags or [],
            metadata_json=metadata or {},
            definition_hash=definition_hash,
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def _validate_references(
        self,
        target_id: str,
        benchmark_id: str,
        metric_config_id: str,
    ) -> None:
        """Validate that all referenced resources exist.

        Args:
            target_id: Target identifier.
            benchmark_id: Benchmark identifier.
            metric_config_id: Metric configuration identifier.

        Raises:
            ValueError: If any reference doesn't exist.
        """
        # Check target exists
        target_result = await self._session.execute(
            select(TargetRecord).where(TargetRecord.target_id == target_id)
        )
        if not target_result.scalar_one_or_none():
            raise ValueError(f"Target '{target_id}' not found")

        # Check benchmark exists
        benchmark_result = await self._session.execute(
            select(BenchmarkRecord).where(BenchmarkRecord.benchmark_id == benchmark_id)
        )
        if not benchmark_result.scalar_one_or_none():
            raise ValueError(f"Benchmark '{benchmark_id}' not found")

        # Check metric config exists
        metric_config_result = await self._session.execute(
            select(MetricConfigRecord).where(
                MetricConfigRecord.metric_config_id == metric_config_id
            )
        )
        if not metric_config_result.scalar_one_or_none():
            raise ValueError(f"MetricConfig '{metric_config_id}' not found")

    async def get(self, test_definition_id: str) -> TestDefinitionRecord | None:
        """Get a test definition by ID.

        Args:
            test_definition_id: Definition identifier.

        Returns:
            TestDefinitionRecord if found, None otherwise.
        """
        result = await self._session.execute(
            select(TestDefinitionRecord).where(
                TestDefinitionRecord.test_definition_id == test_definition_id
            )
        )
        return result.scalar_one_or_none()

    async def list_all(
        self,
        limit: int = 100,
        offset: int = 0,
    ) -> list[TestDefinitionRecord]:
        """List test definitions with pagination.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of TestDefinitionRecord.
        """
        result = await self._session.execute(
            select(TestDefinitionRecord)
            .order_by(TestDefinitionRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(
        self,
        test_definition_id: str,
        name: str | None = None,
        description: str | None = None,
        target_id: str | None = None,
        benchmark_id: str | None = None,
        metric_config_id: str | None = None,
        execution_config: dict[str, Any] | None = None,
        seed: int | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> TestDefinitionRecord | None:
        """Update an existing test definition.

        Args:
            test_definition_id: Definition identifier.
            name: New name.
            description: New description.
            target_id: New target reference.
            benchmark_id: New benchmark reference.
            metric_config_id: New metric config reference.
            execution_config: New execution parameters.
            seed: New random seed.
            tags: New tags.
            metadata: New metadata.

        Returns:
            Updated TestDefinitionRecord if found, None otherwise.

        Raises:
            ValueError: If updated references don't exist.
        """
        record = await self.get(test_definition_id)
        if not record:
            return None

        # Update fields
        if name is not None:
            record.name = name
        if description is not None:
            record.description = description
        if target_id is not None:
            await self._validate_references(
                target_id, record.benchmark_id, record.metric_config_id
            )
            record.target_id = target_id
        if benchmark_id is not None:
            await self._validate_references(
                record.target_id, benchmark_id, record.metric_config_id
            )
            record.benchmark_id = benchmark_id
        if metric_config_id is not None:
            await self._validate_references(
                record.target_id, record.benchmark_id, metric_config_id
            )
            record.metric_config_id = metric_config_id
        if execution_config is not None:
            record.execution_config = execution_config
        if seed is not None:
            record.seed = seed
        if tags is not None:
            record.tags = tags
        if metadata is not None:
            record.metadata_json = metadata

        # Recompute hash
        record.definition_hash = self._compute_definition_hash(
            record.target_id,
            record.benchmark_id,
            record.metric_config_id,
            record.execution_config,
            record.seed,
        )

        await self._session.flush()
        return record

    async def delete(self, test_definition_id: str) -> bool:
        """Delete a test definition.

        Args:
            test_definition_id: Definition identifier.

        Returns:
            True if deleted, False if not found or has dependent runs.
        """
        record = await self.get(test_definition_id)
        if not record:
            return False

        # Check for dependent runs (would violate FK constraint)
        from rag_eval.db.models import RunRecord

        runs_result = await self._session.execute(
            select(RunRecord).where(RunRecord.test_definition_id == test_definition_id)
        )
        if runs_result.scalars().first():
            return False  # Has dependent runs

        await self._session.delete(record)
        await self._session.flush()
        return True

    async def resolve_to_experiment_config(
        self,
        test_definition: TestDefinitionRecord,
    ) -> dict[str, Any]:
        """Resolve test definition to canonical experiment configuration.

        This is the critical function that composes the test definition
        into the canonical Stage 3 experiment configuration format.

        Args:
            test_definition: Test definition to resolve.

        Returns:
            Canonical experiment configuration dictionary.
        """
        # Load referenced resources
        target_result = await self._session.execute(
            select(TargetRecord).where(
                TargetRecord.target_id == test_definition.target_id
            )
        )
        target = target_result.scalar_one()

        benchmark_result = await self._session.execute(
            select(BenchmarkRecord).where(
                BenchmarkRecord.benchmark_id == test_definition.benchmark_id
            )
        )
        benchmark = benchmark_result.scalar_one()

        metric_config_result = await self._session.execute(
            select(MetricConfigRecord).where(
                MetricConfigRecord.metric_config_id == test_definition.metric_config_id
            )
        )
        metric_config = metric_config_result.scalar_one()

        # Build canonical experiment config
        # This mirrors the structure in config/models.py
        experiment_config = {
            "version": "1.0",
            "run": {
                "name": test_definition.name,
                "seed": test_definition.seed,
                "resume": False,
                "tags": test_definition.tags,
                "metadata": test_definition.metadata_json,
            },
            "dataset": {
                "dataset_id": benchmark.benchmark_id,
                "version": benchmark.version,
            },
            "target": {
                "adapter": "http",  # Default, could be stored in TargetRecord
                "base_url": target.metadata_json.get("base_url"),
                "authentication_env": target.metadata_json.get("authentication_env"),
                "corpus": {
                    "mode": target.metadata_json.get("corpus_mode", "EXTERNAL"),
                    "parameters": target.metadata_json.get("corpus_parameters", {}),
                },
                "parameters": target.metadata_json.get("parameters", {}),
            },
            "execution": test_definition.execution_config,
            "metrics": {
                "mode": metric_config.mode,
                "selected": metric_config.selected_metrics,
                "judge": metric_config.judge_config,
            },
            "storage": {
                "database": {"url_env": "RAG_EVAL_DATABASE_URL"},
                "artifacts": {
                    "bucket": "rag-eval-artifacts",
                },
            },
        }

        return experiment_config

    async def validate(
        self,
        test_definition_id: str,
        check_target_capabilities: bool = False,
    ) -> dict[str, Any]:
        """Validate a test definition.

        Two-phase validation:
        1. Structural validation (always performed)
        2. Capability validation (optional, requires target contact)

        Args:
            test_definition_id: Definition identifier.
            check_target_capabilities: Whether to contact target for capabilities.

        Returns:
            Validation result with status and any errors.
        """
        result: dict[str, Any] = {
            "valid": True,
            "structural_valid": True,
            "capabilities_valid": True,
            "errors": [],
            "warnings": [],
        }

        # Get test definition
        definition = await self.get(test_definition_id)
        if not definition:
            result["valid"] = False
            result["structural_valid"] = False
            result["errors"].append("Test definition not found")
            return result

        # Structural validation
        try:
            await self._validate_references(
                definition.target_id,
                definition.benchmark_id,
                definition.metric_config_id,
            )
        except ValueError as e:
            result["valid"] = False
            result["structural_valid"] = False
            result["errors"].append(str(e))

        # Capability validation (optional)
        if check_target_capabilities:
            # This would contact the target to verify capabilities
            # For now, just mark as not implemented
            result["capabilities_valid"] = True
            result["warnings"].append("Capability validation not yet implemented")

        return result

    async def get_plan(
        self,
        test_definition_id: str,
    ) -> dict[str, Any]:
        """Get execution plan for a test definition.

        Shows resolved configuration without executing.

        Args:
            test_definition_id: Definition identifier.

        Returns:
            Execution plan with resolved configuration.
        """
        definition = await self.get(test_definition_id)
        if not definition:
            raise ValueError("Test definition not found")

        # Resolve to experiment config
        experiment_config = await self.resolve_to_experiment_config(definition)

        # Build plan
        plan = {
            "test_definition_id": definition.test_definition_id,
            "name": definition.name,
            "description": definition.description,
            "target": {
                "target_id": definition.target_id,
                "name": "TODO",  # Would load from TargetRecord
            },
            "benchmark": {
                "benchmark_id": definition.benchmark_id,
                "name": "TODO",  # Would load from BenchmarkRecord
            },
            "metric_config": {
                "metric_config_id": definition.metric_config_id,
                "name": "TODO",  # Would load from MetricConfigRecord
                "mode": "TODO",
                "metrics_count": len("TODO"),
            },
            "execution_config": definition.execution_config,
            "seed": definition.seed,
            "config_hash": definition.definition_hash,
            "tags": definition.tags,
            "experiment_config": experiment_config,
        }

        return plan
