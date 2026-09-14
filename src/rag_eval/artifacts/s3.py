"""S3-compatible artifact backend, including MinIO endpoint support."""

import asyncio
import hashlib
import io

import boto3
from botocore.exceptions import ClientError

from rag_eval.artifacts.base import ArtifactInput, ArtifactStore
from rag_eval.artifacts.local import _chunks
from rag_eval.models import ArtifactRef, ArtifactType


class S3ArtifactStore(ArtifactStore):
    """Store immutable artifacts in a configured S3-compatible bucket."""

    def __init__(
        self,
        *,
        endpoint_url: str,
        bucket: str,
        access_key: str,
        secret_key: str,
        region: str,
    ) -> None:
        """Configure an S3 client without contacting the remote service yet."""
        self._bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    async def put(
        self, content: ArtifactInput, artifact_type: ArtifactType, **kwargs: object
    ) -> ArtifactRef:
        """Upload bytes after calculating and checking their content hash."""
        return await asyncio.to_thread(self._put_sync, content, artifact_type, **kwargs)

    def _put_sync(
        self, content: ArtifactInput, artifact_type: ArtifactType, **kwargs: object
    ) -> ArtifactRef:
        """Materialize one upload stream while preserving its exact checksum."""
        data = b"".join(_chunks(content))
        sha256 = hashlib.sha256(data).hexdigest()
        expected = kwargs.get("expected_sha256")
        if expected is not None and sha256 != expected:
            raise ValueError("artifact SHA-256 does not match expected_sha256")
        key = f"artifacts/{sha256[:2]}/{sha256}"
        extra: dict[str, object] = {}
        if isinstance(kwargs.get("content_type"), str):
            extra["ContentType"] = kwargs["content_type"]
        self._client.upload_fileobj(
            io.BytesIO(data), self._bucket, key, ExtraArgs=extra
        )
        return ArtifactRef(
            artifact_id=f"{artifact_type.value.lower()}-{sha256}",
            uri=f"s3://{self._bucket}/{key}",
            sha256=sha256,
            size_bytes=len(data),
            content_type=kwargs.get("content_type")
            if isinstance(kwargs.get("content_type"), str)
            else None,
            metadata=dict(kwargs.get("metadata") or {}),
        )

    async def get(self, artifact: ArtifactRef) -> bytes:
        """Download exact bytes for a bucket-local canonical S3 URI."""
        return await asyncio.to_thread(self._get_sync, artifact)

    def _get_sync(self, artifact: ArtifactRef) -> bytes:
        """Read one object while rejecting a URI from a different bucket."""
        key = self._key(artifact)
        return self._client.get_object(Bucket=self._bucket, Key=key)["Body"].read()

    async def exists(self, artifact: ArtifactRef) -> bool:
        """Check object existence without exposing backend exceptions for absence."""
        return await asyncio.to_thread(self._exists_sync, artifact)

    def _exists_sync(self, artifact: ArtifactRef) -> bool:
        """Translate only S3 not-found results into ``False``."""
        try:
            self._client.head_object(Bucket=self._bucket, Key=self._key(artifact))
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in {
                "404",
                "NoSuchKey",
                "NotFound",
            }:
                return False
            raise
        return True

    async def delete(self, artifact: ArtifactRef) -> None:
        """Delete one object from the configured bucket."""
        await asyncio.to_thread(
            self._client.delete_object, Bucket=self._bucket, Key=self._key(artifact)
        )

    def _key(self, artifact: ArtifactRef) -> str:
        """Extract a key only from this store's configured S3 bucket."""
        prefix = f"s3://{self._bucket}/"
        if not artifact.uri.startswith(prefix):
            raise ValueError("artifact URI is outside configured S3 bucket")
        return artifact.uri.removeprefix(prefix)
