from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from db import queries
from db.models import TargetChannel

VALIDATION_MAX_AGE = timedelta(days=7)


@dataclass(frozen=True)
class ChannelValidationResult:
    channel_id: int
    username: str
    ok: bool
    title: str | None = None
    error: str | None = None


def is_channel_validation_fresh(
    checked_at: datetime | None,
    error: str | None,
    *,
    now: datetime | None = None,
) -> bool:
    if checked_at is None or error:
        return False
    current = now or datetime.now(timezone.utc)
    checked = checked_at if checked_at.tzinfo else checked_at.replace(tzinfo=timezone.utc)
    return current - checked <= VALIDATION_MAX_AGE


async def validate_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> list[ChannelValidationResult]:
    async with session_factory() as session:
        channels = await queries.list_channels(session)

    checked_at = datetime.now(timezone.utc)
    results: list[ChannelValidationResult] = []
    for channel in channels:
        try:
            entity = await client.get_entity(channel.channel_username)
            title = str(getattr(entity, "title", "") or "") or None
            results.append(
                ChannelValidationResult(
                    channel_id=channel.id,
                    username=channel.channel_username,
                    ok=True,
                    title=title,
                )
            )
        except Exception as error:
            results.append(
                ChannelValidationResult(
                    channel_id=channel.id,
                    username=channel.channel_username,
                    ok=False,
                    error=f"{error.__class__.__name__}: {str(error) or 'без текста'}"[:300],
                )
            )

    async with session_factory() as session:
        for result in results:
            row = await session.get(TargetChannel, result.channel_id)
            if not row:
                continue
            row.last_validation_at = checked_at
            if result.ok:
                row.channel_title = result.title
                row.last_validation_error = None
            else:
                row.last_validation_error = result.error
        await session.commit()

    return results
