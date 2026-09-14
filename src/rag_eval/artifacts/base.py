"""Backend-neutral asynchronous artifact byte-storage contract."""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import BinaryIO

from rag_eval.models import ArtifactRef, ArtifactType

ArtifactInput = bytes | Path | BinaryIO


class ArtifactStore(ABC):
    """Store and retrieve immutable artifact bytes using canonical references."""

    @abstractmethod
    async def put(
        self,
        content: ArtifactInput,
        artifact_type: ArtifactType,
        *,
        content_type: str | None = None,
        metadata: dict[str, object] | None = None,
        expected_sha256: str | None = None,
    ) -> ArtifactRef:
        """Persist bytes and return their canonical immutable reference."""

    @abstractmethod
    async def get(self, artifact: ArtifactRef) -> bytes:
        """Return the exact bytes addressed by a canonical reference."""

    @abstractmethod
    async def exists(self, artifact: ArtifactRef) -> bool:
        """Return whether this backend currently contains the artifact bytes."""

    @abstractmethod
    async def delete(self, artifact: ArtifactRef) -> None:
        """Delete an artifact object when lifecycle policy explicitly permits it."""
