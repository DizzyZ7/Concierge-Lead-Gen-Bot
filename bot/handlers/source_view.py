from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.presentation import intent_label, status_label
from db import queries
from services.reviewer_cards import escape_and_trim

router = Router(name=__name__)


def render_source(post) -> str:
    channel = post.channel.channel_username if post.channel else "неизвестно"
    score = f"{post.relevance_score:.2f}" if post.relevance_score is not None else "-"
    return (
        f"Источник #{post.id}\n"
        f"Статус: {escape_and_trim(status_label(post.status), 100)}\n"
        f"Канал: {escape_and_trim(channel, 200)}\n"
        f"Категория: {escape_and_trim(intent_label(post.intent), 100)}\n"
        f"Оценка: {escape_and_trim(score, 32)}\n"
        f"Почему релевантно: {escape_and_trim(post.relevance_reason or '-', 300)}\n"
        f"Кратко: {escape_and_trim(post.content_summary or '-', 350)}\n"
        f"Как зайти в диалог: {escape_and_trim(post.suggested_angle or '-', 350)}\n"
        f"Ссылка: {escape_and_trim(post.post_url or '-', 500)}\n\n"
        f"Текст:\n{escape_and_trim(post.post_text, 1600)}"
    )


@router.message(Command("source"))
async def source_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /source <post_id>")
        return
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, int(parts[1]))
    await message.answer(render_source(post) if post else "Пост не найден.", disable_web_page_preview=True)


@router.callback_query(F.data.startswith("post:source:"))
async def source_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(render_source(post), disable_web_page_preview=True)
