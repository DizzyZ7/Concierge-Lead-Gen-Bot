from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from core.config import Settings


class AdminOnlyMiddleware(BaseMiddleware):
    """Restrict administrative routers to configured owner accounts."""

    def __init__(self, settings: Settings) -> None:
        self.admin_ids = settings.admin_ids

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        elif isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id

        if user_id not in self.admin_ids:
            if isinstance(event, Message):
                await event.answer("Это действие доступно только администратору.")
            elif isinstance(event, CallbackQuery):
                await event.answer("Это действие доступно только администратору.", show_alert=True)
            return None
        return await handler(event, data)
