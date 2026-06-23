from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

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
