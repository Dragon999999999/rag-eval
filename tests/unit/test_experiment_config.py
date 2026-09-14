"""Tests for static experiment loading, identities, matrices, and CLI output."""

from pathlib import Path

import pytest
from pydantic import ValidationError
from typer.testing import CliRunner

from rag_eval.cli import app
from rag_eval.config import (
    ConfigurationError,
    configuration_hash,
    expand_matrix,
    load_experiment_config,
    resolve_environment_reference,
)
from rag_eval.config.models import ExperimentConfig


def config_payload() -> dict[str, object]:
    """Return a complete minimal static experiment configuration payload."""
    return {
        "version": "1",
        "run": {"name": "test-plan", "seed": 7},
        "dataset": {"manifest": "benchmarks/example.yaml"},
        "target": {
            "adapter": "http",
            "base_url": "https://target.example.test",
            "authentication_env": "TARGET_API_TOKEN",
            "corpus": {"mode": "DOCUMENTS"},
            "parameters": {"embedding_model": "bge-m3", "top_k": 5},
        },
        "execution": {
            "concurrency": 2,
            "connect_timeout": 5,
            "request_timeout": 30,
            "total_timeout": 60,
        },
        "metrics": {"mode": "all_available"},
        "storage": {
            "database": {"url_env": "RAG_EVAL_DATABASE_URL"},
            "artifacts": {
                "endpoint_env": "RAG_EVAL_S3_ENDPOINT_URL",
                "bucket": "rag-eval-artifacts",
                "secret_key_env": "RAG_EVAL_S3_SECRET_KEY",
            },
        },
    }


def write_yaml(path: Path, content: str) -> Path:
    """Write a UTF-8 YAML fixture and return its path."""
    path.write_text(content, encoding="utf-8")
    return path


def test_valid_yaml_loading_and_hash_is_order_independent(tmp_path: Path) -> None:
    """Equivalent YAML mappings load and hash identically despite key ordering."""
    first = write_yaml(
        tmp_path / "first.yaml",
        """version: '1'
run: {name: test-plan, seed: 7}
dataset: {manifest: benchmarks/example.yaml}
target:
  adapter: http
  base_url: https://target.example.test
  corpus: {mode: DOCUMENTS}
  parameters: {top_k: 5, embedding_model: bge-m3}
""",
    )
    second = write_yaml(
        tmp_path / "second.yaml",
        """target:
  parameters: {embedding_model: bge-m3, top_k: 5}
  corpus: {mode: DOCUMENTS}
  base_url: https://target.example.test
  adapter: http
dataset: {manifest: benchmarks/example.yaml}
run: {seed: 7, name: test-plan}
version: '1'
""",
    )

    assert configuration_hash(load_experiment_config(first)) == configuration_hash(
        load_experiment_config(second)
    )


def test_malformed_yaml_and_invalid_schema_report_concise_errors(
    tmp_path: Path,
) -> None:
    """Normal YAML and schema mistakes become actionable configuration errors."""
    malformed = write_yaml(tmp_path / "malformed.yaml", "target: [unterminated")
    invalid = write_yaml(
        tmp_path / "invalid.yaml",
        """version: '1'
run: {name: invalid}
dataset: {manifest: benchmark.yaml}
target:
  adapter: http
  corpus: {mode: DOCUMENTS}
execution: {concurrency: 0}
""",
    )

    with pytest.raises(ConfigurationError, match="invalid YAML"):
        load_experiment_config(malformed)
    with pytest.raises(ConfigurationError, match="base_url"):
        load_experiment_config(invalid)


def test_environment_reference_resolution_never_changes_canonical_config() -> None:
    """Resolved values remain runtime-only and cannot affect static identities."""
    config = ExperimentConfig.model_validate(config_payload())
    secret = resolve_environment_reference(
        "TARGET_API_TOKEN", {"TARGET_API_TOKEN": "never-serialize-this"}
    )
    canonical_hash = configuration_hash(config)

    assert secret == "never-serialize-this"
    assert "never-serialize-this" not in config.model_dump_json()
    assert "never-serialize-this" not in canonical_hash
    assert configuration_hash(config) == canonical_hash
    with pytest.raises(ConfigurationError, match="MISSING_TOKEN"):
        resolve_environment_reference("MISSING_TOKEN", {})


def test_matrix_expands_in_stable_order_and_deduplicates_equivalent_values() -> None:
    """Three two-value dimensions produce eight stable validated configurations."""
    payload = config_payload()
    payload["matrix"] = {
        "target.parameters.top_k": [5, 10],
        "target.parameters.chunk_size": [256, 512],
        "target.parameters.embedding_model": ["bge-m3", "e5-large"],
    }
    config = ExperimentConfig.model_validate(payload)

    first = expand_matrix(config)
    second = expand_matrix(config)

    assert len(first) == 8
    assert [item.config_hash for item in first] == [item.config_hash for item in second]
    assert len({item.config_hash for item in first}) == 8
    assert first[0].config.target.parameters["chunk_size"] == 256
    assert first[0].config.target.parameters["top_k"] == 5


def test_matrix_rejects_invalid_paths_and_invalid_expanded_values() -> None:
    """Matrix planning neither creates malformed model fields nor skips validation."""
    payload = config_payload()
    payload["matrix"] = {"target.not_a_field": ["value"]}
    with pytest.raises(ConfigurationError, match="invalid matrix path"):
        expand_matrix(ExperimentConfig.model_validate(payload))

    payload["matrix"] = {"execution.concurrency": [0]}
    with pytest.raises(ConfigurationError, match="execution.concurrency"):
        expand_matrix(ExperimentConfig.model_validate(payload))


def test_target_and_corpus_configuration_validation() -> None:
    """Adapter location rules and canonical corpus modes are enforced locally."""
    payload = config_payload()
    payload["target"] = {
        "adapter": "python",
        "base_url": "https://target.example.test",
        "python_target": "package:target",
        "corpus": {"mode": "INVALID"},
    }

    with pytest.raises(ValidationError):
        ExperimentConfig.model_validate(payload)


def test_cli_validate_and_plan_never_print_secret_values(tmp_path: Path) -> None:
    """CLI validates and plans static YAML without resolving authentication refs."""
    path = write_yaml(
        tmp_path / "config.yaml",
        """version: '1'
run: {name: cli-plan}
dataset: {manifest: benchmark.yaml}
target:
  adapter: http
  base_url: https://target.example.test
  authentication_env: TARGET_API_TOKEN
  corpus: {mode: DOCUMENTS}
metrics: {mode: all_available}
matrix:
  target.parameters.top_k: [5, 10]
""",
    )
    runner = CliRunner()
    validate_result = runner.invoke(app, ["validate", str(path)])
    plan_result = runner.invoke(app, ["plan", str(path)])

    assert validate_result.exit_code == 0
    assert "configuration valid" in validate_result.stdout
    assert plan_result.exit_code == 0
    assert "matrix combinations: 2" in plan_result.stdout
    assert "TARGET_API_TOKEN" not in plan_result.stdout


def test_cli_invalid_configuration_has_no_traceback(tmp_path: Path) -> None:
    """Expected configuration errors are concise rather than Python tracebacks."""
    path = write_yaml(tmp_path / "bad.yaml", "version: '1'\n")
    result = CliRunner().invoke(app, ["validate", str(path)])

    assert result.exit_code == 1
    assert "configuration invalid:" in result.stderr
    assert "Traceback" not in result.stderr
