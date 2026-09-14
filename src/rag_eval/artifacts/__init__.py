"""Durable local and S3-compatible artifact byte storage."""

from rag_eval.artifacts.base import ArtifactStore
from rag_eval.artifacts.local import LocalArtifactStore
from rag_eval.artifacts.s3 import S3ArtifactStore
from rag_eval.artifacts.service import ArtifactService


def create_artifact_store(settings: object) -> ArtifactStore:
    """Create an artifact store from settings.
    
    Args:
        settings: Application settings with S3 configuration.
    
    Returns:
        Artifact store implementation (S3 or local).
    """
    # Check if S3 is configured
    s3_endpoint = getattr(settings, "s3_endpoint_url", None)
    s3_bucket = getattr(settings, "s3_bucket", "rag-eval-artifacts")
    s3_access_key = getattr(settings, "s3_access_key", None)
    s3_secret_key = getattr(settings, "s3_secret_key", None)
    s3_region = getattr(settings, "s3_region", "us-east-1")
    
    if s3_endpoint and s3_access_key and s3_secret_key:
        return S3ArtifactStore(
            endpoint_url=s3_endpoint,
            bucket=s3_bucket,
            access_key=s3_access_key,
            secret_key=s3_secret_key,
            region=s3_region,
        )
    else:
        # Fall back to local storage for development
        import tempfile
        from pathlib import Path
        
        local_dir = Path(tempfile.mkdtemp(prefix="rag-eval-artifacts-"))
        return LocalArtifactStore(root_dir=local_dir)


__all__ = [
    "ArtifactService",
    "ArtifactStore",
    "LocalArtifactStore",
    "S3ArtifactStore",
    "create_artifact_store",
]
