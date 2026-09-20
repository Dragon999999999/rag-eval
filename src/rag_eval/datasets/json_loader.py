"""First-party local JSON, JSONL, and YAML benchmark dataset loader."""

import hashlib
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from rag_eval.datasets.base import BenchmarkDataset
from rag_eval.datasets.manifest import load_manifest_file
from rag_eval.datasets.validation import DatasetValidationError
from rag_eval.models import BenchmarkCase, BenchmarkManifest, Chunk, Document

RecordT = TypeVar("RecordT", BenchmarkCase, Document, Chunk)

class NativeBenchmarkDataset(BenchmarkDataset):
    """Load the small native benchmark format while streaming JSONL records.

    The manifest is JSON or YAML. ``cases`` and ``chunks`` may be inline lists,
    JSON arrays, or JSONL paths relative to the manifest. Document records may
    include a local ``path`` alongside canonical ``Document`` fields.
    """

    def __init__(self, manifest_path: Path) -> None:
        """Bind one native manifest path without eagerly loading case files."""
        self._manifest_path = manifest_path
        self._manifest, self._payload, self.manifest_sha256 = load_manifest_file(
            manifest_path
        )
        self._document_paths = self._index_document_paths()

    def load_manifest(self) -> BenchmarkManifest:
        """Return the canonical manifest parsed at construction time."""
        return self._manifest

    def iter_cases(self) -> Iterator[BenchmarkCase]:
        """Yield validated case records one at a time."""
        yield from self._iter_records("cases", BenchmarkCase)

    def iter_documents(self) -> Iterator[Document]:
        """Yield canonical documents declared inline or in a referenced file."""
        yield from self._iter_records("documents", Document, excluded={"path"})

    def iter_chunks(self) -> Iterator[Chunk]:
        """Yield canonical evaluator-provided chunks without preloading JSONL."""
        yield from self._iter_records("chunks", Chunk)

    def source_path(self, document: Document) -> Path | None:
        """Return the configured local path for an evaluator-owned document."""
        return self._document_paths.get(document.document_id)

    def validate(self) -> None:
        """Stream all records and validate cross-record identity and evidence rules."""
        document_ids: set[str] = set()
        documents = list(self.iter_documents())
        for document in documents:
            if document.document_id in document_ids:
                raise DatasetValidationError(
                    f"duplicate document_id: {document.document_id}"
                )
            document_ids.add(document.document_id)
            self._validate_document_hash(document)
        chunk_ids: set[str] = set()
        for chunk in self.iter_chunks():
            if chunk.chunk_id in chunk_ids:
                raise DatasetValidationError(f"duplicate chunk_id: {chunk.chunk_id}")
            chunk_ids.add(chunk.chunk_id)
            if chunk.document_id not in document_ids:
                raise DatasetValidationError(
                    f"chunk {chunk.chunk_id} references unknown document "
                    f"{chunk.document_id}"
                )
        case_ids: set[str] = set()
        for case in self.iter_cases():
            if case.case_id in case_ids:
                raise DatasetValidationError(f"duplicate case_id: {case.case_id}")
            case_ids.add(case.case_id)
            for evidence in case.gold_evidence:
                if evidence.document_id not in document_ids:
                    raise DatasetValidationError(
                        f"case {case.case_id} evidence {evidence.evidence_id} "
                        "references "
                        f"unknown document {evidence.document_id}"
                    )
        if self._manifest.case_count is not None and self._manifest.case_count != len(
            case_ids
        ):
            raise DatasetValidationError(
                f"manifest case_count is {self._manifest.case_count}, "
                f"found {len(case_ids)}"
            )

    def _iter_records(
        self,
        name: str,
        model_type: type[RecordT],
        *,
        excluded: set[str] | None = None,
    ) -> Iterator[RecordT]:
        """Yield one record source as validated canonical models."""
        source = self._payload.get(name)
        if source is None:
            return

        records: Iterator[dict[str, Any]]
        if isinstance(source, list):
            records = iter(source)
        elif isinstance(source, str):
            records = self._records_from_path(self._resolve(source))
        else:
            raise DatasetValidationError(f"manifest {name} must be a list or file path")

        for index, record in enumerate(records, start=1):
            if not isinstance(record, dict):
                raise DatasetValidationError(f"{name} record {index} must be a mapping")

            canonical_record = dict(record)
            for field in excluded or set():
                canonical_record.pop(field, None)

            try:
                yield model_type.model_validate(canonical_record)
            except ValidationError as exc:
                raise DatasetValidationError(
                    f"invalid {name} record {index}: {exc}"
                ) from exc

    def _records_from_path(self, path: Path) -> Iterator[dict[str, Any]]:
        """Yield JSON arrays or line-by-line JSONL without buffering JSONL."""
        try:
            if path.suffix.lower() == ".jsonl":
                with path.open(encoding="utf-8") as source:
                    for line_number, line in enumerate(source, start=1):
                        if not line.strip():
                            continue
                        try:
                            yield json.loads(line)
                        except json.JSONDecodeError as exc:
                            raise DatasetValidationError(
                                f"invalid JSONL in {path} at line {line_number}"
                            ) from exc
                return
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise DatasetValidationError(f"dataset file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise DatasetValidationError(f"invalid JSON in {path}") from exc
        if not isinstance(payload, list):
            raise DatasetValidationError(
                f"JSON dataset file must contain an array: {path}"
            )
        yield from payload

    def _index_document_paths(self) -> dict[str, Path]:
        """Index optional local document paths without making them canonical IDs."""
        source = self._payload.get("documents", [])
        if isinstance(source, list):
            records = source
        elif isinstance(source, str):
            records = self._records_from_path(self._resolve(source))
        else:
            return {}
        paths: dict[str, Path] = {}
        for record in records:
            if isinstance(record, dict) and isinstance(record.get("path"), str):
                document_id = record.get("document_id")
                if isinstance(document_id, str):
                    paths[document_id] = self._resolve(record["path"])
        return paths

    def _validate_document_hash(self, document: Document) -> None:
        """Verify supplied hashes against local bytes when a path is available."""
        path = self.source_path(document)
        if document.sha256 is None or path is None:
            return
        try:
            with path.open("rb") as source:
                digest = hashlib.file_digest(source, "sha256").hexdigest()
        except FileNotFoundError as exc:
            raise DatasetValidationError(f"document file not found: {path}") from exc
        if digest != document.sha256:
            raise DatasetValidationError(
                f"document SHA-256 mismatch for {document.document_id}"
            )

    def _resolve(self, value: str) -> Path:
        """Resolve a dataset-relative local path without changing canonical identity."""
        return (self._manifest_path.parent / value).resolve()
