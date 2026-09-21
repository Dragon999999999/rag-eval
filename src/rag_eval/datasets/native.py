"""JSON and JSONL loaders for canonical benchmark records."""

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any, TypeVar

from pydantic import ValidationError

from rag_eval.datasets.validation import DatasetValidationError
from rag_eval.models import BenchmarkCase, Chunk, Document

RecordT = TypeVar("RecordT", BenchmarkCase, Document, Chunk)


def load_cases(path: Path) -> list[BenchmarkCase]:
    """Load benchmark cases from a JSON array or JSONL file."""
    return list(iter_cases(path))


def iter_cases(path: Path) -> Iterator[BenchmarkCase]:
    """Yield benchmark cases from JSON or JSONL."""
    yield from _iter_records(path, BenchmarkCase, "case")


def load_documents(path: Path) -> list[Document]:
    """Load canonical document metadata from JSON or JSONL."""
    return list(iter_documents(path))


def iter_documents(path: Path) -> Iterator[Document]:
    """Yield canonical document metadata from JSON or JSONL."""
    yield from _iter_records(path, Document, "document")


def load_chunks(path: Path) -> list[Chunk]:
    """Load canonical chunks from JSON or JSONL."""
    return list(iter_chunks(path))


def iter_chunks(path: Path) -> Iterator[Chunk]:
    """Yield canonical chunks from JSON or JSONL."""
    yield from _iter_records(path, Chunk, "chunk")


def parse_cases_json(data: str | bytes) -> list[BenchmarkCase]:
    """Parse benchmark cases directly from JSON text or bytes.

    Useful for API requests and pasted JSON in the UI.
    """
    payload = _parse_json(data, "cases")

    if not isinstance(payload, list):
        raise DatasetValidationError("case JSON must contain an array")

    return [
        _validate_record(record, BenchmarkCase, "case", index)
        for index, record in enumerate(payload, start=1)
    ]


def parse_case_jsonl(data: str | bytes) -> list[BenchmarkCase]:
    """Parse newline-delimited benchmark cases from text or bytes."""
    text = data.decode("utf-8") if isinstance(data, bytes) else data

    cases: list[BenchmarkCase] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue

        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise DatasetValidationError(
                f"invalid JSONL at line {line_number}"
            ) from exc

        cases.append(
            _validate_record(
                record,
                BenchmarkCase,
                "case",
                line_number,
            )
        )

    return cases


def _iter_records(
    path: Path,
    model_type: type[RecordT],
    record_name: str,
) -> Iterator[RecordT]:
    """Yield validated canonical records from JSON or JSONL."""
    if not path.exists():
        raise DatasetValidationError(f"dataset file not found: {path}")

    if path.suffix.lower() == ".jsonl":
        try:
            with path.open(encoding="utf-8") as source:
                for line_number, line in enumerate(source, start=1):
                    if not line.strip():
                        continue

                    try:
                        record = json.loads(line)
                    except json.JSONDecodeError as exc:
                        raise DatasetValidationError(
                            f"invalid JSONL in {path} at line {line_number}"
                        ) from exc

                    yield _validate_record(
                        record,
                        model_type,
                        record_name,
                        line_number,
                    )

        except OSError as exc:
            raise DatasetValidationError(
                f"could not read dataset file: {path}"
            ) from exc

        return

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DatasetValidationError(
            f"could not read dataset file: {path}"
        ) from exc
    except json.JSONDecodeError as exc:
        raise DatasetValidationError(
            f"invalid JSON in {path}"
        ) from exc

    if not isinstance(payload, list):
        raise DatasetValidationError(
            f"JSON dataset file must contain an array: {path}"
        )

    for index, record in enumerate(payload, start=1):
        yield _validate_record(
            record,
            model_type,
            record_name,
            index,
        )


def _validate_record(
    record: Any,
    model_type: type[RecordT],
    record_name: str,
    index: int,
) -> RecordT:
    """Validate one external record into a canonical model."""
    if not isinstance(record, dict):
        raise DatasetValidationError(
            f"{record_name} record {index} must be a mapping"
        )

    try:
        return model_type.model_validate(record)
    except ValidationError as exc:
        raise DatasetValidationError(
            f"invalid {record_name} record {index}: {exc}"
        ) from exc


def _parse_json(data: str | bytes, name: str) -> Any:
    """Parse JSON text or bytes with dataset-safe errors."""
    try:
        return json.loads(data)
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise DatasetValidationError(
            f"invalid {name} JSON"
        ) from exc

def load_records(
    path: Path,
    model_type: type[RecordT],
    record_name: str,
) -> list[RecordT]:
    """Load validated canonical records from JSON or JSONL."""
    return list(_iter_records(path, model_type, record_name))