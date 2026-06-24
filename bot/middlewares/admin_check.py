from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from core.config import Settings
from core.reviewer_access import allowed_operator_ids


class AdminCheckMiddleware(BaseMiddleware):
    """Allow only configured owners and authorized reviewer users to use the bot."""

    def __init__(self, settings: Settings) -> None:
        self.allowed_ids = allowed_operator_ids(settings)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        user_id: int | None = None
        if isinstance(event, Message) and event.from_user:
            user_id = event.from_user.id
        if isinstance(event, CallbackQuery) and event.from_user:
            user_id = event.from_user.id
        if user_id not in self.allowed_ids:
            if isinstance(event, Message):
                await event.answer("Access denied.")
            if isinstance(event, CallbackQuery):
                await event.answer("Access denied.", show_alert=True)
            return None
        return await handler(event, data)
