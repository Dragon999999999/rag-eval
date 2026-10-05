"""Export and import services for the portable `.rzip` format."""

from __future__ import annotations

import json
from pathlib import PurePosixPath
from typing import Any
from uuid import uuid4

import yaml

from rag_eval.artifacts import ArtifactService
from rag_eval.bundles import (
    BundleImportResult,
    BundleReader,
    BundleWriter,
    benchmark_content_hash,
    redact_secret_refs,
    resolve_secret_placeholders,
)
from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.target_repository import TargetRepository
from rag_eval.db.test_models import (
    AggregateMetricResultRecord,
    AttemptRecord,
    CaseExecutionRecord,
    MetricResultRecord,
    MetricRunRecord,
    RunRecord,
)
from rag_eval.db.test_repository import TestRepository
from rag_eval.models import (
    Benchmark,
    BenchmarkCase,
    BenchmarkManifest,
    Document,
    TargetObservation,
)
from rag_eval.models.enums import ArtifactType
from rag_eval.services.benchmark_service import BenchmarkService
from rag_eval.services.target_service import TargetService
from rag_eval.services.test_service import TestService


def _jsonl(items: list[dict[str, Any]]) -> bytes:
    """Serialize records as deterministic UTF-8 JSON Lines."""
    return "".join(
        f"{json.dumps(item, sort_keys=True, ensure_ascii=False)}\n" for item in items
    ).encode("utf-8")


def _read_jsonl(data: bytes) -> list[dict[str, Any]]:
    """Parse JSON Lines while rejecting non-object records."""
    records: list[dict[str, Any]] = []
    for line in data.decode("utf-8").splitlines():
        if not line.strip():
            continue
        item = json.loads(line)
        if not isinstance(item, dict):
            raise ValueError("JSONL records must be mappings")
        records.append(item)
    return records


class BundleService:
    """Coordinate domain services with the format-only bundle primitives."""

    def __init__(
        self,
        *,
        target_service: TargetService,
        benchmark_service: BenchmarkService,
        test_service: TestService,
        target_repository: TargetRepository,
        benchmark_repository: BenchmarkRepository,
        test_repository: TestRepository,
        artifact_service: ArtifactService,
        tool_version: str = "development",
    ) -> None:
        self._target_service = target_service
        self._benchmark_service = benchmark_service
        self._test_service = test_service
        self._target_repository = target_repository
        self._benchmark_repository = benchmark_repository
        self._test_repository = test_repository
        self._artifact_service = artifact_service
        self._tool_version = tool_version

    async def export_target(self, target_id: str) -> bytes:
        """Export sanitized target YAML with secret placeholders."""
        yaml_text = await self._target_service.get_configuration_yaml(target_id)
        if yaml_text is None:
            raise KeyError(f"target is not configured: {target_id}")
        payload = yaml.safe_load(yaml_text) or {}
        writer = BundleWriter(
            kind="target",
            tool_version=self._tool_version,
            resources={"targets": [f"targets/{target_id}.yaml"]},
        )
        writer.add_yaml(
            f"targets/{target_id}.yaml",
            redact_secret_refs(payload),
        )
        return writer.build()

    async def export_benchmark(self, benchmark_id: str) -> bytes:
        """Export benchmark metadata, truth JSONL, chunks, and source bytes."""
        benchmark = await self._benchmark_service.get(benchmark_id)
        resources: dict[str, bytes] = {}
        cases_name = f"benchmarks/{benchmark_id}/cases.jsonl"
        resources[cases_name] = _jsonl(
            [case.model_dump(mode="json") for case in benchmark.cases]
        )
        if benchmark.chunks:
            resources[f"benchmarks/{benchmark_id}/chunks.jsonl"] = _jsonl(
                [chunk.model_dump(mode="json") for chunk in benchmark.chunks]
            )

        document_descriptors: list[dict[str, Any]] = []
        for document in benchmark.documents:
            descriptor = document.model_dump(mode="json", exclude={"artifact"})
            if document.artifact is not None:
                filename = document.filename or document.document_id
                path = f"benchmarks/{benchmark_id}/documents/{filename}"
                resources[path] = await self._artifact_service.get(document.artifact)
                descriptor["path"] = path
            document_descriptors.append(descriptor)

        manifest = benchmark.manifest.model_dump(mode="json")
        manifest["documents"] = document_descriptors
        manifest["content_hash"] = benchmark_content_hash(
            manifest,
            [case.model_dump(mode="json") for case in benchmark.cases],
            document_descriptors,
            [chunk.model_dump(mode="json") for chunk in benchmark.chunks],
        )
        writer = BundleWriter(
            kind="benchmark",
            tool_version=self._tool_version,
            resources={
                "benchmarks": [f"benchmarks/{benchmark_id}"],
            },
        )
        writer.add_yaml(f"benchmarks/{benchmark_id}/benchmark.yaml", manifest)
        for name, data in resources.items():
            writer.add_bytes(name, data)
        return writer.build()

    async def export_test(self, test_id: str, *, run_id: str | None = None) -> bytes:
        """Export canonical test configuration and optionally raw results."""
        test = await self._test_repository.get_test(test_id)
        if test is None:
            raise KeyError(f"test not found: {test_id}")
        selections = await self._test_repository.list_test_metric_selections(
            test_id,
            enabled_only=True,
        )
        selected = [
            {
                "id": item.metric_id,
                "version": item.metric_version or "1",
                "parameters": dict(item.parameters or {}),
            }
            for item in selections
        ]
        test_payload = {
            "schema_version": "1",
            "name": test.name,
            "description": test.description,
            "target": test.target_id,
            "benchmark": test.benchmark_id,
            "execution": dict(test.execution_config or {}),
            "seed": test.seed,
            "metrics": {
                "mode": test.metric_selection_mode,
                "selected": selected,
                "judge": redact_secret_refs(dict(test.judge_config or {})),
                "retrieval": dict(test.retrieval_config or {}),
            },
            "tags": list(test.tags or []),
            "metadata": dict(test.metadata_json or {}),
        }
        writer = BundleWriter(
            kind="test-with-results" if run_id else "test",
            tool_version=self._tool_version,
            resources={"tests": [test_id]},
        )
        writer.add_yaml(f"tests/{test_id}/test.yaml", test_payload)
        if run_id is not None:
            await self._add_run(writer, run_id, test_id)
        return writer.build()

    async def export_run(self, run_id: str) -> bytes:
        """Export the owning test configuration and one evaluation's results."""
        run = await self._test_repository.get_run(run_id)
        if run is None or run.test_definition_id is None:
            raise KeyError(f"run not found: {run_id}")
        return await self.export_test(run.test_definition_id, run_id=run_id)

    async def import_bundle(
        self,
        data: bytes,
        *,
        secrets: dict[str, str] | None = None,
    ) -> BundleImportResult:
        """Import configuration resources, remapping colliding IDs safely."""
        reader = BundleReader(data)
        secrets = secrets or {}
        created: list[dict[str, Any]] = []
        remapped: dict[str, str] = {}
        missing: list[str] = []

        for name in reader.names:
            if not name.startswith("benchmarks/") or not name.endswith(
                "/benchmark.yaml"
            ):
                continue
            old_id = PurePosixPath(name).parts[1]
            new_id = await self._import_benchmark(reader, old_id, remapped)
            created.append({"kind": "benchmark", "original_id": old_id, "id": new_id})

        for name in reader.names:
            if not name.startswith("targets/") or not name.endswith(".yaml"):
                continue
            old_id = PurePosixPath(name).stem
            target = await self._target_repository.get_target(old_id)
            new_id = old_id if target is None else f"tgt-{uuid4()}"
            payload = resolve_secret_placeholders(
                reader.read_yaml(name), secrets, _missing=missing
            )
            target_record = await self._target_service.create_target(
                old_id,
                target_id=new_id,
                metadata={"bundle_source_id": old_id, "secrets_pending": bool(missing)},
            )
            await self._target_service.save_configuration(
                target_record.target_id,
                yaml.safe_dump(payload, sort_keys=False),
            )
            remapped[old_id] = new_id
            created.append({"kind": "target", "original_id": old_id, "id": new_id})

        for name in reader.names:
            if not name.startswith("tests/") or not name.endswith("/test.yaml"):
                continue
            old_id = PurePosixPath(name).parts[1]
            payload = reader.read_yaml(name)
            payload["target"] = remapped.get(
                payload.get("target"), payload.get("target")
            )
            payload["benchmark"] = remapped.get(
                payload.get("benchmark"), payload.get("benchmark")
            )
            test = await self._test_service.create_test(
                name=str(payload.get("name") or old_id)
            )
            new_id = str(test["test_definition_id"])
            await self._test_service.import_test_yaml(
                new_id,
                yaml.safe_dump(payload, sort_keys=False),
            )
            await self._test_service.update_test(
                new_id,
                execution_config=dict(payload.get("execution") or {}),
                seed=payload.get("seed"),
                tags=list(payload.get("tags") or []),
                metadata=dict(payload.get("metadata") or {}),
            )
            remapped[old_id] = new_id
            created.append({"kind": "test", "original_id": old_id, "id": new_id})

        for name in reader.names:
            if not name.startswith("tests/") or "/runs/" not in name:
                continue
            if not name.endswith("/run.yaml"):
                continue
            old_test_id = PurePosixPath(name).parts[1]
            run_payload = reader.read_yaml(name)
            old_run_id = str(run_payload["run_id"])
            new_run_id = old_run_id
            if await self._test_repository.get_run(old_run_id) is not None:
                new_run_id = f"run-{uuid4()}"
            canonical_config = dict(run_payload.get("canonical_config") or {})
            run_record = RunRecord(
                run_id=new_run_id,
                name=str(run_payload.get("name") or old_run_id),
                status=str(run_payload.get("status") or "COMPLETED"),
                config_hash=str(run_payload.get("config_hash") or f"import-{uuid4()}"),
                target_id=remapped.get(
                    run_payload.get("target_id"), run_payload.get("target_id")
                ),
                benchmark_id=remapped.get(
                    run_payload.get("benchmark_id"), run_payload.get("benchmark_id")
                ),
                test_definition_id=remapped.get(old_test_id, old_test_id),
                tags=[],
                metadata_json={"bundle_source_id": old_run_id},
            )
            await self._test_repository.create_run(run_record, canonical_config)
            results_name = str(PurePosixPath(name).parent / "results.jsonl")
            if results_name in reader.names:
                await self._import_run_results(
                    reader,
                    results_name,
                    run_record,
                    remapped,
                )
            await self._import_metric_runs(
                reader,
                run_record,
                remapped,
                old_test_id,
            )
            remapped[old_run_id] = new_run_id
            created.append({"kind": "run", "original_id": old_run_id, "id": new_run_id})

        return BundleImportResult(
            created=created,
            remapped=remapped,
            secret_missing=sorted(set(missing)),
        )

    async def _import_run_results(
        self,
        reader: BundleReader,
        name: str,
        run: RunRecord,
        remapped: dict[str, str],
    ) -> None:
        """Recreate case executions, attempts, and durable observations."""
        for item in _read_jsonl(reader.read_bytes(name)):
            source_execution_id = str(item["case_execution_id"])
            execution_id = source_execution_id
            if await self._test_repository.get_case_execution(execution_id) is not None:
                execution_id = f"exec-{uuid4()}"
            execution = CaseExecutionRecord(
                case_execution_id=execution_id,
                run_id=run.run_id,
                case_id=remapped.get(str(item["case_id"]), str(item["case_id"])),
                status="COMPLETED",
                metadata_json={"bundle_source_id": source_execution_id},
            )
            await self._test_repository.create_case_execution(execution)
            attempts = item.get("attempts") or []
            for position, attempt_data in enumerate(attempts, start=1):
                attempt_id = str(attempt_data["attempt_id"])
                if await self._test_repository.get_attempt(attempt_id) is not None:
                    attempt_id = f"attempt-{uuid4()}"
                attempt = AttemptRecord(
                    attempt_id=attempt_id,
                    case_execution_id=execution_id,
                    attempt_number=position,
                    request_id=str(attempt_data["request_id"]),
                    status=str(attempt_data.get("status") or "SUCCEEDED"),
                    metadata_json={"bundle_source_id": str(attempt_data["attempt_id"])},
                )
                await self._test_repository.create_attempt(attempt)
            remapped[source_execution_id] = execution_id
            observation_payload = item.get("observation")
            if observation_payload is not None and attempts:
                observation = TargetObservation.model_validate(observation_payload)
                observation = observation.model_copy(
                    update={
                        "case_id": remapped.get(
                            observation.case_id,
                            observation.case_id,
                        )
                    }
                )
                await self._target_repository.persist_observation(
                    observation,
                    execution_id,
                    attempt_id,
                )

    async def _import_metric_runs(
        self,
        reader: BundleReader,
        run: RunRecord,
        remapped: dict[str, str],
        source_test_id: str,
    ) -> None:
        """Restore optional historical scoring passes and their derived rows."""
        prefix = f"tests/{source_test_id}/runs/"
        for name in reader.names:
            if not name.startswith(prefix) or not name.endswith("/metric_run.yaml"):
                continue
            metric_payload = reader.read_yaml(name)
            old_metric_run_id = str(metric_payload["metric_run_id"])
            metric_run_id = old_metric_run_id
            if await self._test_repository.get_metric_run(metric_run_id) is not None:
                metric_run_id = f"mr-{uuid4()}"
            metric_run = MetricRunRecord(
                metric_run_id=metric_run_id,
                run_id=run.run_id,
                name=str(metric_payload.get("name") or old_metric_run_id),
                status=str(metric_payload.get("status") or "COMPLETED"),
                config_snapshot=dict(metric_payload.get("config_snapshot") or {}),
                status_reason=metric_payload.get("status_reason"),
                started_at=metric_payload.get("started_at"),
                finished_at=metric_payload.get("finished_at"),
            )
            await self._test_repository.create_metric_run(metric_run)
            metric_dir = PurePosixPath(name).parent
            results_name = str(metric_dir / "metric_results.jsonl")
            if results_name in reader.names:
                for item in _read_jsonl(reader.read_bytes(results_name)):
                    case_execution_id = item.get("case_execution_id")
                    metric_result = MetricResultRecord(
                        metric_result_id=(
                            f"mr-{metric_run_id}-{item['metric_id']}-"
                            f"{item.get('case_id') or 'run'}-{item['metric_version']}"
                        ),
                        run_id=run.run_id,
                        metric_run_id=metric_run_id,
                        case_execution_id=remapped.get(
                            case_execution_id,
                            case_execution_id,
                        ),
                        case_id=item.get("case_id"),
                        metric_id=item["metric_id"],
                        metric_version=item["metric_version"],
                        value=item.get("value"),
                        status=item["status"],
                        reason=item.get("reason"),
                        details=dict(item.get("details") or {}),
                        payload=dict(item.get("payload") or {}),
                    )
                    self._test_repository._session.add(metric_result)
            aggregates_name = str(metric_dir / "aggregates.jsonl")
            if aggregates_name in reader.names:
                for item in _read_jsonl(reader.read_bytes(aggregates_name)):
                    aggregate = AggregateMetricResultRecord(
                        aggregate_metric_result_id=(
                            f"agr-{metric_run_id}-{item['metric_id']}-"
                            f"{item['aggregation']}-{item['metric_version']}"
                        ),
                        run_id=run.run_id,
                        metric_run_id=metric_run_id,
                        metric_id=item["metric_id"],
                        metric_version=item["metric_version"],
                        aggregation=item["aggregation"],
                        value=item.get("value"),
                        status=item["status"],
                        reason=item.get("reason"),
                        details=dict(item.get("details") or {}),
                    )
                    self._test_repository._session.add(aggregate)
            await self._test_repository._session.flush()
            remapped[old_metric_run_id] = metric_run_id

    async def _import_benchmark(
        self,
        reader: BundleReader,
        benchmark_id: str,
        remapped: dict[str, str],
    ) -> str:
        """Import one benchmark directory and its artifact-backed documents."""
        base = f"benchmarks/{benchmark_id}"
        manifest_payload = reader.read_yaml(f"{base}/benchmark.yaml")
        old_id = str(manifest_payload["benchmark_id"])
        new_id = old_id
        if await self._benchmark_repository.get_benchmark_manifest(old_id) is not None:
            new_id = f"benchmark-{uuid4()}"
        manifest_payload["benchmark_id"] = new_id
        document_payloads = manifest_payload.pop("documents", [])
        manifest = BenchmarkManifest.model_validate(manifest_payload)
        cases = [
            BenchmarkCase.model_validate(item)
            for item in _read_jsonl(reader.read_bytes(f"{base}/cases.jsonl"))
        ]
        for case in cases:
            original_case_id = case.case_id
            if await self._benchmark_repository.case_id_exists(original_case_id):
                case = case.model_copy(update={"case_id": f"case-{uuid4()}"})
            remapped[original_case_id] = case.case_id
        documents: list[Document] = []
        for item in document_payloads:
            path = item.pop("path", None)
            original_document_id = str(item["document_id"])
            document_id = original_document_id
            if await self._benchmark_repository.document_id_exists(document_id):
                document_id = f"document-{uuid4()}"
            remapped[original_document_id] = document_id
            artifact = None
            if path:
                bytes_data = reader.read_bytes(path)
                artifact = await self._artifact_service.put(
                    bytes_data,
                    ArtifactType.SOURCE_DOCUMENT,
                    content_type=item.get("mime_type"),
                    expected_sha256=item.get("sha256"),
                )
            documents.append(
                Document.model_validate(
                    {**item, "document_id": document_id, "artifact": artifact}
                )
            )
        cases = [
            case.model_copy(
                update={
                    "gold_evidence": [
                        evidence.model_copy(
                            update={
                                "document_id": remapped.get(
                                    evidence.document_id,
                                    evidence.document_id,
                                )
                            }
                        )
                        for evidence in case.gold_evidence
                    ]
                }
            )
            for case in cases
        ]
        chunks_name = f"{base}/chunks.jsonl"
        chunks = []
        if chunks_name in reader.names:
            from rag_eval.models import Chunk

            chunks = [
                Chunk.model_validate(item)
                for item in _read_jsonl(reader.read_bytes(chunks_name))
            ]
            chunks = [
                chunk.model_copy(
                    update={
                        "chunk_id": (
                            f"chunk-{uuid4()}"
                            if await self._benchmark_repository.chunk_id_exists(
                                chunk.chunk_id
                            )
                            else chunk.chunk_id
                        ),
                        "document_id": remapped.get(
                            chunk.document_id,
                            chunk.document_id,
                        ),
                    }
                )
                for chunk in chunks
            ]
        await self._benchmark_service.register(
            Benchmark(
                manifest=manifest,
                cases=cases,
                documents=documents,
                chunks=chunks,
            )
        )
        remapped[old_id] = new_id
        return new_id

    async def _add_run(
        self,
        writer: BundleWriter,
        run_id: str,
        test_id: str,
    ) -> None:
        """Add an evaluation snapshot and raw observations as JSONL."""
        run = await self._test_repository.get_run(run_id)
        config = await self._test_repository.get_run_config(run_id)
        if run is None or config is None or run.test_definition_id != test_id:
            raise KeyError(f"run not found for test: {run_id}")
        run_dir = f"tests/{test_id}/runs/{run_id}"
        writer.add_yaml(
            f"{run_dir}/run.yaml",
            {
                "run_id": run.run_id,
                "name": run.name,
                "status": run.status,
                "target_id": run.target_id,
                "benchmark_id": run.benchmark_id,
                "config_hash": run.config_hash,
                "canonical_config": config.canonical_config,
            },
        )
        observations: list[dict[str, Any]] = []
        for execution in await self._test_repository.list_case_executions(run_id):
            attempts = await self._test_repository.list_attempts(
                execution.case_execution_id
            )
            if not attempts:
                continue
            observation = await self._target_repository.get_observation_for_attempt(
                attempts[-1].attempt_id
            )
            observations.append(
                {
                    "case_execution_id": execution.case_execution_id,
                    "case_id": execution.case_id,
                    "observation": (
                        observation.model_dump(mode="json")
                        if observation is not None
                        else None
                    ),
                    "attempts": [
                        {
                            "attempt_id": attempt.attempt_id,
                            "request_id": attempt.request_id,
                            "status": attempt.status,
                        }
                        for attempt in attempts
                    ],
                }
            )
        writer.add_bytes(f"{run_dir}/results.jsonl", _jsonl(observations))
        for metric_run in await self._test_repository.list_metric_runs(run_id):
            metric_dir = f"{run_dir}/metric_runs/{metric_run.metric_run_id}"
            writer.add_yaml(
                f"{metric_dir}/metric_run.yaml",
                {
                    "metric_run_id": metric_run.metric_run_id,
                    "run_id": run_id,
                    "name": metric_run.name,
                    "status": metric_run.status,
                    "config_snapshot": metric_run.config_snapshot,
                    "status_reason": metric_run.status_reason,
                    "created_at": metric_run.created_at,
                    "started_at": metric_run.started_at,
                    "finished_at": metric_run.finished_at,
                },
            )
            metric_results = await self._test_repository.list_metric_results(
                run_id,
                metric_run_id=metric_run.metric_run_id,
            )
            writer.add_bytes(
                f"{metric_dir}/metric_results.jsonl",
                _jsonl(
                    [
                        {
                            "metric_result_id": item.metric_result_id,
                            "run_id": item.run_id,
                            "metric_run_id": item.metric_run_id,
                            "case_execution_id": item.case_execution_id,
                            "case_id": item.case_id,
                            "metric_id": item.metric_id,
                            "metric_version": item.metric_version,
                            "value": item.value,
                            "status": item.status,
                            "reason": item.reason,
                            "details": item.details,
                            "payload": item.payload,
                        }
                        for item in metric_results
                    ]
                ),
            )
            aggregates = await self._test_repository.list_aggregates(
                run_id,
                metric_run_id=metric_run.metric_run_id,
            )
            writer.add_bytes(
                f"{metric_dir}/aggregates.jsonl",
                _jsonl(
                    [
                        {
                            "aggregate_metric_result_id": (
                                item.aggregate_metric_result_id
                            ),
                            "run_id": item.run_id,
                            "metric_run_id": item.metric_run_id,
                            "metric_id": item.metric_id,
                            "metric_version": item.metric_version,
                            "aggregation": item.aggregation,
                            "value": item.value,
                            "status": item.status,
                            "reason": item.reason,
                            "details": item.details,
                        }
                        for item in aggregates
                    ]
                ),
            )
