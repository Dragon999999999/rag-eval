"""Focused async repositories for durable application persistence."""

from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.db.models import ArtifactRecord
from rag_eval.models import ArtifactRef


class PersistenceRepository:
    """Explicit database operations with caller-managed transaction scope."""

    def __init__(self, session: AsyncSession) -> None:
        """Bind this repository to one caller-managed async session."""
        self._session = session


    # -------------------------------------------------------------------------
    # Artifacts
    # -------------------------------------------------------------------------

    async def persist_artifact(
        self,
        artifact: ArtifactRef,
        artifact_type: str,
    ) -> ArtifactRecord:
        """Persist artifact metadata without duplicating stored bytes."""
        record = await self._session.get(
            ArtifactRecord,
            artifact.artifact_id,
        )

        values = {
            "artifact_type": artifact_type,
            "uri": artifact.uri,
            "sha256": artifact.sha256,
            "size_bytes": artifact.size_bytes,
            "content_type": artifact.content_type,
            "metadata_json": artifact.metadata,
        }

        if record is None:
            record = ArtifactRecord(
                artifact_id=artifact.artifact_id,
                **values,
            )
            self._session.add(record)
        else:
            for name, value in values.items():
                setattr(record, name, value)

        await self._session.flush()
        return record

    async def get_artifact(
        self,
        artifact_id: str,
    ) -> ArtifactRef | None:
        """Reload artifact metadata as a canonical reference."""
        record = await self._session.get(
            ArtifactRecord,
            artifact_id,
        )

        if record is None:
            return None

        return ArtifactRef(
            artifact_id=record.artifact_id,
            uri=record.uri,
            sha256=record.sha256,
            size_bytes=record.size_bytes,
            content_type=record.content_type,
            created_at=record.created_at,
            metadata=dict(record.metadata_json or {}),
        )