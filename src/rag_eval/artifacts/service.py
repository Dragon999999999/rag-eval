"""Coordinate artifact byte storage with PostgreSQL metadata registration."""

import json

from rag_eval.artifacts.base import ArtifactInput, ArtifactStore
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.models import ArtifactRef, ArtifactType


class ArtifactService:
    """Store durable bytes before registering their metadata transactionally."""

    def __init__(self, store: ArtifactStore, repository: PersistenceRepository) -> None:
        """Bind one byte-store implementation and Stage 4 metadata repository."""
        self._store = store
        self._repository = repository

    async def put(
        self,
        content: ArtifactInput,
        artifact_type: ArtifactType,
        *,
        content_type: str | None = None,
        metadata: dict[str, object] | None = None,
        expected_sha256: str | None = None,
    ) -> ArtifactRef:
        """Store bytes first, then persist metadata and return a canonical reference."""

        artifact = await self._store.put(
            content,
            artifact_type,
            content_type=content_type,
            metadata=metadata,
            expected_sha256=expected_sha256,
        )

        await self._repository.persist_artifact(
            artifact,
            artifact_type.value,
        )

        return artifact

    async def put_text(
        self,
        text: str,
        artifact_type: ArtifactType,
        *,
        content_type: str | None = None,
        metadata: dict[str, object] | None = None,
        expected_sha256: str | None = None,
    ) -> ArtifactRef:
        """Encode UTF-8 text through the shared byte-storage primitive."""

        return await self.put(
            text.encode("utf-8"),
            artifact_type,
            content_type=content_type,
            metadata=metadata,
            expected_sha256=expected_sha256,
        )

    async def put_json(
        self,
        value: object,
        artifact_type: ArtifactType,
        *,
        content_type: str = "application/json",
        metadata: dict[str, object] | None = None,
        expected_sha256: str | None = None,
    ) -> ArtifactRef:
        """Serialize deterministic JSON through the shared byte-storage primitive."""

        data = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")

        return await self.put(
            data,
            artifact_type,
            content_type=content_type,
            metadata=metadata,
            expected_sha256=expected_sha256,
        )

    async def get_json(self, artifact: ArtifactRef) -> object:
        """Load UTF-8 JSON through the shared byte retrieval primitive."""
        return json.loads((await self._store.get(artifact)).decode("utf-8"))

    async def get(self, artifact: ArtifactRef) -> bytes:
        """Return durable artifact bytes without creating a duplicate artifact."""
        return await self._store.get(artifact)
