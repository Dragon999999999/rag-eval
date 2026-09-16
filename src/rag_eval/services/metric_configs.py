"""Service for managing reusable metric configurations.

Handles CRUD operations for MetricConfigRecord and validates against
the metric registry.
"""

import hashlib
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.models import MetricConfigRecord
from rag_eval.metrics.registry import MetricRegistry


class MetricConfigService:
    """Service for managing metric configurations.

    A MetricConfig represents a reusable named configuration of metrics,
    including which metrics to run, their parameters, judge configuration,
    and retrieval stage settings.
    """

    def __init__(
        self,
        session: AsyncSession,
        metric_registry: MetricRegistry | None = None,
    ) -> None:
        """Initialize with database session and optional metric registry.

        Args:
            session: Async database session.
            metric_registry: Optional metric registry for validation.
        """
        self._session = session
        self._metric_registry = metric_registry or MetricRegistry()

    def _compute_config_hash(self, config: dict[str, Any]) -> str:
        """Compute deterministic hash of metric configuration.

        Args:
            config: Canonical configuration dictionary.

        Returns:
            SHA-256 hex digest of canonical JSON representation.
        """
        canonical = json.dumps(config, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(canonical.encode()).hexdigest()

    async def create(
        self,
        name: str,
        mode: str,
        selected_metrics: list[str] | None = None,
        metric_parameters: dict[str, Any] | None = None,
        judge_config: dict[str, Any] | None = None,
        retrieval_config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MetricConfigRecord:
        """Create a new metric configuration.

        Args:
            name: Human-readable name for the configuration.
            mode: Selection mode ('all_available' or 'explicit').
            selected_metrics: List of metric IDs to run (for explicit mode).
            metric_parameters: Per-metric parameter overrides.
            judge_config: Judge model configuration.
            retrieval_config: Retrieval stage configuration (k values, etc.).
            metadata: Additional metadata.

        Returns:
            Created MetricConfigRecord.

        Raises:
            ValueError: If mode is 'explicit' but no metrics selected.
            KeyError: If referenced metrics not in registry.
        """
        # Validate configuration
        if mode == "explicit":
            if not selected_metrics:
                raise ValueError(
                    "explicit mode requires at least one selected metric"
                )
            # Validate metrics exist in registry
            for metric_id in selected_metrics:
                # Check if metric exists (ignore version for now)
                if not any(
                    m.definition.metric_id == metric_id
                    for m in self._metric_registry._metrics.values()
                ):
                    raise KeyError(
                        f"Metric '{metric_id}' not found in registry"
                    )

        # Build canonical config for hashing
        canonical_config = {
            "mode": mode,
            "selected_metrics": selected_metrics or [],
            "metric_parameters": metric_parameters or {},
            "judge_config": judge_config or {},
            "retrieval_config": retrieval_config or {},
        }

        config_hash = self._compute_config_hash(canonical_config)

        # Create record
        record = MetricConfigRecord(
            metric_config_id=f"mc-{name.lower().replace(' ', '-')}",
            name=name,
            mode=mode,
            selected_metrics=selected_metrics or [],
            metric_parameters=metric_parameters or {},
            judge_config=judge_config or {},
            retrieval_config=retrieval_config or {},
            metadata_json=metadata or {},
            config_hash=config_hash,
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def get(self, metric_config_id: str) -> MetricConfigRecord | None:
        """Get a metric configuration by ID.

        Args:
            metric_config_id: Configuration identifier.

        Returns:
            MetricConfigRecord if found, None otherwise.
        """
        result = await self._session.execute(
            select(MetricConfigRecord).where(
                MetricConfigRecord.metric_config_id == metric_config_id
            )
        )
        return result.scalar_one_or_none()

    async def list(self, limit: int = 100, offset: int = 0) -> list[MetricConfigRecord]:
        """List metric configurations with pagination.

        Args:
            limit: Maximum number of records to return.
            offset: Number of records to skip.

        Returns:
            List of MetricConfigRecord.
        """
        result = await self._session.execute(
            select(MetricConfigRecord)
            .order_by(MetricConfigRecord.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update(
        self,
        metric_config_id: str,
        name: str | None = None,
        mode: str | None = None,
        selected_metrics: list[str] | None = None,
        metric_parameters: dict[str, Any] | None = None,
        judge_config: dict[str, Any] | None = None,
        retrieval_config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> MetricConfigRecord | None:
        """Update an existing metric configuration.

        Args:
            metric_config_id: Configuration identifier.
            name: New name (optional).
            mode: New mode (optional).
            selected_metrics: New selected metrics (optional).
            metric_parameters: New metric parameters (optional).
            judge_config: New judge configuration (optional).
            retrieval_config: New retrieval configuration (optional).
            metadata: New metadata (optional).

        Returns:
            Updated MetricConfigRecord if found, None otherwise.

        Raises:
            ValueError: If updated configuration is invalid.
            KeyError: If referenced metrics not in registry.
        """
        record = await self.get(metric_config_id)
        if not record:
            return None

        # Update fields
        if name is not None:
            record.name = name
        if mode is not None:
            record.mode = mode
        if selected_metrics is not None:
            record.selected_metrics = selected_metrics
        if metric_parameters is not None:
            record.metric_parameters = metric_parameters
        if judge_config is not None:
            record.judge_config = judge_config
        if retrieval_config is not None:
            record.retrieval_config = retrieval_config
        if metadata is not None:
            record.metadata_json = metadata

        # Recompute hash
        canonical_config = {
            "mode": record.mode,
            "selected_metrics": record.selected_metrics,
            "metric_parameters": record.metric_parameters,
            "judge_config": record.judge_config,
            "retrieval_config": record.retrieval_config,
        }
        record.config_hash = self._compute_config_hash(canonical_config)

        await self._session.flush()
        return record

    async def delete(self, metric_config_id: str) -> bool:
        """Delete a metric configuration.

        Args:
            metric_config_id: Configuration identifier.

        Returns:
            True if deleted, False if not found.
        """
        record = await self.get(metric_config_id)
        if not record:
            return False

        await self._session.delete(record)
        await self._session.flush()
        return True

    async def get_or_create(
        self,
        name: str,
        mode: str,
        selected_metrics: list[str] | None = None,
        metric_parameters: dict[str, Any] | None = None,
        judge_config: dict[str, Any] | None = None,
        retrieval_config: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[MetricConfigRecord, bool]:
        """Get existing configuration or create new one.

        Uses config hash to detect duplicates.

        Args:
            name: Configuration name.
            mode: Selection mode.
            selected_metrics: Selected metric IDs.
            metric_parameters: Metric parameters.
            judge_config: Judge configuration.
            retrieval_config: Retrieval configuration.
            metadata: Additional metadata.

        Returns:
            Tuple of (MetricConfigRecord, created_flag).
        """
        # Build canonical config
        canonical_config = {
            "mode": mode,
            "selected_metrics": selected_metrics or [],
            "metric_parameters": metric_parameters or {},
            "judge_config": judge_config or {},
            "retrieval_config": retrieval_config or {},
        }
        config_hash = self._compute_config_hash(canonical_config)

        # Check for existing with same hash
        result = await self._session.execute(
            select(MetricConfigRecord).where(
                MetricConfigRecord.config_hash == config_hash
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            return existing, False

        # Create new
        new_config = await self.create(
            name=name,
            mode=mode,
            selected_metrics=selected_metrics,
            metric_parameters=metric_parameters,
            judge_config=judge_config,
            retrieval_config=retrieval_config,
            metadata=metadata,
        )
        return new_config, True
