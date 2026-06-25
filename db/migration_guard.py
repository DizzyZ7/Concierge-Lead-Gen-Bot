from __future__ import annotations

from typing import Final

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

REQUIRED_ALEMBIC_REVISION: Final = "0010_reviewer_claims"


class SchemaNotReadyError(RuntimeError):
    pass


async def current_schema_revision(session: AsyncSession) -> str | None:
    try:
        revision = await session.scalar(text("SELECT version_num FROM alembic_version LIMIT 1"))
    except SQLAlchemyError:
        return None
    return str(revision) if revision else None


async def ensure_schema_current(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        current_revision = await current_schema_revision(session)
    if current_revision != REQUIRED_ALEMBIC_REVISION:
        actual = current_revision or "не найдена"
        raise SchemaNotReadyError(
            "Схема БД не готова: "
            f"текущая revision={actual}, требуется={REQUIRED_ALEMBIC_REVISION}. "
            "Выполни: docker compose run --rm bot alembic upgrade head"
        )
    return current_revision
