"""YAML loading and explicit environment-reference resolution helpers."""

import os
from collections.abc import Mapping
from pathlib import Path

import yaml
from pydantic import ValidationError

from rag_eval.config.models import ExperimentConfig


class ConfigurationError(ValueError):
    """A concise, user-correctable experiment configuration error."""


def load_experiment_config(path: Path) -> ExperimentConfig:
    """Load and validate one experiment configuration YAML file.

    Args:
        path: YAML configuration file to validate.

    Raises:
        ConfigurationError: If the file is missing, malformed, or invalid.
    """
    try:
        content = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ConfigurationError(f"configuration file not found: {path}") from exc

    try:
        payload = yaml.safe_load(content)
    except yaml.YAMLError as exc:
        raise ConfigurationError(
            f"invalid YAML: {exc.problem or 'unable to parse'}"
        ) from exc

    if not isinstance(payload, dict):
        raise ConfigurationError("configuration root must be a YAML mapping")

    try:
        return ExperimentConfig.model_validate(payload)
    except ValidationError as exc:
        raise ConfigurationError(format_validation_error(exc)) from exc


def format_validation_error(error: ValidationError) -> str:
    """Return the first Pydantic error as a concise dotted-path message."""
    issue = error.errors(include_url=False)[0]
    location = ".".join(str(part) for part in issue["loc"])
    return f"{location}: {issue['msg']}"


def resolve_environment_reference(
    name: str, environment: Mapping[str, str] | None = None
) -> str:
    """Resolve one required environment value without modifying static config.

    Args:
        name: Name of the required environment variable.
        environment: Optional mapping used for deterministic tests.

    Raises:
        ConfigurationError: If the referenced variable is unset or empty.
    """
    source = os.environ if environment is None else environment
    value = source.get(name)
    if not value:
        raise ConfigurationError(f"required environment variable is not set: {name}")
    return value
