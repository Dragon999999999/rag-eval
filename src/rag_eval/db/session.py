"""Factories for asynchronous PostgreSQL database resources."""

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine as sqlalchemy_create_async_engine

from rag_eval.config import Settings


def create_async_engine(settings: Settings) -> AsyncEngine:
    """Create an async PostgreSQL engine without opening a database connection.

    Args:
        settings: Application database configuration.

    Returns:
        Engine suitable for short-lived sessions and application startup wiring.
    """
    return sqlalchemy_create_async_engine(
        settings.async_database_url,
        pool_pre_ping=True,
    )


def create_session_factory(
    engine: AsyncEngine,
) -> async_sessionmaker[AsyncSession]:
    """Create sessions that do not expire values immediately after commits."""
    return async_sessionmaker(engine, expire_on_commit=False)
