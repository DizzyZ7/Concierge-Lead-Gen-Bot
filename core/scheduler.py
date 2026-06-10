from __future__ import annotations

from collections.abc import Awaitable, Callable
from zoneinfo import ZoneInfo

from aiogram import Bot
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.logger import get_logger
from db import queries

log = get_logger(__name__)


def create_scheduler(settings: Settings) -> AsyncIOScheduler:
    """Create AsyncIO scheduler in configured timezone."""
    return AsyncIOScheduler(timezone=ZoneInfo(settings.timezone))


def register_jobs(
    scheduler: AsyncIOScheduler,
    *,
    parser_job: Callable[[], Awaitable[None]],
    commenter_job: Callable[[], Awaitable[None]],
    alert_job: Callable[[], Awaitable[None]],
) -> None:
    """Register recurring service jobs."""
    scheduler.add_job(parser_job, "interval", minutes=10, jitter=1200, id="parser", max_instances=1, coalesce=True)
    scheduler.add_job(commenter_job, "interval", minutes=5, jitter=60, id="commenter", max_instances=1, coalesce=True)
    scheduler.add_job(alert_job, "interval", minutes=15, id="ai_alerts", max_instances=1, coalesce=True)


class AlertService:
    """Owner alerts for operational anomalies."""

    def __init__(self, *, bot: Bot, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.settings = settings

    async def check_ai_failures(self) -> None:
        """Notify owners once per day when AI failures exceed threshold."""
        async with self.session_factory() as session:
            stats = await queries.get_today_stats(session)
            if stats.ai_failures <= 10:
                return
            key = f"ai_alert_sent_{stats.date.isoformat()}"
            already_sent = await queries.get_setting(session, key, "false")
            if already_sent == "true":
                return
            text = "Claude API unstable today. Fallback templates are active."
            for admin_id in self.settings.admin_ids:
                try:
                    await self.bot.send_message(admin_id, text)
                except Exception as error:
                    log.warning("owner_alert_failed", admin_id=admin_id, error=str(error))
            await queries.set_setting(session, key, "true")
