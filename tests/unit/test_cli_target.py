"""Tests for evaluator-managed target CLI compatibility."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from rag_eval.cli import app
from rag_eval.models import TargetCapabilities, TargetConnectionState, TargetInfo
from rag_eval.models.enums import TargetConnectionStatus

runner = CliRunner()


def test_cli_version() -> None:
    """The top-level version command remains compatible after regrouping."""
    result = runner.invoke(app, ["version"])

    assert result.exit_code == 0
    assert "rag-eval" in result.stdout


def test_cli_help_lists_current_command_groups() -> None:
    """The top-level CLI exposes the refactored command groups."""
    result = runner.invoke(app, ["--help"])

    assert result.exit_code == 0
    for command in ("benchmark", "target", "test", "score"):
        assert command in result.stdout


def test_target_management_help_lists_lifecycle_and_configuration_commands() -> None:
    """Target CLI exposes lifecycle, configuration, and adapter operations."""
    result = runner.invoke(app, ["target", "--help"])

    assert result.exit_code == 0
    for command in (
        "create",
        "list",
        "show",
        "update",
        "enable",
        "disable",
        "delete",
        "config-set",
        "config-show",
        "config-versions",
        "adapters",
        "upload-python",
    ):
        assert command in result.stdout


def test_target_lifecycle_commands_delegate_to_target_service(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CRUD and enable/disable commands use the target service boundary."""
    from rag_eval.cli import target as target_cli

    target = SimpleNamespace(target_id="target-1")
    calls: list[tuple[str, object]] = []

    async def create_target(**kwargs: object) -> SimpleNamespace:
        calls.append(("create", kwargs))
        return target

    async def update_target(target_id: str, **kwargs: object) -> SimpleNamespace:
        calls.append(("update", (target_id, kwargs)))
        return target

    async def set_enabled(target_id: str, enabled: bool) -> None:
        calls.append(("enabled", (target_id, enabled)))

    async def delete_target(target_id: str) -> None:
        calls.append(("delete", target_id))

    monkeypatch.setattr(target_cli, "_create_target", create_target)
    monkeypatch.setattr(target_cli, "_update_target", update_target)
    monkeypatch.setattr(target_cli, "_set_target_enabled", set_enabled)
    monkeypatch.setattr(target_cli, "_delete_target", delete_target)

    assert (
        runner.invoke(app, ["target", "create", "Demo", "--id", "target-1"]).exit_code
        == 0
    )
    assert (
        runner.invoke(
            app, ["target", "update", "target-1", "--name", "Renamed"]
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["target", "disable", "target-1"]).exit_code == 0
    assert runner.invoke(app, ["target", "enable", "target-1"]).exit_code == 0
    assert runner.invoke(app, ["target", "delete", "target-1", "--yes"]).exit_code == 0
    assert [call[0] for call in calls] == [
        "create",
        "update",
        "enabled",
        "enabled",
        "delete",
    ]


def test_target_configuration_and_adapter_commands(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    """Configuration history, Python uploads, and adapter listing are exposed."""
    from rag_eval.cli import target as target_cli

    config_file = tmp_path / "target.yaml"
    config_file.write_text("adapter: {}\n", encoding="utf-8")
    source_file = tmp_path / "adapter.py"
    source_file.write_text("def create_adapter(): return object()\n", encoding="utf-8")
    version = SimpleNamespace(
        config_version_id="version-1",
        version=1,
        schema_version="1.0",
        source_artifact_id="artifact-1",
        config_hash="a" * 64,
        created_at=datetime.now(UTC),
    )
    monkeypatch.setattr(
        target_cli, "_save_configuration", lambda *_args: _async_value(version)
    )
    monkeypatch.setattr(
        target_cli,
        "_get_configuration",
        lambda *_args: _async_value("adapter:\n  type: python\n"),
    )
    monkeypatch.setattr(
        target_cli,
        "_list_configuration_versions",
        lambda *_args: _async_value([version]),
    )
    monkeypatch.setattr(
        target_cli, "_upload_python_adapter", lambda *_args: _async_value(None)
    )

    assert (
        runner.invoke(
            app, ["target", "config-set", "target-1", str(config_file)]
        ).exit_code
        == 0
    )
    shown = runner.invoke(app, ["target", "config-show", "target-1"])
    assert shown.exit_code == 0
    assert "type: python" in shown.stdout
    versions = runner.invoke(app, ["target", "config-versions", "target-1"])
    assert versions.exit_code == 0
    assert "v1" in versions.stdout
    assert (
        runner.invoke(
            app, ["target", "upload-python", "target-1", str(source_file)]
        ).exit_code
        == 0
    )
    assert runner.invoke(app, ["target", "adapters"]).exit_code == 0


def test_target_connection_and_capabilities_commands(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Connection tests and cached/refresh capability reads are distinct."""
    from rag_eval.cli import target as target_cli

    state = TargetConnectionState(status=TargetConnectionStatus.CONNECTED)
    capabilities = TargetCapabilities(target=TargetInfo(name="demo"), query=True)
    refresh_flags: list[bool] = []

    monkeypatch.setattr(
        target_cli, "_test_connection", lambda *_args: _async_value(state)
    )

    async def get_capabilities(_target_id: str, *, refresh: bool) -> TargetCapabilities:
        refresh_flags.append(refresh)
        return capabilities

    monkeypatch.setattr(target_cli, "_get_capabilities", get_capabilities)
    tested = runner.invoke(app, ["target", "test-connection", "target-1"])
    assert tested.exit_code == 0
    assert "connected" in tested.stdout.lower()
    assert runner.invoke(app, ["target", "capabilities", "target-1"]).exit_code == 0
    assert (
        runner.invoke(
            app, ["target", "capabilities", "target-1", "--refresh"]
        ).exit_code
        == 0
    )
    assert refresh_flags == [False, True]


async def _async_value(value: object) -> object:
    """Return a value from a tiny async CLI test double."""
    return value
