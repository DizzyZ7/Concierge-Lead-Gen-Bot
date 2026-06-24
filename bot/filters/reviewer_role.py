from __future__ import annotations

from aiogram.filters import Filter
from aiogram.types import CallbackQuery, Message

from core.config import Settings


class NotAdmin(Filter):
    """Match a known operator who is not configured as an owner/admin."""

    async def __call__(self, event: Message | CallbackQuery, settings: Settings) -> bool:
        return bool(event.from_user and event.from_user.id not in settings.admin_ids)
