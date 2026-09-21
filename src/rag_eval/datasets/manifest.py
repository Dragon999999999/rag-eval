"""Portable benchmark manifest import helpers."""

import hashlib
import json
from pathlib import Path
from typing import Any, TypeVar

import yaml
from pydantic import ValidationError

from rag_eval.datasets.native import (
    load_records,
)
from rag_eval.datasets.validation import DatasetValidationError
from rag_eval.models import (
    Benchmark,
    BenchmarkCase,
    BenchmarkManifest,
    Chunk,
    Document,
)

RecordT = TypeVar("RecordT", BenchmarkCase, Document, Chunk)

def load_benchmark_file(path: Path) -> Benchmark:
    """Load a portable JSON/YAML benchmark definition into a Benchmark.

    This is an import format only. Normal API/CLI benchmark creation does not
    require a manifest file.
    """
    payload, raw = _load_payload(path)

    manifest_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"cases", "documents", "chunks"}
    }

    try:
        manifest = BenchmarkManifest.model_validate(manifest_payload)
    except ValidationError as exc:
        raise DatasetValidationError(
            f"invalid benchmark manifest: {exc}"
        ) from exc

    cases = _load_component(
        payload.get("cases"),
        path.parent,
        BenchmarkCase,
    )

    documents = _load_component(
        payload.get("documents"),
        path.parent,
        Document,
    )

    chunks = _load_component(
        payload.get("chunks"),
        path.parent,
        Chunk,
    )

    benchmark = Benchmark(
        manifest=manifest,
        cases=cases,
        documents=documents,
        chunks=chunks,
    )

    validate_benchmark(benchmark)

    return benchmark


def validate_benchmark(benchmark: Benchmark) -> None:
    """Validate cross-record invariants of a canonical Benchmark."""
    document_ids: set[str] = set()

    for document in benchmark.documents:
        if document.document_id in document_ids:
            raise DatasetValidationError(
                f"duplicate document_id: {document.document_id}"
            )

        document_ids.add(document.document_id)

    chunk_ids: set[str] = set()

    for chunk in benchmark.chunks:
        if chunk.chunk_id in chunk_ids:
            raise DatasetValidationError(
                f"duplicate chunk_id: {chunk.chunk_id}"
            )

        chunk_ids.add(chunk.chunk_id)

        if chunk.document_id not in document_ids:
            raise DatasetValidationError(
                f"chunk {chunk.chunk_id} references unknown document "
                f"{chunk.document_id}"
            )

    case_ids: set[str] = set()

    for case in benchmark.cases:
        if case.case_id in case_ids:
            raise DatasetValidationError(
                f"duplicate case_id: {case.case_id}"
            )

        case_ids.add(case.case_id)

        for evidence in case.gold_evidence:
            if evidence.document_id not in document_ids:
                raise DatasetValidationError(
                    f"case {case.case_id} evidence "
                    f"{evidence.evidence_id} references unknown document "
                    f"{evidence.document_id}"
                )


def benchmark_file_sha256(path: Path) -> str:
    """Return the SHA-256 hash of a portable benchmark file."""
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except FileNotFoundError as exc:
        raise DatasetValidationError(
            f"benchmark file not found: {path}"
        ) from exc


def _load_payload(path: Path) -> tuple[dict[str, Any], bytes]:
    """Load the root JSON/YAML mapping."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise DatasetValidationError(
            f"benchmark file not found: {path}"
        ) from exc

    try:
        if path.suffix.lower() == ".json":
            payload = json.loads(raw)
        else:
            payload = yaml.safe_load(raw)
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise DatasetValidationError(
            f"invalid benchmark syntax: {path}"
        ) from exc

    if not isinstance(payload, dict):
        raise DatasetValidationError(
            "benchmark root must be a mapping"
        )

    return payload, raw


def _load_component(
    source: Any,
    base_path: Path,
    model_type: type[RecordT],
) -> list[RecordT]:
    """Load inline records or a referenced JSON/JSONL file."""
    if source is None:
        return []

    if isinstance(source, list):
        try:
            return [
                model_type.model_validate(record)
                for record in source
            ]
        except ValidationError as exc:
            raise DatasetValidationError(
                f"invalid {model_type.__name__} record: {exc}"
            ) from exc

    if isinstance(source, str):
        source_path = (base_path / source).resolve()
        return load_records(
            source_path,
            model_type,
            model_type.__name__,
        )

    raise DatasetValidationError(
        f"{model_type.__name__} source must be "
        "an inline list or JSON/JSONL path"
    )