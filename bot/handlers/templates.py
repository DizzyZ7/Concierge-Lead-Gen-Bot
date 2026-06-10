from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import queries

router = Router(name=__name__)


async def send_templates(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        templates = await queries.list_templates(session)
    if not templates:
        await message.answer("No templates yet.")
        return
    for item in templates:
        text = (
            f"Template #{item.id}\n"
            f"Geo: {escape(item.geo or '-')}\n"
            f"Category: {escape(item.category or '-')}\n"
            f"Active: {item.is_active}\n\n"
            f"{escape(item.template_text)}"
        )
        await message.answer(text)


@router.message(Command("templates"))
async def templates_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_templates(message, session_factory)


@router.callback_query(F.data == "nav:templates")
async def templates_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_templates(callback.message, session_factory)


@router.message(Command("add_template"))
async def add_template_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) != 4:
        await message.answer("Usage: /add_template <geo> <category> <text>")
        return
    async with session_factory() as session:
        item = await queries.add_template(session, parts[1], parts[2], parts[3])
    await message.answer(f"Added template #{item.id}.")


@router.message(Command("disable_template"))
async def disable_template_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /disable_template <template_id>")
        return
    async with session_factory() as session:
        ok = await queries.disable_template(session, int(parts[1]))
    await message.answer("Disabled." if ok else "Not found.")
