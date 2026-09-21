"""REST API for evaluator-managed targets."""

from __future__ import annotations

from typing import Annotated

from fastapi import (
    APIRouter,
    Body,
    File,
    HTTPException,
    UploadFile,
    status,
)

from rag_eval.adapters import target_adapter_descriptors
from rag_eval.api.dependencies import (
    TargetServiceDep,
    verify_api_key,
)
from rag_eval.api.schemas import (
    TargetAdapterInfo,
    TargetCapabilitiesInfo,
    TargetConfigurationResponse,
    TargetConfigVersionInfo,
    TargetConnectionInfo,
    TargetCreate,
    TargetDetail,
    TargetSummary,
    TargetUpdate,
)
from rag_eval.db.target_models import TargetRecord
from rag_eval.models.enums import TargetConnectionStatus


router = APIRouter(
    prefix="/targets",
    dependencies=[],
)


# ============================================================================
# Serialization helpers
# ============================================================================


async def _target_summary(
    service: TargetServiceDep,
    target: TargetRecord,
) -> TargetSummary:
    """Build frontend-facing target summary."""

    # TargetRecord is deliberately not used as the API schema directly.
    target_id = target.target_id

    connection = await service.get_connection_state(
        target_id
    )

    return TargetSummary(
        target_id=target_id,
        name=target.name,
        adapter_type=target.adapter_type,
        configuration_status=target.configuration_status,
        connection_status=(
            connection.status.value
            if connection is not None
            else TargetConnectionStatus.NOT_TESTED.value
        ),
        current_config_version=target.current_config_version,
        enabled=target.enabled,
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


async def _target_detail(
    service: TargetServiceDep,
    target: TargetRecord,
) -> TargetDetail:
    """Build frontend-facing target detail."""

    connection = await service.get_connection_state(
        target.target_id
    )

    capabilities = await service.get_capabilities(
        target.target_id
    )

    return TargetDetail(
        target_id=target.target_id,
        name=target.name,
        adapter_type=target.adapter_type,
        configuration_status=target.configuration_status,
        connection=(
            connection.model_dump(
                mode="json",
                exclude_none=True,
            )
            if connection is not None
            else None
        ),
        current_config_version=target.current_config_version,
        capabilities=(
            capabilities.model_dump(
                mode="json",
                exclude_none=True,
            )
            if capabilities is not None
            else None
        ),
        enabled=target.enabled,
        metadata=dict(
            target.metadata_json or {}
        ),
        created_at=target.created_at,
        updated_at=target.updated_at,
    )


# ============================================================================
# Adapter catalogue
# ============================================================================


@router.get(
    "/adapters",
    response_model=list[TargetAdapterInfo],
)
async def list_target_adapters() -> list[TargetAdapterInfo]:
    """List registered target integration adapters."""

    return [
        TargetAdapterInfo.model_validate(
            descriptor.model_dump(
                mode="json"
            )
        )
        for descriptor in target_adapter_descriptors()
    ]


# ============================================================================
# Target lifecycle
# ============================================================================


@router.get(
    "",
    response_model=list[TargetSummary],
)
async def list_targets(
    service: TargetServiceDep,
) -> list[TargetSummary]:
    """List evaluator-managed targets."""

    targets = await service.list_targets()

    return [
        await _target_summary(
            service,
            target,
        )
        for target in targets
    ]


@router.post(
    "",
    response_model=TargetDetail,
    status_code=status.HTTP_201_CREATED,
)
async def create_target(
    payload: TargetCreate,
    service: TargetServiceDep,
) -> TargetDetail:
    """Create an empty evaluator-managed target."""

    target = await service.create_target(
        payload.name,
        metadata=payload.metadata,
    )

    return await _target_detail(
        service,
        target,
    )


@router.get(
    "/{target_id}",
    response_model=TargetDetail,
)
async def get_target(
    target_id: str,
    service: TargetServiceDep,
) -> TargetDetail:
    """Return one target."""

    target = await service.get_target(
        target_id
    )

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target not found: {target_id}",
        )

    return await _target_detail(
        service,
        target,
    )


@router.patch(
    "/{target_id}",
    response_model=TargetDetail,
)
async def update_target(
    target_id: str,
    payload: TargetUpdate,
    service: TargetServiceDep,
) -> TargetDetail:
    """Update mutable target properties."""

    try:
        target = await service.update_target(
            target_id,
            name=payload.name,
            metadata=payload.metadata,
            enabled=payload.enabled,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return await _target_detail(
        service,
        target,
    )


@router.delete(
    "/{target_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_target(
    target_id: str,
    service: TargetServiceDep,
) -> None:
    """Delete one evaluator-managed target."""

    try:
        await service.delete_target(
            target_id
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc


# ============================================================================
# YAML configuration
# ============================================================================


@router.put(
    "/{target_id}/configuration",
    response_model=TargetConfigVersionInfo,
)
async def save_target_configuration(
    target_id: str,
    service: TargetServiceDep,
    yaml_content: Annotated[
        str,
        Body(
            media_type="application/yaml",
        ),
    ],
) -> TargetConfigVersionInfo:
    """Save target.yaml as a new immutable configuration version."""

    try:
        record = await service.save_configuration(
            target_id,
            yaml_content,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc

    return TargetConfigVersionInfo(
        config_version_id=record.config_version_id,
        version=record.version,
        schema_version=record.schema_version,
        source_artifact_id=record.source_artifact_id,
        config_hash=record.config_hash,
        created_at=record.created_at,
    )


@router.get(
    "/{target_id}/configuration",
    response_model=TargetConfigurationResponse,
)
async def get_target_configuration(
    target_id: str,
    service: TargetServiceDep,
) -> TargetConfigurationResponse:
    """Return current sanitized editable target.yaml."""

    target = await service.get_target(
        target_id
    )

    if target is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Target not found: {target_id}",
        )

    yaml_content = await service.get_configuration_yaml(
        target_id
    )

    if (
        yaml_content is None
        or target.current_config_version is None
    ):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target has no YAML configuration.",
        )

    return TargetConfigurationResponse(
        target_id=target_id,
        version=target.current_config_version,
        yaml=yaml_content,
    )


@router.get(
    "/{target_id}/configuration/versions",
    response_model=list[TargetConfigVersionInfo],
)
async def list_target_configuration_versions(
    target_id: str,
    service: TargetServiceDep,
) -> list[TargetConfigVersionInfo]:
    """List target configuration history."""

    try:
        records = await service.list_config_versions(
            target_id
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return [
        TargetConfigVersionInfo(
            config_version_id=record.config_version_id,
            version=record.version,
            schema_version=record.schema_version,
            source_artifact_id=record.source_artifact_id,
            config_hash=record.config_hash,
            created_at=record.created_at,
        )
        for record in records
    ]


# ============================================================================
# Uploaded Python adapter
# ============================================================================


@router.post(
    "/{target_id}/adapter-source",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def upload_target_adapter_source(
    target_id: str,
    service: TargetServiceDep,
    file: Annotated[
        UploadFile,
        File(...),
    ],
) -> None:
    """Configure a target from a trusted uploaded Python adapter."""

    filename = (
        file.filename
        or "target_adapter.py"
    )

    if not filename.lower().endswith(".py"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded adapter must be a .py file.",
        )

    content = await file.read()

    if not content:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Uploaded adapter file is empty.",
        )

    try:
        await service.upload_python_adapter(
            target_id,
            content,
            filename=filename,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc


# ============================================================================
# Connection
# ============================================================================


@router.post(
    "/{target_id}/connection-test",
    response_model=TargetConnectionInfo,
)
async def test_target_connection(
    target_id: str,
    service: TargetServiceDep,
) -> TargetConnectionInfo:
    """Test target connectivity and persist the result."""

    try:
        connection = await service.test_connection(
            target_id
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return TargetConnectionInfo.model_validate(
        connection.model_dump(
            mode="json",
            exclude_none=True,
        )
    )


@router.get(
    "/{target_id}/connection",
    response_model=TargetConnectionInfo,
)
async def get_target_connection(
    target_id: str,
    service: TargetServiceDep,
) -> TargetConnectionInfo:
    """Return latest persisted connection state."""

    connection = await service.get_connection_state(
        target_id
    )

    if connection is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Target connection state not found.",
        )

    return TargetConnectionInfo.model_validate(
        connection.model_dump(
            mode="json",
            exclude_none=True,
        )
    )


# ============================================================================
# Capabilities
# ============================================================================


@router.post(
    "/{target_id}/capabilities/discover",
    response_model=TargetCapabilitiesInfo,
)
async def discover_target_capabilities(
    target_id: str,
    service: TargetServiceDep,
) -> TargetCapabilitiesInfo:
    """Discover and persist normalized target capabilities."""

    try:
        capabilities = await service.discover_capabilities(
            target_id
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        ) from exc

    return TargetCapabilitiesInfo(
        target_id=target_id,
        capabilities=capabilities.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )


@router.get(
    "/{target_id}/capabilities",
    response_model=TargetCapabilitiesInfo,
)
async def get_target_capabilities(
    target_id: str,
    service: TargetServiceDep,
) -> TargetCapabilitiesInfo:
    """Return latest persisted normalized capabilities."""

    capabilities = await service.get_capabilities(
        target_id
    )

    if capabilities is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No target capabilities have been discovered.",
        )

    return TargetCapabilitiesInfo(
        target_id=target_id,
        capabilities=capabilities.model_dump(
            mode="json",
            exclude_none=True,
        ),
    )