"""Database module for the transcoding pipeline."""

import asyncio
from contextlib import asynccontextmanager

from sqlalchemy import MetaData, create_engine
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    create_async_engine,
)
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# Naming convention for consistent constraint names
naming_convention = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=naming_convention)


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    metadata = metadata


# Engine factories - initialized lazily
_async_engine: AsyncSession | None = None
_async_session_factory: sessionmaker | None = None


def init_db() -> None:
    """Initialize the async database engine and session factory."""
    global _async_engine, _async_session_factory

    from app.core.config import get_settings

    settings = get_settings()

    database_url = (
        f"postgresql+asyncpg://"
        f"{settings.POSTGRES_USER or 'postgres'}:"
        f"{settings.POSTGRES_PASSWORD or 'postgres'}@"
        f"{settings.POSTGRES_HOST or 'postgres'}:"
        f"{settings.POSTGRES_PORT or 5432}/"
        f"{settings.POSTGRES_DB or 'transcode_db'}"
    )

    _async_engine = create_async_engine(
        database_url,
        echo=settings.DEBUG if hasattr(settings, "DEBUG") else False,
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=3600,
    )

    _async_session_factory = sessionmaker(
        _async_engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
        autocommit=False,
    )


async def close_db() -> None:
    """Close the database engine."""
    global _async_engine

    if _async_engine:
        await _async_engine.dispose()
        _async_engine = None
        _async_session_factory = None


def get_session_factory() -> sessionmaker:
    """Get the session factory (for health checks / testing)."""
    if _async_session_factory is None:
        init_db()
    return _async_session_factory