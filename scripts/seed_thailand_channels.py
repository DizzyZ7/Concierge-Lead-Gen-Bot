from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.exc import IntegrityError

from core.config import get_settings
from db.queries import (
    add_channel,
    list_channels,
    set_channel_allowed_intents,
    set_channel_blocked_keywords,
    set_channel_delay,
    set_channel_limit,
    set_channel_min_score,
)
from db.session import create_engine, create_session_factory


@dataclass(frozen=True)
class ChannelSeed:
    username: str
    geo: str
    category: str
    daily_limit: int = 5
    delay_min: int = 3
    delay_max: int = 18
    min_score: float | None = None
    allowed_intents: str | None = None
    blocked_keywords: str | None = None


CHANNELS = [
    ChannelSeed("@phuket_f", "thailand", "realty", 8, 3, 18, 0.62, "realty,investment,expat_life"),
    ChannelSeed("@ru_chat_thailand", "thailand", "expat_life", 8, 4, 22, 0.68, "relocation,realty,visa,expat_life,tourism"),
    ChannelSeed("@thailand_russia_ru", "thailand", "relocation", 8, 4, 22, 0.68, "relocation,realty,visa,expat_life,tourism"),
    ChannelSeed("@dengivezde", "thailand", "finance", 3, 10, 40, 0.78, "investment,business,finance"),
    ChannelSeed("@delaumoney", "thailand", "business", 3, 10, 40, 0.80, "investment,business,finance"),
    ChannelSeed("@TrueBusines", "thailand", "business", 3, 10, 40, 0.80, "investment,business,finance"),
    ChannelSeed("@nowtrendbrand", "thailand", "business", 3, 10, 40, 0.80, "investment,business,finance"),
    ChannelSeed("@BusinesAdvisor", "thailand", "business", 3, 10, 40, 0.80, "investment,business,finance"),
]


async def apply_channel_settings(session, channel, item: ChannelSeed) -> None:
    await set_channel_limit(session, channel.id, item.daily_limit)
    await set_channel_delay(session, channel.id, item.delay_min, item.delay_max)
    await set_channel_min_score(session, channel.id, item.min_score)
    await set_channel_allowed_intents(session, channel.id, item.allowed_intents)
    await set_channel_blocked_keywords(session, channel.id, item.blocked_keywords)


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
                await apply_channel_settings(session, channel, item)
                print(f"Updated channel: {item.username}")
                continue
            try:
                channel = await add_channel(session, item.username, item.geo, item.category)
                await apply_channel_settings(session, channel, item)
                print(f"Added channel: {item.username}")
            except IntegrityError:
                await session.rollback()
                print(f"Skipped duplicate channel: {item.username}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
