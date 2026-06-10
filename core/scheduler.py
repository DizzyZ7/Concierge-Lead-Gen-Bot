from __future__ import annotations

from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from core.config import Settings


def create_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Create AsyncIO scheduler in configured timezone."""
    return AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))
