from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Final

from alembic import command
from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

REQUIRED_ALEMBIC_REVISION: Final = "0010_reviewer_claims"


class SchemaNotReadyError(RuntimeError):
    """Raised when the database schema is not at the required Alembic revision."""


def _alembic_config() -> Config:
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "db" / "migrations"))
    config.set_main_option("prepend_sys_path", str(root))
    return config


def upgrade_schema_to_head_sync() -> None:
    command.upgrade(_alembic_config(), "head")


async def upgrade_schema_to_head() -> None:
    """Run Alembic migrations from async startup without nesting event loops."""
    await asyncio.to_thread(upgrade_schema_to_head_sync)


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
            "Выполни на BotHost shell: python -m alembic upgrade head"
        )
    return current_revision
