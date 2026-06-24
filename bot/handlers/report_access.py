from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message

from bot.filters.reviewer_role import NotAdmin

router = Router(name=__name__)

ADMIN_REPORTS_MESSAGE = "Аналитика каналов и качество источников доступны только администратору."


@router.message(Command("channel_stats"), NotAdmin())
async def deny_channel_stats(message: Message) -> None:
    await message.answer(ADMIN_REPORTS_MESSAGE)


@router.message(Command("source_quality"), NotAdmin())
async def deny_source_quality(message: Message) -> None:
    await message.answer(ADMIN_REPORTS_MESSAGE)


@router.callback_query(F.data == "nav:channel_stats", NotAdmin())
async def deny_channel_stats_callback(callback: CallbackQuery) -> None:
    await callback.answer(ADMIN_REPORTS_MESSAGE, show_alert=True)
