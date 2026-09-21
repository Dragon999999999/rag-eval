"""Focused API tests for target lifecycle and error translation."""

from __future__ import annotations

import pytest
from fastapi import HTTPException

from rag_eval.api import targets
from rag_eval.api.schemas import TargetCreate
from rag_eval.models import TargetConnectionState


@pytest.mark.anyio
async def test_adapter_catalogue_publishes_registered_adapters() -> None:
    """The API catalogue is sourced from the canonical adapter registry."""
    descriptors = await targets.list_target_adapters()
    adapter_types = {descriptor.type for descriptor in descriptors}
    assert {"python", "generic_http", "uploaded_python"} <= adapter_types


@pytest.mark.anyio
async def test_target_api_translates_missing_and_invalid_configuration() -> None:
    """Target configuration routes preserve 404 and 422 semantics."""

    class MissingService:
        async def save_configuration(self, target_id: str, content: str):
            raise KeyError(target_id)

    with pytest.raises(HTTPException) as missing:
        await targets.save_target_configuration(
            "missing", MissingService(), "adapter: {}"
        )
    assert missing.value.status_code == 404

    class InvalidService:
        async def save_configuration(self, target_id: str, content: str):
            raise ValueError("invalid adapter")

    with pytest.raises(HTTPException) as invalid:
        await targets.save_target_configuration(
            "target-1", InvalidService(), "adapter: {}"
        )
    assert invalid.value.status_code == 422


@pytest.mark.anyio
async def test_target_api_upload_validates_extension_and_empty_files() -> None:
    """Python adapter uploads reject unsupported and empty files before persistence."""

    class Service:
        calls = 0

        async def upload_python_adapter(
            self,
            target_id: str,
            content: bytes,
            *,
            filename: str,
        ) -> None:
            self.calls += 1

    class FakeUpload:
        def __init__(self, filename: str, content: bytes) -> None:
            self.filename = filename
            self.content = content

        async def read(self) -> bytes:
            return self.content

    service = Service()
    with pytest.raises(HTTPException) as bad_extension:
        await targets.upload_target_adapter_source(
            "target-1",
            service,
            FakeUpload("adapter.txt", b"print('no')"),  # type: ignore[arg-type]
        )
    assert bad_extension.value.status_code == 422

    with pytest.raises(HTTPException) as empty:
        await targets.upload_target_adapter_source(
            "target-1",
            service,
            FakeUpload("adapter.py", b""),  # type: ignore[arg-type]
        )
    assert empty.value.status_code == 422
    assert service.calls == 0


@pytest.mark.anyio
async def test_target_api_connection_not_found_is_404() -> None:
    """Connection testing maps missing target state to a not-found response."""

    class MissingService:
        async def test_connection(self, target_id: str) -> TargetConnectionState:
            raise KeyError(target_id)

    with pytest.raises(HTTPException) as missing:
        await targets.test_target_connection("missing", MissingService())
    assert missing.value.status_code == 404


@pytest.mark.anyio
async def test_target_api_duplicate_creation_is_409() -> None:
    """Repository duplicate errors are exposed as a conflict response."""

    class ConflictService:
        async def create_target(self, name: str, *, metadata: dict | None = None):
            raise ValueError("target already exists")

    with pytest.raises(HTTPException) as conflict:
        await targets.create_target(TargetCreate(name="demo"), ConflictService())
    assert conflict.value.status_code == 409
