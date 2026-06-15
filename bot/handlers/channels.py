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


def clean_csv(value: str | None) -> str | None:
    if not value or value.strip() in {"-", "none", "None", "null"}:
        return None
    parts = [part.strip().lower() for part in value.split(",") if part.strip()]
    return ",".join(dict.fromkeys(parts)) or None


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
            f"Category: {escape(channel.category or '-')}\n"
            f"Active: {channel.is_active}\n"
            f"Daily draft limit: {channel.daily_draft_limit}\n"
            f"Reviewer delay: {channel.review_delay_min}-{channel.review_delay_max} min\n"
            f"Min score: {channel.min_score if channel.min_score is not None else '-'}\n"
            f"Allowed intents: {escape(channel.allowed_intents or '-')}\n"
            f"Blocked keywords: {escape(channel.blocked_keywords or '-')}"
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


@router.message(Command("set_channel_delay"))
async def set_channel_delay_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) != 4 or not all(part.isdigit() for part in parts[1:]):
        await message.answer("Usage: /set_channel_delay <channel_id> <min> <max>")
        return
    channel_id = int(parts[1])
    delay_min = int(parts[2])
    delay_max = int(parts[3])
    if delay_min > delay_max:
        await message.answer("Min delay must be less than or equal to max delay.")
        return
    async with session_factory() as session:
        channel = await queries.set_channel_delay(session, channel_id, delay_min, delay_max)
    await message.answer("Updated." if channel else "Channel not found.")


@router.message(Command("set_channel_min_score"))
async def set_channel_min_score_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Usage: /set_channel_min_score <channel_id> <0.00-1.00|->")
        return
    value = None
    if parts[2] != "-":
        try:
            value = float(parts[2].replace(",", "."))
        except ValueError:
            await message.answer("Min score must be a number from 0.00 to 1.00, or - to reset.")
            return
        if value < 0 or value > 1:
            await message.answer("Min score must be from 0.00 to 1.00.")
            return
    async with session_factory() as session:
        channel = await queries.set_channel_min_score(session, int(parts[1]), value)
    await message.answer("Updated." if channel else "Channel not found.")


@router.message(Command("set_channel_intents"))
async def set_channel_intents_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Usage: /set_channel_intents <channel_id> <intent1,intent2|->")
        return
    intents = clean_csv(parts[2])
    async with session_factory() as session:
        channel = await queries.set_channel_allowed_intents(session, int(parts[1]), intents)
    await message.answer("Updated." if channel else "Channel not found.")


@router.message(Command("set_channel_blocklist"))
async def set_channel_blocklist_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Usage: /set_channel_blocklist <channel_id> <word1,word2|->")
        return
    blocked = clean_csv(parts[2])
    async with session_factory() as session:
        channel = await queries.set_channel_blocked_keywords(session, int(parts[1]), blocked)
    await message.answer("Updated." if channel else "Channel not found.")


@router.callback_query(F.data.startswith("channel:toggle:"))
async def toggle_channel_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        channel = await queries.toggle_channel(session, channel_id)
    await callback.answer("Updated" if channel else "Not found")
