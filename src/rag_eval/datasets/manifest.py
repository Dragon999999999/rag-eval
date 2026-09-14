"""Native benchmark-manifest parsing helpers."""

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from rag_eval.datasets.validation import DatasetValidationError
from rag_eval.models import BenchmarkManifest


def load_manifest_file(path: Path) -> tuple[BenchmarkManifest, dict[str, Any], str]:
    """Load one JSON or YAML manifest and return its canonical identity and hash.

    Args:
        path: Manifest file to read as UTF-8 JSON or YAML.

    Raises:
        DatasetValidationError: If the source is unavailable, malformed, or not
            a canonical manifest mapping.
    """
    try:
        raw = path.read_bytes()
    except FileNotFoundError as exc:
        raise DatasetValidationError(f"manifest file not found: {path}") from exc
    try:
        payload = (
            json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
        )
    except (json.JSONDecodeError, yaml.YAMLError) as exc:
        raise DatasetValidationError(f"invalid manifest syntax: {path}") from exc
    if not isinstance(payload, dict):
        raise DatasetValidationError("manifest root must be a mapping")
    manifest_payload = {
        key: value
        for key, value in payload.items()
        if key
        not in {
            "cases",
            "documents",
            "chunks",
            "document_sources",
            "case_file",
            "chunk_file",
        }
    }
    try:
        manifest = BenchmarkManifest.model_validate(manifest_payload)
    except ValidationError as exc:
        raise DatasetValidationError(f"invalid manifest: {exc}") from exc
    return manifest, payload, hashlib.sha256(raw).hexdigest()
