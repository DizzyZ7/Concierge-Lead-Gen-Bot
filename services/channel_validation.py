from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from telethon import TelegramClient

from db import queries
from db.models import TargetChannel


@dataclass(frozen=True)
class ChannelValidationResult:
    channel_id: int
    username: str
    ok: bool
    title: str | None = None
    error: str | None = None


async def validate_channels(
    client: TelegramClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> list[ChannelValidationResult]:
    async with session_factory() as session:
        channels = await queries.list_channels(session)

    results: list[ChannelValidationResult] = []
    titles: dict[int, str | None] = {}
    for channel in channels:
        try:
            entity = await client.get_entity(channel.channel_username)
            title = str(getattr(entity, "title", "") or "") or None
            titles[channel.id] = title
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

    if titles:
        async with session_factory() as session:
            for channel_id, title in titles.items():
                row = await session.get(TargetChannel, channel_id)
                if row:
                    row.channel_title = title
            await session.commit()

    return results
