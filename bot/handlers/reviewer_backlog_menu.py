from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.review_extras import DEFAULT_REVIEWER_BACKLOG_HOURS, send_reviewer_backlog
from bot.ui import callback_message_or_alert

router = Router(name=__name__)


@router.callback_query(F.data == "nav:reviewer_backlog")
async def reviewer_backlog_callback(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    message = await callback_message_or_alert(callback)
    if not message:
        return
    await callback.answer()
    await send_reviewer_backlog(message, session_factory, DEFAULT_REVIEWER_BACKLOG_HOURS)
