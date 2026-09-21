"""Focused async repositories for durable application persistence."""

import hashlib
import json
from collections.abc import Mapping, Sequence
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.models import (
    AggregateMetricResultRecord,
    ArtifactRecord,
    AttemptRecord,
    BenchmarkCaseRecord,
    BenchmarkChunkRecord,
    BenchmarkDocumentRecord,
    BenchmarkRecord,
    CaseExecutionRecord,
    CorpusRecord,
    DocumentRecord,
    ErrorRecordDB,
    MetricResultRecord,
    RunConfigRecord,
    RunRecord,
    TargetCapabilityRecord,
    TargetObservationRecord,
    TargetRecord,
)
from rag_eval.models import (
    ArtifactRef,
    Benchmark,
    BenchmarkCase,
    BenchmarkManifest,
    Chunk,
    CorpusMode,
    Document,
    ErrorRecord,
    MetricResult,
    TargetCapabilities,
    TargetInfo,
    TargetObservation,
)
from rag_eval.models.metrics import AggregateMetricResult


def _payload_hash(payload: Mapping[str, Any]) -> str:
    """Hash canonical JSON payload content for durable integrity checks."""
    encoded = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


class PersistenceRepository:
    """Explicit database operations with caller-managed transaction scope."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to one caller-managed async session."""
        self._session = session

    # -------------------------------------------------------------------------
    # Benchmarks
    # -------------------------------------------------------------------------

    async def persist_benchmark(
        self,
        manifest: BenchmarkManifest,
    ) -> BenchmarkRecord:
        """Create or update canonical benchmark identity metadata."""
        record = await self._session.get(
            BenchmarkRecord,
            manifest.benchmark_id,
        )

        values = {
            "name": manifest.name,
            "version": manifest.version,
            "schema_version": manifest.schema_version,
            "corpus_mode": manifest.corpus_mode.value,
            "content_hash": manifest.content_hash,
            "corpus_id": manifest.corpus_id,
            "source": manifest.source,
            "tags": manifest.tags,
            "metadata_json": manifest.metadata,
        }

        if record is None:
            record = BenchmarkRecord(
                benchmark_id=manifest.benchmark_id,
                created_at=manifest.created_at,
                **values,
            )
            self._session.add(record)
        else:
            for name, value in values.items():
                setattr(record, name, value)

            if manifest.created_at is not None:
                record.created_at = manifest.created_at

        await self._session.flush()
        return record

    async def get_benchmark(
        self,
        benchmark_id: str,
    ) -> Benchmark | None:
        """Load and reconstruct one complete canonical benchmark."""
        record = await self._session.get(
            BenchmarkRecord,
            benchmark_id,
        )

        if record is None:
            return None

        manifest = BenchmarkManifest(
            benchmark_id=record.benchmark_id,
            name=record.name,
            version=record.version,
            schema_version=record.schema_version,
            corpus_mode=CorpusMode(record.corpus_mode),
            content_hash=record.content_hash,
            corpus_id=record.corpus_id,
            created_at=record.created_at,
            source=record.source,
            tags=list(record.tags or []),
            metadata=dict(record.metadata_json or {}),
        )

        cases = await self.list_benchmark_cases(benchmark_id)
        documents = await self.list_benchmark_documents(benchmark_id)
        chunks = await self.list_benchmark_chunks(benchmark_id)

        return Benchmark(
            manifest=manifest,
            cases=list(cases),
            documents=list(documents),
            chunks=list(chunks),
        )

    async def list_benchmarks(
        self,
    ) -> Sequence[BenchmarkRecord]:
        """List persisted benchmark identities."""
        result = await self._session.scalars(
            select(BenchmarkRecord).order_by(
                BenchmarkRecord.name,
                BenchmarkRecord.benchmark_id,
            )
        )
        return result.all()

    async def persist_benchmark_case(
        self,
        benchmark_id: str,
        case: BenchmarkCase,
    ) -> BenchmarkCaseRecord:
        """Persist evaluator-owned benchmark truth."""
        record = await self._session.get(
            BenchmarkCaseRecord,
            case.case_id,
        )

        values = {
            "benchmark_id": benchmark_id,
            "query": case.query,
            "history": [
                item.model_dump(mode="json")
                for item in case.history
            ],
            "reference_answer": case.reference_answer,
            "gold_evidence": [
                item.model_dump(mode="json")
                for item in case.gold_evidence
            ],
            "answerability": (
                case.answerability.value
                if case.answerability is not None
                else None
            ),
            "tags": case.tags,
            "metadata_json": {
                **case.metadata,
                "difficulty": case.difficulty,
                "language": case.language,
            },
        }

        if record is None:
            record = BenchmarkCaseRecord(
                case_id=case.case_id,
                **values,
            )
            self._session.add(record)
        else:
            if record.benchmark_id != benchmark_id:
                raise ValueError(
                    f"case {case.case_id} already belongs to benchmark "
                    f"{record.benchmark_id}"
                )

            for name, value in values.items():
                setattr(record, name, value)

        await self._session.flush()
        return record

    async def list_benchmark_cases(
        self,
        benchmark_id: str,
    ) -> Sequence[BenchmarkCase]:
        """Load all canonical cases belonging to a benchmark."""
        result = await self._session.scalars(
            select(BenchmarkCaseRecord)
            .where(
                BenchmarkCaseRecord.benchmark_id == benchmark_id
            )
            .order_by(BenchmarkCaseRecord.case_id)
        )

        cases: list[BenchmarkCase] = []

        for record in result.all():
            metadata = dict(record.metadata_json or {})

            difficulty = metadata.pop("difficulty", None)
            language = metadata.pop("language", None)

            cases.append(
                BenchmarkCase.model_validate(
                    {
                        "case_id": record.case_id,
                        "query": record.query,
                        "history": record.history or [],
                        "reference_answer": record.reference_answer,
                        "gold_evidence": record.gold_evidence or [],
                        "answerability": record.answerability,
                        "tags": record.tags or [],
                        "difficulty": difficulty,
                        "language": language,
                        "metadata": metadata,
                    }
                )
            )

        return cases

    async def persist_benchmark_document(
        self,
        benchmark_id: str,
        document: Document,
    ) -> BenchmarkDocumentRecord:
        """Persist an evaluator-owned source document for a benchmark."""
        record = await self._session.get(
            BenchmarkDocumentRecord,
            document.document_id,
        )

        values = {
            "benchmark_id": benchmark_id,
            "filename": document.filename,
            "mime_type": document.mime_type,
            "sha256": document.sha256,
            "size_bytes": document.size_bytes,
            "artifact_id": (
                document.artifact.artifact_id
                if document.artifact is not None
                else None
            ),
            "metadata_json": document.metadata,
        }

        if record is None:
            record = BenchmarkDocumentRecord(
                document_id=document.document_id,
                **values,
            )
            self._session.add(record)
        else:
            if record.benchmark_id != benchmark_id:
                raise ValueError(
                    f"document {document.document_id} already belongs to "
                    f"benchmark {record.benchmark_id}"
                )

            for name, value in values.items():
                setattr(record, name, value)

        await self._session.flush()
        return record

    async def list_benchmark_documents(
        self,
        benchmark_id: str,
    ) -> Sequence[Document]:
        """Load all source documents belonging to a benchmark."""
        result = await self._session.scalars(
            select(BenchmarkDocumentRecord)
            .where(
                BenchmarkDocumentRecord.benchmark_id == benchmark_id
            )
            .order_by(BenchmarkDocumentRecord.document_id)
        )

        documents: list[Document] = []

        for record in result.all():
            artifact = None

            if record.artifact_id is not None:
                artifact = await self.get_artifact(record.artifact_id)

                if artifact is None:
                    raise ValueError(
                        f"artifact {record.artifact_id} referenced by "
                        f"document {record.document_id} does not exist"
                    )

            documents.append(
                Document(
                    document_id=record.document_id,
                    filename=record.filename,
                    mime_type=record.mime_type,
                    sha256=record.sha256,
                    size_bytes=record.size_bytes,
                    artifact=artifact,
                    metadata=dict(record.metadata_json or {}),
                )
            )

        return documents

    async def persist_benchmark_chunk(
        self,
        benchmark_id: str,
        chunk: Chunk,
    ) -> BenchmarkChunkRecord:
        """Persist one evaluator-owned canonical benchmark chunk."""
        record = await self._session.get(
            BenchmarkChunkRecord,
            chunk.chunk_id,
        )

        values = {
            "benchmark_id": benchmark_id,
            "document_id": chunk.document_id,
            "text": chunk.text,
            "location": (
                chunk.location.model_dump(mode="json")
                if chunk.location is not None
                else None
            ),
            "metadata_json": chunk.metadata,
        }

        if record is None:
            record = BenchmarkChunkRecord(
                chunk_id=chunk.chunk_id,
                **values,
            )
            self._session.add(record)
        else:
            if record.benchmark_id != benchmark_id:
                raise ValueError(
                    f"chunk {chunk.chunk_id} already belongs to benchmark "
                    f"{record.benchmark_id}"
                )

            for name, value in values.items():
                setattr(record, name, value)

        await self._session.flush()
        return record

    async def list_benchmark_chunks(
        self,
        benchmark_id: str,
    ) -> Sequence[Chunk]:
        """Load all canonical chunks belonging to a benchmark."""
        result = await self._session.scalars(
            select(BenchmarkChunkRecord)
            .where(
                BenchmarkChunkRecord.benchmark_id == benchmark_id
            )
            .order_by(BenchmarkChunkRecord.chunk_id)
        )

        return [
            Chunk.model_validate(
                {
                    "chunk_id": record.chunk_id,
                    "document_id": record.document_id,
                    "text": record.text,
                    "location": record.location,
                    "metadata": dict(record.metadata_json or {}),
                }
            )
            for record in result.all()
        ]

    # -------------------------------------------------------------------------
    # Targets
    # -------------------------------------------------------------------------

    async def persist_target(
        self,
        target_id: str,
        target: TargetInfo,
    ) -> TargetRecord:
        """Create or update stable target identity metadata."""
        record = await self._session.get(
            TargetRecord,
            target_id,
        )

        if record is None:
            record = TargetRecord(
                target_id=target_id,
                name=target.name,
                version=target.version,
                implementation=target.implementation,
                metadata_json=target.metadata,
            )
            self._session.add(record)
        else:
            record.name = target.name
            record.version = target.version
            record.implementation = target.implementation
            record.metadata_json = target.metadata

        await self._session.flush()
        return record

    async def persist_capabilities(
        self,
        target_id: str,
        capabilities: TargetCapabilities,
    ) -> TargetCapabilityRecord:
        """Persist latest canonical target capabilities."""
        record = await self._session.get(
            TargetCapabilityRecord,
            target_id,
        )

        payload = capabilities.model_dump(mode="json")

        if record is None:
            record = TargetCapabilityRecord(
                target_id=target_id,
                payload=payload,
            )
            self._session.add(record)
        else:
            record.payload = payload

        await self._session.flush()
        return record

    # -------------------------------------------------------------------------
    # Prepared target corpora
    # -------------------------------------------------------------------------

    async def persist_corpus(
        self,
        record: CorpusRecord,
    ) -> CorpusRecord:
        """Persist target corpus identity and current preparation state."""
        existing = await self._session.get(
            CorpusRecord,
            record.corpus_id,
        )

        if existing is None:
            self._session.add(record)
        else:
            existing.target_id = record.target_id
            existing.mode = record.mode
            existing.status = record.status
            existing.content_hash = record.content_hash
            existing.metadata_json = record.metadata_json
            record = existing

        await self._session.flush()
        return record

    async def persist_document(
        self,
        corpus_id: str,
        document: Document,
    ) -> DocumentRecord:
        """Persist a document uploaded into a target corpus.

        This is deliberately separate from persist_benchmark_document().
        """
        record = await self._session.get(
            DocumentRecord,
            document.document_id,
        )

        values = {
            "corpus_id": corpus_id,
            "filename": document.filename,
            "mime_type": document.mime_type,
            "sha256": document.sha256,
            "size_bytes": document.size_bytes,
            "artifact_id": (
                document.artifact.artifact_id
                if document.artifact is not None
                else None
            ),
            "metadata_json": document.metadata,
        }

        if record is None:
            record = DocumentRecord(
                document_id=document.document_id,
                **values,
            )
            self._session.add(record)
        else:
            for name, value in values.items():
                setattr(record, name, value)

        await self._session.flush()
        return record

    # -------------------------------------------------------------------------
    # Runs
    # -------------------------------------------------------------------------

    async def create_run(
        self,
        run: RunRecord,
        canonical_config: Mapping[str, Any],
    ) -> RunRecord:
        """Persist a run and immutable canonical configuration identity."""
        config = RunConfigRecord(
            config_hash=run.config_hash,
            canonical_config=dict(canonical_config),
        )

        existing = await self._session.get(
            RunConfigRecord,
            run.config_hash,
        )

        if existing is None:
            self._session.add(config)
        elif existing.canonical_config != canonical_config:
            raise ValueError(
                "config_hash already exists with different "
                "canonical configuration"
            )

        self._session.add(run)
        await self._session.flush()

        return run

    async def get_run(
        self,
        run_id: str,
    ) -> RunRecord | None:
        """Retrieve one run by durable identity."""
        return await self._session.get(
            RunRecord,
            run_id,
        )

    async def update_run_status(
        self,
        run_id: str,
        status: str,
    ) -> RunRecord:
        """Update mutable runtime state without modifying configuration."""
        run = await self._session.get(
            RunRecord,
            run_id,
        )

        if run is None:
            raise KeyError(f"run not found: {run_id}")

        run.status = status

        await self._session.flush()
        return run

    async def get_run_config(
        self,
        run_id: str,
    ) -> RunConfigRecord | None:
        """Get canonical configuration associated with one run."""
        run = await self._session.get(
            RunRecord,
            run_id,
        )

        if run is None:
            return None

        return await self._session.get(
            RunConfigRecord,
            run.config_hash,
        )

    # -------------------------------------------------------------------------
    # Case execution / attempts
    # -------------------------------------------------------------------------

    async def create_case_execution(
        self,
        record: CaseExecutionRecord,
    ) -> CaseExecutionRecord:
        """Register one logical run/case execution."""
        self._session.add(record)
        await self._session.flush()

        return record

    async def list_case_executions(
        self,
        run_id: str,
    ) -> Sequence[CaseExecutionRecord]:
        """List case executions in deterministic identity order."""
        result = await self._session.scalars(
            select(CaseExecutionRecord)
            .where(CaseExecutionRecord.run_id == run_id)
            .order_by(CaseExecutionRecord.case_execution_id)
        )

        return result.all()

    async def create_attempt(
        self,
        record: AttemptRecord,
    ) -> AttemptRecord:
        """Append a new execution attempt."""
        self._session.add(record)
        await self._session.flush()

        return record

    async def update_attempt_status(
        self,
        attempt_id: str,
        status: str,
    ) -> AttemptRecord:
        """Update the lifecycle state of an existing attempt."""
        attempt = await self._session.get(
            AttemptRecord,
            attempt_id,
        )

        if attempt is None:
            raise KeyError(f"attempt not found: {attempt_id}")

        attempt.status = status

        await self._session.flush()
        return attempt

    async def list_attempts(
        self,
        case_execution_id: str,
    ) -> Sequence[AttemptRecord]:
        """List execution attempts by deterministic attempt number."""
        result = await self._session.scalars(
            select(AttemptRecord)
            .where(
                AttemptRecord.case_execution_id == case_execution_id
            )
            .order_by(AttemptRecord.attempt_number)
        )

        return result.all()

    # -------------------------------------------------------------------------
    # Target observations
    # -------------------------------------------------------------------------

    async def persist_observation(
        self,
        observation: TargetObservation,
        case_execution_id: str,
        attempt_id: str,
    ) -> TargetObservationRecord:
        """Persist a normalized target observation."""
        payload = observation.model_dump(mode="json")

        record = TargetObservationRecord(
            observation_id=observation.observation_id,
            request_id=observation.request_id,
            case_execution_id=case_execution_id,
            attempt_id=attempt_id,
            normalization_version=observation.normalization_version,
            payload=payload,
            payload_hash=_payload_hash(payload),
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def get_observation(
        self,
        observation_id: str,
    ) -> TargetObservation | None:
        """Reload one observation through canonical validation."""
        record = await self._session.get(
            TargetObservationRecord,
            observation_id,
        )

        if record is None:
            return None

        return TargetObservation.model_validate(
            record.payload
        )

    # -------------------------------------------------------------------------
    # Artifacts
    # -------------------------------------------------------------------------

    async def persist_artifact(
        self,
        artifact: ArtifactRef,
        artifact_type: str,
    ) -> ArtifactRecord:
        """Persist artifact metadata without duplicating stored bytes."""
        record = await self._session.get(
            ArtifactRecord,
            artifact.artifact_id,
        )

        values = {
            "artifact_type": artifact_type,
            "uri": artifact.uri,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "content_type": artifact.content_type,
            "metadata_json": artifact.metadata,
        }

        if record is None:
            record = ArtifactRecord(
                artifact_id=artifact.artifact_id,
                **values,
            )
            self._session.add(record)
        else:
            for name, value in values.items():
                setattr(record, name, value)

        await self._session.flush()
        return record

    async def get_artifact(
        self,
        artifact_id: str,
    ) -> ArtifactRef | None:
        """Reload artifact metadata as a canonical reference."""
        record = await self._session.get(
            ArtifactRecord,
            artifact_id,
        )

        if record is None:
            return None

        return ArtifactRef(
            artifact_id=record.artifact_id,
            uri=record.uri,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            content_type=record.content_type,
            created_at=record.created_at,
            metadata=dict(record.metadata_json or {}),
        )

    # -------------------------------------------------------------------------
    # Metrics
    # -------------------------------------------------------------------------

    async def persist_metric(
        self,
        metric: MetricResult,
        case_execution_id: str | None = None,
    ) -> MetricResultRecord:
        """Persist a canonical metric result."""
        payload = metric.model_dump(mode="json")

        record = MetricResultRecord(
            metric_result_id=metric.metric_result_id,
            run_id=metric.run_id or "",
            case_execution_id=case_execution_id,
            case_id=metric.case_id,
            metric_id=metric.metric_id,
            metric_version=metric.metric_version,
            value=metric.value,
            status=metric.status.value,
            reason=metric.reason,
            details=metric.details,
            payload=payload,
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def list_metric_results(
        self,
        run_id: str,
    ) -> Sequence[MetricResultRecord]:
        """List all individual metric results for a run."""
        result = await self._session.scalars(
            select(MetricResultRecord)
            .where(MetricResultRecord.run_id == run_id)
            .order_by(
                MetricResultRecord.case_id,
                MetricResultRecord.metric_id,
            )
        )

        return result.all()

    async def persist_aggregate(
        self,
        aggregate: AggregateMetricResult,
    ) -> AggregateMetricResultRecord:
        """Persist a canonical run-level aggregate metric."""
        record = AggregateMetricResultRecord(
            aggregate_metric_result_id=(
                f"agr-{aggregate.run_id}-"
                f"{aggregate.metric_id}-"
                f"{aggregate.aggregation}-"
                f"{aggregate.metric_version}"
            ),
            run_id=aggregate.run_id,
            metric_id=aggregate.metric_id,
            metric_version=aggregate.metric_version,
            aggregation=aggregate.aggregation,
            value=aggregate.value,
            status=aggregate.status.value,
            reason=aggregate.reason,
            details={
                **aggregate.distribution,
                "sample_count": aggregate.sample_count,
                "available_count": aggregate.available_count,
                "failed_count": aggregate.failed_count,
            },
        )

        self._session.add(record)
        await self._session.flush()

        return record

    async def list_aggregates(
        self,
        run_id: str,
    ) -> Sequence[AggregateMetricResultRecord]:
        """List all aggregate metric results for a run."""
        result = await self._session.scalars(
            select(AggregateMetricResultRecord)
            .where(
                AggregateMetricResultRecord.run_id == run_id
            )
            .order_by(
                AggregateMetricResultRecord.metric_id,
                AggregateMetricResultRecord.aggregation,
            )
        )

        return result.all()

    # -------------------------------------------------------------------------
    # Errors
    # -------------------------------------------------------------------------

    async def persist_error(
        self,
        error: ErrorRecord,
        **relations: str | None,
    ) -> ErrorRecordDB:
        """Persist one normalized structured error."""
        record = ErrorRecordDB(
            error_id=error.error_id,
            run_id=relations.get("run_id"),
            case_execution_id=relations.get("case_execution_id"),
            attempt_id=relations.get("attempt_id"),
            category=error.category.value,
            code=error.code,
            message=error.message,
            stage=error.stage,
            retryable=error.retryable,
            retry_after_ms=error.retry_after_ms,
            http_status=error.http_status,
            provider=error.provider,
            raw_artifact_id=(
                error.raw_artifact.artifact_id
                if error.raw_artifact is not None
                else None
            ),
            details=error.details,
        )

        self._session.add(record)
        await self._session.flush()

        return record