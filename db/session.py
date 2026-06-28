from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine


def normalize_database_url(database_url: str) -> str:
    """Return an asyncpg SQLAlchemy URL for PostgreSQL connections."""
    database_url = database_url.strip().strip('"').strip("'").strip()
    if database_url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + database_url.removeprefix("postgresql://")
    return database_url


def create_engine(database_url: str) -> AsyncEngine:
    """Create async SQLAlchemy engine."""
    return create_async_engine(normalize_database_url(database_url), pool_pre_ping=True, pool_size=5, max_overflow=10)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    """Create async session factory."""
    return async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)


async def check_database_connection(engine: AsyncEngine) -> None:
    """Verify that the configured database is reachable."""
    try:
        async with engine.connect() as connection:
            await connection.execute(text("select 1"))
    except SQLAlchemyError:
        raise
