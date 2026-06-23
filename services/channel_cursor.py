from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from telethon import TelegramClient

from db.models import TargetChannel


async def advance_channel_cursor(session: AsyncSession, channel_id: int, message_id: int) -> None:
    channel = await session.get(TargetChannel, channel_id)
    if not channel:
        return
    current = channel.last_seen_message_id or 0
    if message_id <= current:
        return
    channel.last_seen_message_id = message_id
    await session.commit()


async def reset_channel_cursor(session: AsyncSession, channel_id: int) -> bool:
    channel = await session.get(TargetChannel, channel_id)
    if not channel:
        return False
    channel.last_seen_message_id = None
    await session.commit()
    return True


async def iter_unseen_messages(
    client: TelegramClient,
    entity: Any,
    *,
    last_seen_message_id: int | None,
    limit: int,
) -> AsyncIterator[Any]:
    """Yield a bounded chronological batch without skipping unseen messages after a stored cursor."""
    if last_seen_message_id:
        async for message in client.iter_messages(
            entity,
            min_id=last_seen_message_id,
            reverse=True,
            limit=limit,
        ):
            yield message
        return

    initial_batch = [message async for message in client.iter_messages(entity, limit=limit)]
    for message in reversed(initial_batch):
        yield message
