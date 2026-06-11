from __future__ import annotations

import asyncio
from pathlib import Path

from telethon import TelegramClient

from core.config import get_settings


async def main() -> None:
    settings = get_settings()
    if not settings.tg_api_id or not settings.tg_api_hash:
        raise RuntimeError("TG_API_ID and TG_API_HASH are required for Telegram session login")
    session_dir = Path("sessions")
    session_dir.mkdir(exist_ok=True)
    session_path = session_dir / settings.tg_session_name
    client = TelegramClient(str(session_path), settings.tg_api_id, settings.tg_api_hash)
    await client.start(phone=settings.tg_phone)
    me = await client.get_me()
    print(f"Telegram session saved for: {getattr(me, 'username', None) or me.id}")
    await client.disconnect()


if __name__ == "__main__":
    asyncio.run(main())
