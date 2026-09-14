"""Deterministic canonical serialization and SHA-256 config identities."""

import hashlib
import json
from typing import Any

from pydantic import BaseModel


def canonicalize_config(
    value: BaseModel | dict[str, Any], *, include_matrix: bool = False
) -> str:
    """Serialize semantic config content as stable, whitespace-free JSON.

    Environment references remain names in the supplied model, so resolved
    credentials cannot be included in this representation or its hash.
    """
    if isinstance(value, BaseModel):
        payload = value.model_dump(mode="json", exclude_none=True)
    else:
        payload = value
    if not include_matrix and isinstance(payload, dict):
        payload = {key: item for key, item in payload.items() if key != "matrix"}
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def configuration_hash(
    value: BaseModel | dict[str, Any], *, include_matrix: bool = False
) -> str:
    """Return the SHA-256 identity of canonical semantic configuration JSON."""
    canonical_json = canonicalize_config(value, include_matrix=include_matrix)
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
