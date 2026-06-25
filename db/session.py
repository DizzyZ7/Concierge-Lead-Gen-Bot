from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def normalize_database_url(database_url: str) -> str:
    """Return an asyncpg SQLAlchemy URL for PostgreSQL connections."""
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url.removeprefix("postgresql://")
    return database_url


def create_engine(database_url: str) -> AsyncEngine:
    """Create async SQLAlchemy engine."""
    return create_async_engine(normalize_database_url(database_url), pool_pre_ping=True, pool_size=5, max_overflow=10)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)
