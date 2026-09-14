"""Declarative metadata registry for future relational persistence models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class whose metadata is used by Alembic migrations."""
