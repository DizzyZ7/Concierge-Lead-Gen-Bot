from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from telethon import TelegramClient

from core.config import get_settings
from db import queries
from db.migration_guard import ensure_schema_current
from db.session import create_engine, create_session_factory
from services.channel_validation import validate_channels
from services.channel_validation import ChannelValidationResult
from services.runtime_ops import now_iso, runtime_key


def validation_details(results: list[ChannelValidationResult]) -> str:
    failed = [item for item in results if not item.ok]
    return f"checked={len(results)} failed={len(failed)}"


def validation_exit_code(results: list[ChannelValidationResult]) -> int:
    return 1 if any(not item.ok for item in results) else 0


def render_validation_lines(results: list[ChannelValidationResult]) -> list[str]:
    lines = ["Telegram source validation", validation_details(results)]
    for item in results:
        if item.ok:
            title = f" - {item.title}" if item.title else ""
            lines.append(f"OK #{item.channel_id} {item.username}{title}")
        else:
            lines.append(f"FAIL #{item.channel_id} {item.username}: {item.error or '-'}")
    return lines


async def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    if not settings.tg_api_id or not settings.tg_api_hash:
        raise RuntimeError("TG_API_ID and TG_API_HASH are required for source validation")

    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    client = TelegramClient(str(Path("sessions") / settings.tg_session_name), settings.tg_api_id, settings.tg_api_hash)
    try:
        revision = await ensure_schema_current(session_factory)
        print(f"Schema revision: {revision}")
        await client.connect()
        if not await client.is_user_authorized():
            raise RuntimeError("Telegram user session is not authorized. Run: python -m services.session_login")

        results = await validate_channels(client, session_factory)
        failed = [item for item in results if not item.ok]
        details = validation_details(results)
        async with session_factory() as session:
            if failed:
                usernames = ", ".join(item.username for item in failed[:5])
                await queries.set_setting(session, runtime_key("source_validation", "last_error_at"), now_iso())
                await queries.set_setting(
                    session,
                    runtime_key("source_validation", "last_error"),
                    f"Недоступные источники: {usernames}"[:900],
                )
                await queries.set_setting(session, runtime_key("source_validation", "last_details"), details)
            else:
                await queries.set_setting(session, runtime_key("source_validation", "last_success_at"), now_iso())
                await queries.set_setting(session, runtime_key("source_validation", "last_details"), details)

        print("\n".join(render_validation_lines(results)))
        if validation_exit_code(results):
            raise SystemExit(1)
    finally:
        await client.disconnect()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
