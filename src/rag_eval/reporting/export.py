"""Portable Parquet export service.

Exports run data to PyArrow/Parquet files for offline analysis.
Includes:
- manifest.yaml (reproducibility metadata)
- config.yaml (redacted canonical config)
- summary.json (machine-readable summary)
- cases.parquet
- retrievals.parquet
- metrics.parquet
- traces.parquet (if available)
- errors.parquet (if available)

All exports are from persisted data only.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pyarrow as pa
import pyarrow.parquet as pq
import yaml

from rag_eval.db.benchmark_models import BenchmarkCaseRecord
from rag_eval.db.test_models import (
    AggregateMetricResultRecord,
    CaseExecutionRecord,
    ErrorRecordDB,
)
from rag_eval.db.test_repository import TestRepository


@dataclass
class ExportedRun:
    """Result of exporting a run."""

    run_id: str
    export_path: Path
    files: list[str]
    manifest: dict[str, Any]


class ExportService:
    """Export runs to portable Parquet format."""

    def __init__(self, repository: TestRepository, output_dir: Path) -> None:
        """Initialize export service.

        Args:
            repository: Repository for data access.
            output_dir: Base directory for exports.
        """
        self._repository = repository
        self._output_dir = output_dir
        self._output_dir.mkdir(parents=True, exist_ok=True)

    async def export_run(self, run_id: str) -> ExportedRun:
        """Export a complete run to Parquet files.

        Args:
            run_id: Run identifier.

        Returns:
            Exported run metadata.
        """
        # Create export directory
        export_path = self._output_dir / run_id
        export_path.mkdir(parents=True, exist_ok=True)

        # Load run data
        run = await self._repository.get_run(run_id)
        if run is None:
            raise KeyError(f"Run {run_id} not found")

        config = await self._repository.get_run_config(run_id)
        case_executions = await self._repository.list_case_executions(run_id)
        aggregates = await self._repository.list_aggregates(run_id)

        files = []

        # Export manifest
        manifest = self._create_manifest(run, config)
        manifest_path = export_path / "manifest.yaml"
        with open(manifest_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(manifest, f, default_flow_style=False)
        files.append("manifest.yaml")

        # Export redacted config
        if config:
            redacted_config = self._redact_config(config.canonical_config)
            config_path = export_path / "config.yaml"
            with open(config_path, "w", encoding="utf-8") as f:
                yaml.safe_dump(redacted_config, f, default_flow_style=False)
            files.append("config.yaml")

        # Export summary
        summary = self._create_summary(run, case_executions, aggregates)
        summary_path = export_path / "summary.json"
        with open(summary_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)
        files.append("summary.json")

        # Export cases
        cases_path = export_path / "cases.parquet"
        await self._export_cases(run_id, case_executions, cases_path)
        files.append("cases.parquet")

        # Export metrics
        metrics_path = export_path / "metrics.parquet"
        await self._export_metrics(run_id, metrics_path)
        files.append("metrics.parquet")

        # Export retrievals (if available)
        retrievals_path = export_path / "retrievals.parquet"
        retrievals_exported = await self._export_retrievals(run_id, retrievals_path)
        if retrievals_exported:
            files.append("retrievals.parquet")

        # Export traces (if available)
        traces_path = export_path / "traces.parquet"
        traces_exported = await self._export_traces(run_id, traces_path)
        if traces_exported:
            files.append("traces.parquet")

        # Export errors (if available)
        errors_path = export_path / "errors.parquet"
        errors_exported = await self._export_errors(run_id, errors_path)
        if errors_exported:
            files.append("errors.parquet")

        return ExportedRun(
            run_id=run_id,
            export_path=export_path,
            files=files,
            manifest=manifest,
        )

    def _create_manifest(self, run: Any, config: Any | None) -> dict[str, Any]:
        """Create reproducibility manifest."""
        import rag_eval

        manifest = {
            "run_id": run.run_id,
            "rag_eval_version": getattr(rag_eval, "__version__", "unknown"),
            "target_id": run.target_id,
            "benchmark_name": None,
            "benchmark_version": None,
            "corpus_hash": None,
            "config_hash": run.config_hash,
            "metric_versions": {},
            "seed": run.seed,
            "created_at": run.created_at.isoformat() if run.created_at else None,
            "started_at": run.started_at.isoformat() if run.started_at else None,
            "finished_at": run.finished_at.isoformat() if run.finished_at else None,
        }

        # Extract benchmark info from config
        if config:
            dataset = config.canonical_config.get("dataset", {})
            manifest["benchmark_name"] = dataset.get("name")
            manifest["benchmark_version"] = dataset.get("version")

            corpus = config.canonical_config.get("target", {}).get("corpus", {})
            manifest["corpus_hash"] = corpus.get("content_hash")

        return manifest

    def _redact_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Redact secrets from config."""
        redacted = json.loads(json.dumps(config))  # Deep copy

        # Redact common secret patterns
        self._redact_dict(redacted)

        return redacted

    def _redact_dict(self, d: dict[str, Any]) -> None:
        """Recursively redact sensitive fields."""
        secret_keys = {
            "api_key",
            "api_key_file",
            "token",
            "password",
            "secret",
            "credential",
            "auth",
        }

        for key in list(d.keys()):
            key_lower = key.lower()
            if any(s in key_lower for s in secret_keys):
                d[key] = "[REDACTED]"
            elif isinstance(d[key], dict):
                self._redact_dict(d[key])
            elif isinstance(d[key], list):
                for item in d[key]:
                    if isinstance(item, dict):
                        self._redact_dict(item)

    def _create_summary(
        self,
        run: Any,
        case_executions: Sequence[CaseExecutionRecord],
        aggregates: Sequence[AggregateMetricResultRecord],
    ) -> dict[str, Any]:
        """Create machine-readable summary."""
        total = len(case_executions)
        complete = sum(1 for c in case_executions if c.status == "COMPLETE")
        failed = sum(1 for c in case_executions if c.status == "FAILED")
        pending = sum(1 for c in case_executions if c.status == "PENDING")

        # Organize aggregates
        metrics_summary = {}
        for agg in aggregates:
            key = f"{agg.metric_id}.{agg.aggregation}"
            metrics_summary[key] = {
                "value": agg.value,
                "available_count": agg.details.get(
                    "available_count", agg.details.get("computed_count")
                ),
                "sample_count": agg.details.get("sample_count"),
            }

        return {
            "run_id": run.run_id,
            "run_name": run.name,
            "status": run.status,
            "target_id": run.target_id,
            "case_counts": {
                "total": total,
                "complete": complete,
                "failed": failed,
                "pending": pending,
            },
            "metrics": metrics_summary,
        }

    async def _export_cases(
        self, run_id: str, case_executions: Sequence[CaseExecutionRecord], path: Path
    ) -> None:
        """Export cases to Parquet."""
        # Load case details
        cases = []

        for case_exec in case_executions:
            case_record = await self._repository._session.get(
                BenchmarkCaseRecord, case_exec.case_id
            )
            if case_record:
                cases.append(
                    {
                        "run_id": run_id,
                        "case_id": case_exec.case_id,
                        "case_execution_id": case_exec.case_execution_id,
                        "status": case_exec.status,
                        "query": case_record.query,
                        "reference_answer": case_record.reference_answer,
                        "attempt_count": len(
                            await self._repository.list_attempts(
                                case_exec.case_execution_id
                            )
                        ),
                    }
                )

        if cases:
            table = pa.Table.from_pylist(cases)
            pq.write_table(table, path, compression="snappy")

    async def _export_metrics(self, run_id: str, path: Path) -> None:
        """Export metric results to Parquet."""
        metrics = await self._repository.list_metric_results(run_id)

        rows = []
        for m in metrics:
            rows.append(
                {
                    "run_id": run_id,
                    "case_id": m.case_id,
                    "metric_result_id": m.metric_result_id,
                    "metric_id": m.metric_id,
                    "metric_version": m.metric_version,
                    "status": m.status,
                    "value": m.value,
                    "reason": m.reason,
                }
            )

        if rows:
            table = pa.Table.from_pylist(rows)
            pq.write_table(table, path, compression="snappy")

    async def _export_retrievals(self, run_id: str, path: Path) -> bool:
        """Export retrieval results to Parquet.

        Returns True if any retrievals were exported.
        """
        # This would require loading retrieval data from observations
        # For now, skip if not implemented
        return False

    async def _export_traces(self, run_id: str, path: Path) -> bool:
        """Export trace spans to Parquet.

        Returns True if any traces were exported.
        """
        # This would require loading trace data from observations
        # For now, skip if not implemented
        return False

    async def _export_errors(self, run_id: str, path: Path) -> bool:
        """Export error records to Parquet.

        Returns True if any errors were exported.
        """
        # Query error records for this run
        from sqlalchemy import select

        stmt = select(ErrorRecordDB).where(ErrorRecordDB.run_id == run_id)
        result = await self._repository._session.execute(stmt)
        error_records = result.scalars().all()

        if not error_records:
            return False

        case_executions = await self._repository.list_case_executions(run_id)
        case_ids = {case.case_execution_id: case.case_id for case in case_executions}
        rows = []
        for err in error_records:
            rows.append(
                {
                    "run_id": run_id,
                    "case_id": (
                        case_ids.get(err.case_execution_id)
                        if err.case_execution_id is not None
                        else None
                    ),
                    "attempt_id": err.attempt_id,
                    "error_id": err.error_id,
                    "category": err.category,
                    "code": err.code,
                    "message": err.message,
                    "stage": err.stage,
                    "retryable": err.retryable,
                    "http_status": err.http_status,
                    "provider_code": err.provider.get("code"),
                    "timestamp": err.created_at.isoformat(),
                }
            )

        table = pa.Table.from_pylist(rows)
        pq.write_table(table, path, compression="snappy")
        return True
