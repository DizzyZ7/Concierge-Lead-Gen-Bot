from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import channel_actions
from db import queries

router = Router(name=__name__)


async def send_channels(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        channels = await queries.list_channels(session)
    if not channels:
        await message.answer("No channels yet. Use /add_channel @username thailand relocation")
        return
    for channel in channels:
        text = (
            f"Channel #{channel.id}\n"
            f"Username: {escape(channel.channel_username)}\n"
            f"Geo: {escape(channel.geo)}\n"
            f"Category: {escape(channel.category or '-') }\n"
            f"Active: {channel.is_active}\n"
            f"Daily draft limit: {channel.daily_draft_limit}"
        )
        await message.answer(text, reply_markup=channel_actions(channel.id))


@router.message(Command("channels"))
async def channels_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_channels(message, session_factory)


@router.callback_query(F.data == "nav:channels")
async def channels_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_channels(callback.message, session_factory)


@router.message(Command("add_channel"))
async def add_channel_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Usage: /add_channel @username geo category")
        return
    username = parts[1]
    geo = parts[2]
    category = parts[3] if len(parts) > 3 else None
    async with session_factory() as session:
        try:
            channel = await queries.add_channel(session, username, geo, category)
        except IntegrityError:
            await session.rollback()
            await message.answer("Channel already exists.")
            return
    await message.answer(f"Added channel #{channel.id}.")


@router.message(Command("set_channel_limit"))
async def set_channel_limit_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("Usage: /set_channel_limit <channel_id> <limit>")
        return
    async with session_factory() as session:
        channel = await queries.set_channel_limit(session, int(parts[1]), int(parts[2]))
    await message.answer("Updated." if channel else "Channel not found.")


@router.callback_query(F.data.startswith("channel:toggle:"))
async def toggle_channel_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        channel = await queries.toggle_channel(session, channel_id)
    await callback.answer("Updated" if channel else "Not found")
