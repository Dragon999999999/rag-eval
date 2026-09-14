"""Unit coverage for the real atomic local artifact backend."""

import hashlib
from pathlib import Path

import pytest

from rag_eval.artifacts import LocalArtifactStore
from rag_eval.models import ArtifactRef, ArtifactType


@pytest.mark.anyio
async def test_local_artifact_round_trip_hash_and_duplicate_content(
    tmp_path: Path,
) -> None:
    """Content-addressed local storage preserves bytes, size, and SHA-256."""
    store = LocalArtifactStore(tmp_path / "artifacts")
    content = b"raw target response"
    first = await store.put(
        content, ArtifactType.RAW_TARGET_RESPONSE, content_type="text/plain"
    )
    second = await store.put(content, ArtifactType.RAW_TARGET_RESPONSE)

    assert await store.get(first) == content
    assert first.sha256 == hashlib.sha256(content).hexdigest()
    assert first.size_bytes == len(content)
    assert first.content_type == "text/plain"
    assert first.uri == second.uri
    assert await store.exists(first)


@pytest.mark.anyio
async def test_local_artifact_rejects_hash_mismatch_and_path_escape(
    tmp_path: Path,
) -> None:
    """Corruption and traversal attempts cannot create or read final artifacts."""
    store = LocalArtifactStore(tmp_path / "artifacts")
    with pytest.raises(ValueError, match="SHA-256"):
        await store.put(b"bytes", ArtifactType.OTHER, expected_sha256="0" * 64)

    escaped = ArtifactRef(
        artifact_id="escape", uri="file:///tmp/escape", sha256="a" * 64
    )
    with pytest.raises(ValueError, match="escapes"):
        await store.get(escaped)


@pytest.mark.anyio
async def test_local_artifact_json_helpers_work_through_store(tmp_path: Path) -> None:
    """Local store supports file inputs and safe deletion after finalization."""
    store = LocalArtifactStore(tmp_path / "artifacts")
    source = tmp_path / "input.bin"
    source.write_bytes(b"from-path")
    artifact = await store.put(source, ArtifactType.SOURCE_DOCUMENT)

    assert await store.get(artifact) == b"from-path"
    await store.delete(artifact)
    assert not await store.exists(artifact)
