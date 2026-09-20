"""Atomic local filesystem backend for development and small local runs."""

import hashlib
import os
import tempfile
from pathlib import Path

from rag_eval.artifacts.base import ArtifactInput, ArtifactStore
from rag_eval.models import ArtifactRef, ArtifactType


class LocalArtifactStore(ArtifactStore):
    """Store immutable content-addressed artifacts beneath one safe root path."""

    def __init__(self, root: Path) -> None:
        """Configure the local root; it is created lazily on first write."""
        self._root = root.resolve()

    async def put(
        self,
        content: ArtifactInput,
        artifact_type: ArtifactType,
        *,
        content_type: str | None = None,
        metadata: dict[str, object] | None = None,
        expected_sha256: str | None = None,
    ) -> ArtifactRef:
        return self._put_sync(
            content,
            artifact_type,
            content_type=content_type,
            metadata=metadata,
            expected_sha256=expected_sha256,
        )

    def _put_sync(
        self,
        content: ArtifactInput,
        artifact_type: ArtifactType,
        *,
        content_type: str | None = None,
        metadata: dict[str, object] | None = None,
        expected_sha256: str | None = None,
    ) -> ArtifactRef:
        """Write one temporary file while calculating its exact SHA-256."""
        artifact_metadata = dict(metadata or {})

        self._root.mkdir(parents=True, exist_ok=True)
        handle, temporary_name = tempfile.mkstemp(
            dir=self._root,
            prefix=".artifact-",
        )

        digest = hashlib.sha256()
        size = 0

        try:
            with os.fdopen(handle, "wb") as destination:
                for chunk in _chunks(content):
                    destination.write(chunk)
                    digest.update(chunk)
                    size += len(chunk)

                destination.flush()

            sha256 = digest.hexdigest()

            if expected_sha256 is not None and sha256 != expected_sha256:
                raise ValueError(
                    "artifact SHA-256 does not match expected_sha256"
                )

            final_path = self._path_for_hash(sha256)
            final_path.parent.mkdir(parents=True, exist_ok=True)

            if not final_path.exists():
                os.replace(temporary_name, final_path)
                temporary_name = ""

            return ArtifactRef(
                artifact_id=f"{artifact_type.value.lower()}-{sha256}",
                uri=final_path.as_uri(),
                sha256=sha256,
                size_bytes=size,
                content_type=content_type,
                metadata=artifact_metadata,
            )

        finally:
            if temporary_name:
                Path(temporary_name).unlink(missing_ok=True)

    async def get(self, artifact: ArtifactRef) -> bytes:
        """Read artifact bytes only after validating that the URI stays in root."""
        return self._resolve(artifact).read_bytes()

    async def exists(self, artifact: ArtifactRef) -> bool:
        """Check for an artifact within the configured root only."""
        return self._resolve(artifact).exists()

    async def delete(self, artifact: ArtifactRef) -> None:
        """Remove one content-addressed local artifact when explicitly requested."""
        self._delete_sync(artifact)

    def _delete_sync(self, artifact: ArtifactRef) -> None:
        """Delete a validated local artifact path if it is present."""
        self._resolve(artifact).unlink(missing_ok=True)

    def _path_for_hash(self, sha256: str) -> Path:
        """Create a collision-safe deterministic layout from a content hash."""
        return self._root / "artifacts" / sha256[:2] / sha256

    def _resolve(self, artifact: ArtifactRef) -> Path:
        """Resolve a local URI and reject attempts to escape the configured root."""
        if not artifact.uri.startswith("file://"):
            raise ValueError("local artifact store requires a file URI")
        path = Path(artifact.uri.removeprefix("file://")).resolve()
        if self._root != path and self._root not in path.parents:
            raise ValueError("artifact path escapes configured root")
        return path


def _chunks(content: ArtifactInput, size: int = 1024 * 1024):
    """Yield practical chunks from bytes, paths, or a binary file-like object."""
    if isinstance(content, bytes):
        yield content
        return
    if isinstance(content, Path):
        with content.open("rb") as source:
            while chunk := source.read(size):
                yield chunk
        return
    while chunk := content.read(size):
        yield chunk
