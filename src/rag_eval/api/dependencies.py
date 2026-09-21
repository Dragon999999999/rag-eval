"""FastAPI application dependencies for rag-eval API.

Provides dependency injection for:
- Database sessions
- Service instances
- Authentication
- Configuration
"""

import os
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession

from rag_eval.artifacts import ArtifactService
from rag_eval.artifacts.base import ArtifactStore
from rag_eval.db.benchmark_repository import BenchmarkRepository
from rag_eval.db.repositories import PersistenceRepository
from rag_eval.db.session import create_async_engine, create_session_factory
from rag_eval.metrics.registry import MetricRegistry
from rag_eval.services.benchmark_service import BenchmarkService
from rag_eval.services.metric_configs import MetricConfigService
from rag_eval.services.test_definitions import TestDefinitionService

# ============================================================================
# Authentication
# ============================================================================

API_KEY_HEADER = APIKeyHeader(name="X-API-Key", auto_error=False)


async def get_api_key(
    api_key_header: Annotated[str | None, Security(API_KEY_HEADER)],
) -> str | None:
    """Extract API key from header.

    Args:
        api_key_header: API key from X-API-Key header.

    Returns:
        API key if provided, None otherwise.

    Note:
        Authentication is optional in development mode.
        Set RAG_EVAL_API_KEY_REQUIRED=true to require authentication.
    """
    if api_key_header:
        return api_key_header

    # Check if API key is required
    if os.getenv("RAG_EVAL_API_KEY_REQUIRED", "false").lower() == "true":
        expected_key = os.getenv("RAG_EVAL_API_KEY")
        if not expected_key:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="RAG_EVAL_API_KEY environment variable not set",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="API key required",
        )

    return None


async def verify_api_key(
    api_key: Annotated[str | None, Depends(get_api_key)],
) -> str | None:
    """Verify API key if required.

    Args:
        api_key: API key from header.

    Returns:
        API key if valid.

    Raises:
        HTTPException: If API key is invalid.
    """
    if not api_key:
        return None

    expected_key = os.getenv("RAG_EVAL_API_KEY")
    if not expected_key:
        # No key configured, allow access
        return api_key

    if api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key",
        )

    return api_key


# ============================================================================
# Database session
# ============================================================================


async def get_db_session(
    request: Request,
) -> AsyncGenerator[AsyncSession, None]:
    """Provide one transaction-scoped database session."""
    session_factory = request.app.state.session_factory

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


DbSession = Annotated[
    AsyncSession,
    Depends(get_db_session),
]


# ============================================================================
# Database repositories
# ============================================================================


def get_repository(
    session: DbSession,
) -> PersistenceRepository:
    """Provide general persistence for the current transaction."""
    return PersistenceRepository(session)


RepositoryDep = Annotated[
    PersistenceRepository,
    Depends(get_repository),
]


def get_benchmark_repository(
    session: DbSession,
) -> BenchmarkRepository:
    """Provide benchmark-specific persistence."""
    return BenchmarkRepository(session)


BenchmarkRepositoryDep = Annotated[
    BenchmarkRepository,
    Depends(get_benchmark_repository),
]


# ============================================================================
# Artifact services
# ============================================================================


def get_artifact_store(
    request: Request,
) -> ArtifactStore:
    """Return the application-lifetime artifact store."""
    return request.app.state.artifact_store


ArtifactStoreDep = Annotated[
    ArtifactStore,
    Depends(get_artifact_store),
]


def get_artifact_service(
    repository: RepositoryDep,
    store: ArtifactStoreDep,
) -> ArtifactService:
    """Provide transaction-aware artifact coordination."""
    return ArtifactService(
        store,
        repository,
    )


ArtifactServiceDep = Annotated[
    ArtifactService,
    Depends(get_artifact_service),
]


# ============================================================================
# Benchmark service
# ============================================================================


def get_benchmark_service(
    repository: BenchmarkRepositoryDep,
    artifact_service: ArtifactServiceDep,
) -> BenchmarkService:
    """Provide benchmark management and conversion service."""
    return BenchmarkService(
        repository,
        artifact_service,
    )


BenchmarkServiceDep = Annotated[
    BenchmarkService,
    Depends(get_benchmark_service),
]

# ============================================================================
# Services
# ============================================================================


def get_metric_registry() -> MetricRegistry:
    """Get metric registry instance.

    Returns:
        Shared MetricRegistry instance.
    """
    return MetricRegistry()


MetricRegistryDep = Annotated[MetricRegistry, Depends(get_metric_registry)]


async def get_metric_config_service(
    session: DbSession,
    registry: MetricRegistryDep,
) -> MetricConfigService:
    """Get metric configuration service.

    Args:
        session: Database session.
        registry: Metric registry.

    Returns:
        MetricConfigService instance.
    """
    return MetricConfigService(session, metric_registry=registry)


MetricConfigServiceDep = Annotated[
    MetricConfigService, Depends(get_metric_config_service)
]


async def get_test_definition_service(
    session: DbSession,
) -> TestDefinitionService:
    """Get test definition service.

    Args:
        session: Database session.

    Returns:
        TestDefinitionService instance.
    """
    return TestDefinitionService(session)


TestDefinitionServiceDep = Annotated[
    TestDefinitionService, Depends(get_test_definition_service)
]


# ============================================================================
# Common Dependencies
# ============================================================================


async def get_pagination_params(
    limit: int = 100,
    offset: int = 0,
) -> dict[str, int]:
    """Get pagination parameters.

    Args:
        limit: Maximum items to return.
        offset: Number of items to skip.

    Returns:
        Dictionary with limit and offset.
    """
    # Validate limits
    if limit < 1:
        limit = 1
    if limit > 1000:
        limit = 1000
    if offset < 0:
        offset = 0

    return {"limit": limit, "offset": offset}


PaginationDep = Annotated[dict[str, int], Depends(get_pagination_params)]
