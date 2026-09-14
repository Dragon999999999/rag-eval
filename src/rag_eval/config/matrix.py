"""Deterministic, validated Cartesian expansion of experiment matrices."""

from copy import deepcopy
from dataclasses import dataclass
from itertools import product
from typing import Any

from pydantic import ValidationError

from rag_eval.config.hashing import configuration_hash
from rag_eval.config.loader import ConfigurationError, format_validation_error
from rag_eval.config.models import ExperimentConfig


@dataclass(frozen=True)
class PlannedExperiment:
    """One validated matrix combination and its deterministic identities."""

    config: ExperimentConfig
    config_hash: str
    parent_hash: str


def expand_matrix(config: ExperimentConfig) -> list[PlannedExperiment]:
    """Expand a configuration matrix into unique validated combinations.

    Paths are sorted for stable ordering. A final member beneath a declared
    flexible dictionary, such as ``target.parameters.top_k``, may be created;
    every preceding path component must already be a valid model field or
    dictionary key.
    """
    matrix = config.matrix or {}
    parent_hash = configuration_hash(config, include_matrix=True)
    if not matrix:
        base = config.model_copy(update={"matrix": None})
        return [PlannedExperiment(base, configuration_hash(base), parent_hash)]

    paths = sorted(matrix)
    values = [matrix[path] for path in paths]
    base_payload = config.model_dump(mode="python")
    base_payload["matrix"] = None
    planned: list[PlannedExperiment] = []
    seen_hashes: set[str] = set()

    for combination in product(*values):
        payload = deepcopy(base_payload)
        for path, value in zip(paths, combination, strict=True):
            _set_matrix_path(payload, path, value)
        try:
            expanded = ExperimentConfig.model_validate(payload)
        except ValidationError as exc:
            raise ConfigurationError(format_validation_error(exc)) from exc
        identity = configuration_hash(expanded)
        if identity not in seen_hashes:
            seen_hashes.add(identity)
            planned.append(PlannedExperiment(expanded, identity, parent_hash))
    return planned


def _set_matrix_path(payload: dict[str, Any], path: str, value: Any) -> None:
    """Set one validated dot path in a serialized experiment payload."""
    parts = path.split(".")
    current: Any = payload
    for index, part in enumerate(parts):
        final = index == len(parts) - 1
        if not isinstance(current, dict):
            raise ConfigurationError(f"matrix path is not a mapping: {path}")
        if final:
            if part not in current and not _allows_new_key(parts[:index]):
                raise ConfigurationError(f"invalid matrix path: {path}")
            current[part] = value
            return
        if part not in current:
            raise ConfigurationError(f"invalid matrix path: {path}")
        current = current[part]


def _allows_new_key(prefix: list[str]) -> bool:
    """Allow leaves only in documented flexible target-parameter mappings."""
    return prefix in (["target", "parameters"], ["target", "corpus", "parameters"])
