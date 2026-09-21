"""CLI commands for evaluator-managed targets."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator, Mapping
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Never

import typer

from rag_eval.adapters import target_adapter_descriptors
from rag_eval.artifacts import (
    ArtifactService,
    create_artifact_store,
)
from rag_eval.config import get_settings
from rag_eval.config.target_resolver import TargetConfigResolver
from rag_eval.db import (
    create_async_engine,
    create_session_factory,
)
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.target_models import (
    TargetConfigVersionRecord,
    TargetRecord,
)
from rag_eval.db.target_repository import TargetRepository
from rag_eval.services.secret_service import SecretService
from rag_eval.services.target_service import TargetService


app = typer.Typer(
    help="Manage evaluator targets.",
    no_args_is_help=True,
)


# ============================================================================
# Target lifecycle
# ============================================================================


@app.command("list")
def list_targets(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    """List registered evaluation targets."""

    try:
        targets = asyncio.run(
            _list_targets()
        )
    except Exception as exc:
        _fail(
            "target listing failed",
            exc,
        )

    if as_json:
        typer.echo(
            json.dumps(
                targets,
                indent=2,
                default=str,
            )
        )
        return

    if not targets:
        typer.echo(
            "No targets registered."
        )
        return

    for target in targets:
        typer.echo(
            f"{target['target_id']}  "
            f"{target['name']}  "
            f"[{target['adapter_type'] or 'unconfigured'}]  "
            f"{target['configuration_status']}  "
            f"{target['connection_status']}"
        )


@app.command("show")
def show_target(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    """Show target configuration and current state."""

    try:
        target = asyncio.run(
            _show_target(
                target_id
            )
        )
    except Exception as exc:
        _fail(
            "target lookup failed",
            exc,
        )

    if as_json:
        typer.echo(
            json.dumps(
                target,
                indent=2,
                default=str,
            )
        )
        return

    typer.echo(
        f"Target: {target['target_id']}"
    )
    typer.echo(
        f"Name: {target['name']}"
    )
    typer.echo(
        f"Adapter: "
        f"{target['adapter_type'] or 'not configured'}"
    )
    typer.echo(
        f"Configuration: "
        f"{target['configuration_status']}"
    )
    typer.echo(
        f"Config version: "
        f"{target['current_config_version'] or 'N/A'}"
    )
    typer.echo(
        f"Enabled: {target['enabled']}"
    )

    connection = target.get(
        "connection"
    )

    typer.echo()
    typer.echo("Connection:")

    if connection is None:
        typer.echo(
            "  status: not_tested"
        )
    else:
        typer.echo(
            f"  status: {connection['status']}"
        )

        if connection.get("checked_at"):
            typer.echo(
                f"  checked: "
                f"{connection['checked_at']}"
            )

    capabilities = target.get(
        "capabilities"
    )

    typer.echo()
    typer.echo(
        "Capabilities: "
        + (
            "available"
            if capabilities is not None
            else "not discovered"
        )
    )


@app.command("create")
def create_target(
    name: str = typer.Argument(
        ...,
        help="Human-readable target name.",
    ),
    target_id: str | None = typer.Option(
        None,
        "--id",
        help="Optional explicit target ID.",
    ),
    metadata: str | None = typer.Option(
        None,
        "--metadata",
        help="JSON object containing target metadata.",
    ),
) -> None:
    """Create a new empty evaluator-managed target."""

    try:
        parsed_metadata = _parse_json_object(
            metadata
        )

        target = asyncio.run(
            _create_target(
                name=name,
                target_id=target_id,
                metadata=parsed_metadata,
            )
        )
    except Exception as exc:
        _fail(
            "target creation failed",
            exc,
        )

    typer.echo(
        f"Created target {target.target_id}"
    )


@app.command("update")
def update_target(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    name: str | None = typer.Option(
        None,
        "--name",
        help="New target name.",
    ),
    metadata: str | None = typer.Option(
        None,
        "--metadata",
        help="Replacement metadata as JSON object.",
    ),
) -> None:
    """Update mutable target identity."""

    if (
        name is None
        and metadata is None
    ):
        typer.echo(
            "Nothing to update.",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        parsed_metadata = (
            _parse_json_object(metadata)
            if metadata is not None
            else None
        )

        target = asyncio.run(
            _update_target(
                target_id,
                name=name,
                metadata=parsed_metadata,
            )
        )
    except Exception as exc:
        _fail(
            "target update failed",
            exc,
        )

    typer.echo(
        f"Updated target {target.target_id}"
    )


@app.command("enable")
def enable_target(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
) -> None:
    """Enable a target."""

    try:
        asyncio.run(
            _set_target_enabled(
                target_id,
                True,
            )
        )
    except Exception as exc:
        _fail(
            "target enable failed",
            exc,
        )

    typer.echo(
        f"Enabled target {target_id}"
    )


@app.command("disable")
def disable_target(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
) -> None:
    """Disable a target."""

    try:
        asyncio.run(
            _set_target_enabled(
                target_id,
                False,
            )
        )
    except Exception as exc:
        _fail(
            "target disable failed",
            exc,
        )

    typer.echo(
        f"Disabled target {target_id}"
    )


@app.command("delete")
def delete_target(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    yes: bool = typer.Option(
        False,
        "--yes",
        "-y",
        help="Delete without interactive confirmation.",
    ),
) -> None:
    """Delete a registered target."""

    if not yes:
        confirmed = typer.confirm(
            f"Delete target '{target_id}'?"
        )

        if not confirmed:
            raise typer.Abort()

    try:
        asyncio.run(
            _delete_target(
                target_id
            )
        )
    except Exception as exc:
        _fail(
            "target deletion failed",
            exc,
        )

    typer.echo(
        f"Deleted target {target_id}"
    )


# ============================================================================
# Adapter catalogue
# ============================================================================


@app.command("adapters")
def list_adapters(
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    """List available target adapter types."""

    descriptors = [
        descriptor.model_dump(
            mode="json",
            exclude_none=True,
        )
        for descriptor in target_adapter_descriptors()
    ]

    if as_json:
        typer.echo(
            json.dumps(
                descriptors,
                indent=2,
                default=str,
            )
        )
        return

    for descriptor in descriptors:
        typer.echo(
            descriptor["type"]
        )

        description = descriptor.get(
            "description"
        )

        if description:
            typer.echo(
                f"  {description}"
            )

        typer.echo(
            "  overrides: "
            f"{descriptor['supports_overrides']}"
        )
        typer.echo(
            "  full protocol: "
            f"{descriptor['supports_full_protocol']}"
        )


# ============================================================================
# YAML configuration
# ============================================================================


@app.command("config-set")
def set_configuration(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    config: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to target.yaml.",
    ),
) -> None:
    """Save target.yaml as a new immutable configuration version."""

    try:
        content = config.read_text(
            encoding="utf-8"
        )

        record = asyncio.run(
            _save_configuration(
                target_id,
                content,
            )
        )
    except Exception as exc:
        _fail(
            "configuration save failed",
            exc,
        )

    typer.echo(
        f"Saved target configuration "
        f"version {record.version}"
    )
    typer.echo(
        f"Hash: {record.config_hash}"
    )


@app.command("config-show")
def show_configuration(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
) -> None:
    """Print the current sanitized target.yaml."""

    try:
        content = asyncio.run(
            _get_configuration(
                target_id
            )
        )
    except Exception as exc:
        _fail(
            "configuration lookup failed",
            exc,
        )

    if content is None:
        typer.echo(
            "Target has no YAML configuration.",
            err=True,
        )
        raise typer.Exit(code=1)

    typer.echo(
        content,
        nl=not content.endswith("\n"),
    )


@app.command("config-versions")
def list_configuration_versions(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    """List immutable target configuration versions."""

    try:
        versions = asyncio.run(
            _list_configuration_versions(
                target_id
            )
        )
    except Exception as exc:
        _fail(
            "configuration history lookup failed",
            exc,
        )

    if as_json:
        typer.echo(
            json.dumps(
                [
                    _config_version_dict(
                        version
                    )
                    for version in versions
                ],
                indent=2,
                default=str,
            )
        )
        return

    if not versions:
        typer.echo(
            "No configuration versions."
        )
        return

    for version in versions:
        typer.echo(
            f"v{version.version}  "
            f"{version.config_hash}  "
            f"{version.created_at}"
        )


# ============================================================================
# Trusted Python adapter
# ============================================================================


@app.command("upload-python")
def upload_python_adapter(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    source: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Trusted Python TargetAdapter source file.",
    ),
) -> None:
    """Upload a trusted Python adapter for a target."""

    if source.suffix.lower() != ".py":
        typer.echo(
            "Adapter source must be a .py file.",
            err=True,
        )
        raise typer.Exit(code=2)

    try:
        content = source.read_bytes()

        asyncio.run(
            _upload_python_adapter(
                target_id,
                content,
                source.name,
            )
        )
    except Exception as exc:
        _fail(
            "Python adapter upload failed",
            exc,
        )

    typer.echo(
        f"Configured {target_id} "
        f"with uploaded adapter {source.name}"
    )


# ============================================================================
# Connection / capabilities
# ============================================================================


@app.command("test-connection")
def test_connection(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    """Test target connectivity and persist the result."""

    try:
        state = asyncio.run(
            _test_connection(
                target_id
            )
        )
    except Exception as exc:
        _fail(
            "connection test failed",
            exc,
        )

    payload = state.model_dump(
        mode="json",
        exclude_none=True,
    )

    if as_json:
        typer.echo(
            json.dumps(
                payload,
                indent=2,
                default=str,
            )
        )
        return

    typer.echo(
        f"Connection: {payload['status']}"
    )

    if payload.get("checked_at"):
        typer.echo(
            f"Checked: {payload['checked_at']}"
        )

    if payload.get("error"):
        typer.echo(
            f"Error: {payload['error']}",
            err=True,
        )


@app.command("capabilities")
def capabilities(
    target_id: str = typer.Argument(
        ...,
        help="Target identifier.",
    ),
    refresh: bool = typer.Option(
        False,
        "--refresh",
        help="Re-query the target before displaying capabilities.",
    ),
    as_json: bool = typer.Option(
        False,
        "--json",
        help="Output machine-readable JSON.",
    ),
) -> None:
    """Display normalized target capabilities."""

    try:
        result = asyncio.run(
            _get_capabilities(
                target_id,
                refresh=refresh,
            )
        )
    except Exception as exc:
        _fail(
            "capabilities lookup failed",
            exc,
        )

    if result is None:
        typer.echo(
            "No capabilities have been discovered. "
            "Use --refresh.",
            err=True,
        )
        raise typer.Exit(code=1)

    payload = result.model_dump(
        mode="json",
        exclude_none=True,
    )

    if as_json:
        typer.echo(
            json.dumps(
                payload,
                indent=2,
                default=str,
            )
        )
        return

    typer.echo("Target Capabilities:")
    typer.echo(
        f"  Target: {result.target.name}"
    )
    typer.echo(
        f"  Query: {result.query}"
    )
    typer.echo(
        f"  Retrieval: {result.retrieval}"
    )
    typer.echo(
        f"  Streaming: {result.streaming}"
    )
    typer.echo(
        f"  Citations: {result.citations}"
    )
    typer.echo(
        f"  Confidence: {result.confidence}"
    )
    typer.echo(
        f"  Trace: {result.target_trace}"
    )


# ============================================================================
# Async service operations
# ============================================================================


@asynccontextmanager
async def _target_service() -> AsyncIterator[TargetService]:
    """Build a transaction-scoped TargetService for one CLI operation."""

    settings = get_settings()

    engine = create_async_engine(
        settings
    )

    try:
        session_factory = create_session_factory(
            engine
        )

        async with session_factory() as session:
            async with session.begin():
                persistence_repository = PersistenceRepository(
                    session
                )

                target_repository = TargetRepository(
                    session
                )

                artifact_store = create_artifact_store(
                    settings
                )

                artifact_service = ArtifactService(
                    artifact_store,
                    persistence_repository,
                )

                secret_service = SecretService(
                    repository=target_repository,
                    encryption_key=settings.secret_key,
                )

                resolver = TargetConfigResolver()

                service = TargetService(
                    repository=target_repository,
                    persistence_repository=persistence_repository,
                    artifact_service=artifact_service,
                    secret_service=secret_service,
                    config_resolver=resolver,
                )

                yield service

    finally:
        await engine.dispose()


async def _list_targets() -> list[dict[str, Any]]:
    """Return serialized target summaries."""

    async with _target_service() as service:
        targets = await service.list_targets()

        result: list[dict[str, Any]] = []

        for target in targets:
            connection = await service.get_connection_state(
                target.target_id
            )

            result.append(
                {
                    **_target_record_dict(
                        target
                    ),
                    "connection_status": (
                        connection.status.value
                        if connection is not None
                        else "not_tested"
                    ),
                }
            )

        return result


async def _show_target(
    target_id: str,
) -> dict[str, Any]:
    """Return complete target state."""

    async with _target_service() as service:
        target = await service.get_target(
            target_id
        )

        if target is None:
            raise KeyError(
                f"target not found: {target_id}"
            )

        connection = await service.get_connection_state(
            target_id
        )

        capabilities = await service.get_capabilities(
            target_id
        )

        return {
            **_target_record_dict(
                target
            ),
            "connection": (
                connection.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                if connection is not None
                else None
            ),
            "capabilities": (
                capabilities.model_dump(
                    mode="json",
                    exclude_none=True,
                )
                if capabilities is not None
                else None
            ),
        }


async def _create_target(
    *,
    name: str,
    target_id: str | None,
    metadata: Mapping[str, Any] | None,
) -> TargetRecord:
    """Create one target."""

    async with _target_service() as service:
        return await service.create_target(
            name,
            target_id=target_id,
            metadata=metadata,
        )


async def _update_target(
    target_id: str,
    *,
    name: str | None,
    metadata: Mapping[str, Any] | None,
) -> TargetRecord:
    """Update one target."""

    async with _target_service() as service:
        return await service.update_target(
            target_id,
            name=name,
            metadata=metadata,
        )


async def _set_target_enabled(
    target_id: str,
    enabled: bool,
) -> None:
    """Enable or disable a target."""

    async with _target_service() as service:
        await service.set_enabled(
            target_id,
            enabled,
        )


async def _delete_target(
    target_id: str,
) -> None:
    """Delete one target."""

    async with _target_service() as service:
        await service.delete_target(
            target_id
        )


async def _save_configuration(
    target_id: str,
    content: str,
) -> TargetConfigVersionRecord:
    """Save one target YAML version."""

    async with _target_service() as service:
        return await service.save_configuration(
            target_id,
            content,
        )


async def _get_configuration(
    target_id: str,
) -> str | None:
    """Return current sanitized target YAML."""

    async with _target_service() as service:
        target = await service.get_target(
            target_id
        )

        if target is None:
            raise KeyError(
                f"target not found: {target_id}"
            )

        if target.adapter_type == "uploaded_python":
            raise ValueError(
                "Target uses an uploaded Python adapter "
                "and has no editable target.yaml."
            )

        return await service.get_configuration_yaml(
            target_id
        )


async def _list_configuration_versions(
    target_id: str,
) -> list[TargetConfigVersionRecord]:
    """Return target configuration history."""

    async with _target_service() as service:
        return await service.list_config_versions(
            target_id
        )


async def _upload_python_adapter(
    target_id: str,
    content: bytes,
    filename: str,
) -> None:
    """Persist a trusted uploaded Python adapter."""

    async with _target_service() as service:
        await service.upload_python_adapter(
            target_id,
            content,
            filename=filename,
        )


async def _test_connection(
    target_id: str,
):
    """Test target connectivity."""

    async with _target_service() as service:
        return await service.test_connection(
            target_id
        )


async def _get_capabilities(
    target_id: str,
    *,
    refresh: bool,
):
    """Read or rediscover normalized target capabilities."""

    async with _target_service() as service:
        if refresh:
            return await service.discover_capabilities(
                target_id
            )

        return await service.get_capabilities(
            target_id
        )


# ============================================================================
# Formatting helpers
# ============================================================================


def _target_record_dict(
    target: TargetRecord,
) -> dict[str, Any]:
    """Serialize one ORM target record for CLI output."""

    return {
        "target_id": target.target_id,
        "name": target.name,
        "adapter_type": target.adapter_type,
        "configuration_status": target.configuration_status,
        "current_config_version": target.current_config_version,
        "enabled": target.enabled,
        "metadata": dict(
            target.metadata_json or {}
        ),
        "created_at": target.created_at,
        "updated_at": target.updated_at,
    }


def _config_version_dict(
    version: TargetConfigVersionRecord,
) -> dict[str, Any]:
    """Serialize one immutable target configuration version."""

    return {
        "config_version_id": version.config_version_id,
        "version": version.version,
        "schema_version": version.schema_version,
        "source_artifact_id": version.source_artifact_id,
        "config_hash": version.config_hash,
        "created_at": version.created_at,
    }


def _parse_json_object(
    value: str | None,
) -> dict[str, Any]:
    """Parse a CLI JSON object argument."""

    if value is None:
        return {}

    try:
        parsed = json.loads(
            value
        )
    except json.JSONDecodeError as exc:
        raise ValueError(
            "--metadata must contain valid JSON."
        ) from exc

    if not isinstance(parsed, dict):
        raise ValueError(
            "--metadata must contain a JSON object."
        )

    return parsed


def _fail(
    message: str,
    exc: Exception,
) -> Never:
    """Print a normalized CLI failure and exit."""

    typer.echo(
        f"{message}: {exc}",
        err=True,
    )

    raise typer.Exit(
        code=1
    ) from exc