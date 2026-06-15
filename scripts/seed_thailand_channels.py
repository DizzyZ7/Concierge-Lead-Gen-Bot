from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from core.config import get_settings
from db.queries import add_channel, list_channels, set_channel_delay, set_channel_limit
from db.session import create_engine, create_session_factory


@dataclass(frozen=True)
class ChannelSeed:
    username: str
    geo: str
    category: str
    daily_limit: int = 5
    delay_min: int = 0
    delay_max: int = 0


CHANNELS = [
    ChannelSeed("@phuket_f", "thailand", "realty", 8),
    ChannelSeed("@ru_chat_thailand", "thailand", "expat_life", 8),
    ChannelSeed("@thailand_russia_ru", "thailand", "relocation", 8),
    ChannelSeed("@dengivezde", "thailand", "finance", 3),
    ChannelSeed("@delaumoney", "thailand", "business", 3),
    ChannelSeed("@TrueBusines", "thailand", "business", 3),
    ChannelSeed("@nowtrendbrand", "thailand", "business", 3),
    ChannelSeed("@BusinesAdvisor", "thailand", "business", 3),
]


async def main() -> None:
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    async with session_factory() as session:
        existing = {channel.channel_username.lower(): channel for channel in await list_channels(session)}
        for item in CHANNELS:
            key = item.username.lower()
            if key in existing:
                channel = existing[key]
                await set_channel_limit(session, channel.id, item.daily_limit)
                await set_channel_delay(session, channel.id, item.delay_min, item.delay_max)
                print(f"Updated channel: {item.username}")
                continue
            try:
                channel = await add_channel(session, item.username, item.geo, item.category)
                await set_channel_limit(session, channel.id, item.daily_limit)
                await set_channel_delay(session, channel.id, item.delay_min, item.delay_max)
                print(f"Added channel: {item.username}")
            except IntegrityError:
                await session.rollback()
                print(f"Skipped duplicate channel: {item.username}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
