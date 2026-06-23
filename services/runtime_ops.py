from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
from typing import Final

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.logger import get_logger
from db import queries

log = get_logger(__name__)

ALERT_COOLDOWN: Final[timedelta] = timedelta(minutes=15)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def runtime_key(component: str, field: str) -> str:
    return f"runtime.{component}.{field}"


class RuntimeOps:
    """Persists service health signals and sends rate-limited operator alerts."""

    def __init__(
        self,
        *,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
    ) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.settings = settings

    async def heartbeat(self, component: str, details: str = "") -> None:
        async with self.session_factory() as session:
            await queries.set_setting(session, runtime_key(component, "last_success_at"), now_iso())
            if details:
                await queries.set_setting(session, runtime_key(component, "last_details"), details[:500])

    async def failure(self, component: str, error: Exception, context: str = "") -> None:
        timestamp = now_iso()
        error_text = f"{error.__class__.__name__}: {str(error) or 'без текста'}"[:900]
        should_alert = False
        async with self.session_factory() as session:
            await queries.set_setting(session, runtime_key(component, "last_error_at"), timestamp)
            await queries.set_setting(session, runtime_key(component, "last_error"), error_text)
            last_alert = parse_iso(await queries.get_setting(session, runtime_key(component, "last_alert_at")))
            if last_alert is None or datetime.now(timezone.utc) - last_alert >= ALERT_COOLDOWN:
                await queries.set_setting(session, runtime_key(component, "last_alert_at"), timestamp)
                should_alert = True

        log.warning("runtime_component_failed", component=component, error=error_text, context=context)
        if should_alert:
            await self._send_alert(component, error_text, context)

    async def _send_alert(self, component: str, error_text: str, context: str) -> None:
        message = (
            "<b>⚠️ Thailand Lead Radar: ошибка сервиса</b>\n\n"
            f"<b>Компонент:</b> {escape(component)}\n"
            f"<b>Ошибка:</b> <code>{escape(error_text)}</code>"
        )
        if context:
            message += f"\n<b>Контекст:</b> {escape(context[:500])}"
        for admin_id in self.settings.admin_ids:
            try:
                await self.bot.send_message(admin_id, message, disable_web_page_preview=True)
            except Exception as alert_error:
                log.warning("runtime_alert_send_failed", admin_id=admin_id, error=str(alert_error))


async def get_component_runtime_state(session: AsyncSession, component: str) -> dict[str, str | None]:
    return {
        "last_success_at": await queries.get_setting(session, runtime_key(component, "last_success_at")),
        "last_details": await queries.get_setting(session, runtime_key(component, "last_details")),
        "last_error_at": await queries.get_setting(session, runtime_key(component, "last_error_at")),
        "last_error": await queries.get_setting(session, runtime_key(component, "last_error")),
    }
