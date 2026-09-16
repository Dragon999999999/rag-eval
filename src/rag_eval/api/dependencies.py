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

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from rag_eval.db.session import create_async_session_factory
from rag_eval.metrics.registry import MetricRegistry
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
# Database
# ============================================================================


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Get async database session.

    Yields:
        AsyncSession for database operations.

    Note:
        Session is automatically closed after use.
    """
    from rag_eval.config import get_settings

    settings = get_settings()
    session_factory = create_async_session_factory(settings)

    async with session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


# Type alias for dependency-injected session
DbSession = Annotated[AsyncSession, Depends(get_db_session)]


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
