from __future__ import annotations

from datetime import timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import channel_actions, channels_menu
from bot.ui import edit_callback_message
from db import queries
from db.models import TargetChannel
from services.ai import VALID_INTENTS
from services.channel_cursor import reset_channel_cursor
from services.channel_validation import is_channel_validation_fresh

router = Router(name=__name__)


def clean_csv(value: str | None) -> str | None:
    if not value or value.strip() in {"-", "none", "None", "null"}:
        return None
    parts = [part.strip().lower() for part in value.split(",") if part.strip()]
    return ",".join(dict.fromkeys(parts)) or None


def format_channel_validation(channel) -> str:
    checked_at = channel.last_validation_at
    if checked_at is None:
        return "не проверялся"
    checked = checked_at if checked_at.tzinfo else checked_at.replace(tzinfo=timezone.utc)
    checked_text = checked.astimezone(timezone.utc).strftime("%d.%m %H:%M UTC")
    if channel.last_validation_error:
        return f"ошибка {checked_text}: {channel.last_validation_error}"
    if is_channel_validation_fresh(checked_at, channel.last_validation_error):
        return f"подтвержден {checked_text}"
    return f"устарело {checked_text}: запусти /validate_channels"


def format_channel_detail(channel: TargetChannel) -> str:
    return (
        f"Канал #{channel.id}\n"
        f"Username: {escape(channel.channel_username)}\n"
        f"Название: {escape(channel.channel_title or '-')}\n"
        f"Валидация: {escape(format_channel_validation(channel))}\n"
        f"Гео: {escape(channel.geo)}\n"
        f"Категория: {escape(channel.category or '-')}\n"
        f"Мониторинг: {'включен' if channel.is_active else 'выключен'}\n"
        f"Лимит черновиков в день: {channel.daily_draft_limit}\n"
        f"Задержка для reviewer-а: {channel.review_delay_min}-{channel.review_delay_max} мин.\n"
        f"Минимальная оценка: {channel.min_score if channel.min_score is not None else '-'}\n"
        f"Разрешенные intent: {escape(channel.allowed_intents or '-')}\n"
        f"Стоп-слова: {escape(channel.blocked_keywords or '-')}\n"
        f"Последнее сообщение cursor: {channel.last_seen_message_id or '-'}"
    )


def format_channels_overview(channels) -> str:
    if not channels:
        return "Каналов пока нет. Используй: /add_channel @username thailand relocation"
    active_count = sum(1 for channel in channels if channel.is_active)
    unchecked_count = sum(1 for channel in channels if not is_channel_validation_fresh(channel.last_validation_at, channel.last_validation_error))
    lines = [
        "Каналы",
        "",
        f"Всего: {len(channels)}",
        f"Мониторинг включен: {active_count}",
        f"Требуют проверки: {unchecked_count}",
        "",
        "Выбери канал для деталей:",
    ]
    for channel in channels:
        state = "вкл" if channel.is_active else "выкл"
        validation = "ok" if is_channel_validation_fresh(channel.last_validation_at, channel.last_validation_error) else "проверить"
        lines.append(f"#{channel.id} {escape(channel.channel_username)} — {state}, {validation}")
    return "\n".join(lines)


async def send_channels(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        channels = await queries.list_channels(session)
    if not channels:
        await message.answer("Каналов пока нет. Используй: /add_channel @username thailand relocation")
        return
    await message.answer(format_channels_overview(channels), reply_markup=channels_menu([channel.id for channel in channels]))


@router.message(Command("channels"))
async def channels_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_channels(message, session_factory)


@router.callback_query(F.data == "nav:channels")
async def channels_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    async with session_factory() as session:
        channels = await queries.list_channels(session)
    await edit_callback_message(
        callback,
        format_channels_overview(channels),
        reply_markup=channels_menu([channel.id for channel in channels]) if channels else None,
    )


@router.callback_query(F.data.startswith("channel:view:"))
async def channel_detail_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    channel_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        channel = await session.get(TargetChannel, channel_id)
    if not channel:
        await edit_callback_message(callback, "Канал не найден.", reply_markup=channels_menu([]))
        return
    await edit_callback_message(callback, format_channel_detail(channel), reply_markup=channel_actions(channel.id))


@router.message(Command("add_channel"))
async def add_channel_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) < 3:
        await message.answer("Формат: /add_channel @username geo category")
        return
    username = parts[1]
    geo = parts[2]
    category = parts[3] if len(parts) > 3 else None
    async with session_factory() as session:
        try:
            channel = await queries.add_channel(session, username, geo, category)
        except IntegrityError:
            await session.rollback()
            await message.answer("Такой канал уже добавлен.")
            return
    await message.answer(f"Добавлен канал #{channel.id}. Проверь доступ через /validate_channels.")


@router.message(Command("set_channel_limit"))
async def set_channel_limit_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit() or not parts[2].isdigit():
        await message.answer("Формат: /set_channel_limit <channel_id> <limit>")
        return
    async with session_factory() as session:
        channel = await queries.set_channel_limit(session, int(parts[1]), int(parts[2]))
    await message.answer("Обновлено." if channel else "Канал не найден.")


@router.message(Command("set_channel_delay"))
async def set_channel_delay_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) != 4 or not all(part.isdigit() for part in parts[1:]):
        await message.answer("Формат: /set_channel_delay <channel_id> <min> <max>")
        return
    channel_id = int(parts[1])
    delay_min = int(parts[2])
    delay_max = int(parts[3])
    if delay_min > delay_max:
        await message.answer("Минимальная задержка не может быть больше максимальной.")
        return
    async with session_factory() as session:
        channel = await queries.set_channel_delay(session, channel_id, delay_min, delay_max)
    await message.answer("Обновлено." if channel else "Канал не найден.")


@router.message(Command("set_channel_min_score"))
async def set_channel_min_score_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Формат: /set_channel_min_score <channel_id> <0.00-1.00|->")
        return
    value = None
    if parts[2] != "-":
        try:
            value = float(parts[2].replace(",", "."))
        except ValueError:
            await message.answer("Минимальная оценка должна быть числом от 0.00 до 1.00 или - для сброса.")
            return
        if value < 0 or value > 1:
            await message.answer("Минимальная оценка должна быть от 0.00 до 1.00.")
            return
    async with session_factory() as session:
        channel = await queries.set_channel_min_score(session, int(parts[1]), value)
    await message.answer("Обновлено." if channel else "Канал не найден.")


@router.message(Command("set_channel_intents"))
async def set_channel_intents_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Формат: /set_channel_intents <channel_id> <intent1,intent2|->")
        return
    intents = clean_csv(parts[2])
    if intents:
        invalid = sorted(set(intents.split(",")) - VALID_INTENTS)
        if invalid:
            available = ", ".join(sorted(VALID_INTENTS))
            await message.answer(f"Неизвестные intent: {', '.join(invalid)}\nДоступные: {available}")
            return
    async with session_factory() as session:
        channel = await queries.set_channel_allowed_intents(session, int(parts[1]), intents)
    await message.answer("Обновлено." if channel else "Канал не найден.")


@router.message(Command("set_channel_blocklist"))
async def set_channel_blocklist_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Формат: /set_channel_blocklist <channel_id> <word1,word2|->")
        return
    blocked = clean_csv(parts[2])
    async with session_factory() as session:
        channel = await queries.set_channel_blocked_keywords(session, int(parts[1]), blocked)
    await message.answer("Обновлено." if channel else "Канал не найден.")


@router.message(Command("reset_channel_cursor"))
async def reset_channel_cursor_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /reset_channel_cursor <channel_id>")
        return
    async with session_factory() as session:
        ok = await reset_channel_cursor(session, int(parts[1]))
    await message.answer(
        "Cursor сброшен. Теперь используй /scan_now, чтобы сразу взять свежий стартовый срез сообщений."
        if ok
        else "Канал не найден."
    )


@router.callback_query(F.data.startswith("channel:toggle:"))
async def toggle_channel_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    channel_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        channel = await queries.toggle_channel(session, channel_id)
    await callback.answer("Мониторинг обновлен" if channel else "Канал не найден")
    if channel:
        await edit_callback_message(callback, format_channel_detail(channel), reply_markup=channel_actions(channel.id))
