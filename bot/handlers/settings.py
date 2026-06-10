from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import queries

router = Router(name=__name__)


async def send_settings(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        paused = await queries.get_setting(session, "paused", "false")
        auto = await queries.get_setting(session, "auto_approve", "false")
    await message.answer(f"Settings\npaused={paused}\nauto_approve={auto}\nreviewer_first=true")


@router.message(Command("settings"))
async def settings_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_settings(message, session_factory)


@router.callback_query(F.data == "nav:settings")
async def settings_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_settings(callback.message, session_factory)


@router.message(Command("pause"))
async def pause_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await queries.set_setting(session, "paused", "true")
    await message.answer("Paused.")


@router.message(Command("resume"))
async def resume_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await queries.set_setting(session, "paused", "false")
    await message.answer("Resumed.")


@router.message(Command("autoapprove"))
async def autoapprove_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or parts[1] not in {"on", "off"}:
        await message.answer("Usage: /autoapprove on|off")
        return
    async with session_factory() as session:
        await queries.set_setting(session, "auto_approve", "true" if parts[1] == "on" else "false")
    await message.answer("Updated.")
