from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import saved_actions
from bot.presentation import intent_label
from core.logger import get_logger
from db import queries
from services.post_audit import actor_from_user, record_post_action
from services.post_state import save_post_once

router = Router(name=__name__)
log = get_logger(__name__)


def cut(text: str | None, limit: int = 700) -> str:
    value = text or ""
    return value if len(value) <= limit else value[: limit - 1] + "..."


def save_feedback(result: str) -> str:
    if result == "updated":
        return "Сохранено"
    if result == "already":
        return "Этот пост уже сохранен"
    if result == "blocked":
        return "Пост уже закрыт другим результатом"
    return "Пост не найден"


async def send_saved_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_saved_posts(session, 20)
    if not posts:
        await message.answer("Сохраненных постов пока нет.")
        return
    for post in posts:
        channel = post.channel.channel_username if post.channel else "неизвестно"
        score = f"{post.relevance_score:.2f}" if post.relevance_score is not None else "-"
        text = (
            f"Сохранено #{post.id}\n"
            f"Канал: {escape(channel)}\n"
            f"Категория: {escape(intent_label(post.intent))}\n"
            f"Оценка: {escape(score)}\n"
            f"Почему релевантно: {escape(post.relevance_reason or '-')}\n"
            f"Кратко: {escape(post.content_summary or '-')}\n"
            f"Как зайти в диалог: {escape(post.suggested_angle or '-')}\n"
            f"Ссылка: {escape(post.post_url or '-')}\n\n"
            f"Текст:\n{escape(cut(post.post_text))}"
        )
        await message.answer(text, reply_markup=saved_actions(post.id, post.post_url), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("post:save:"))
async def save_post_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        previous_status = post.status if post else None
        result = await save_post_once(session, post_id)
        if result == "updated":
            try:
                await record_post_action(
                    session,
                    post_id=post_id,
                    action="saved",
                    previous_status=previous_status,
                    new_status="saved",
                    actor=actor_from_user(callback.from_user),
                )
            except Exception as error:
                log.warning("post_action_audit_failed", post_id=post_id, action="saved", error=str(error))
    await callback.answer(save_feedback(result), show_alert=result in {"blocked", "missing"})


@router.message(Command("saved_queue"))
async def saved_queue_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_saved_queue(message, session_factory)


@router.callback_query(F.data == "nav:saved_queue")
async def saved_queue_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_saved_queue(callback.message, session_factory)
