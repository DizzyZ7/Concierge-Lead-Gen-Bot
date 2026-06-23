from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import saved_actions
from bot.presentation import intent_label
from db import queries
from db.models import Lead
from services.post_state import FINAL_OUTCOME_STATUSES, apply_result_once

router = Router(name=__name__)

RESULT_STATUS_MAP = {
    "commented": "commented",
    "lead": "lead",
    "content_idea": "content_idea",
    "not_relevant": "not_relevant",
}

RESULT_LABELS = {
    "commented": "Отмечено: комментарий написан",
    "lead": "Отмечено: стал лидом",
    "content_idea": "Сохранено как идея",
    "not_relevant": "Отмечено как нерелевантное",
}


def cut(text: str | None, limit: int = 700) -> str:
    value = text or ""
    return value if len(value) <= limit else value[: limit - 1] + "..."


def state_feedback(result: str, success: str) -> str:
    if result == "updated":
        return success
    if result == "already":
        return "Этот результат уже зафиксирован."
    if result == "blocked":
        return "Пост уже закрыт другим результатом."
    return "Пост не найден."


async def mark_as_lead(session: AsyncSession, post_id: int) -> tuple[str, int | None]:
    post = await queries.get_post_with_details(session, post_id)
    if not post:
        return "missing", None

    existing = await session.scalar(select(Lead).where(Lead.source_post_id == post_id).limit(1))
    if existing:
        if post.status != "lead":
            post.status = "lead"
            await session.commit()
        return "already", existing.id

    if post.status in FINAL_OUTCOME_STATUSES:
        return "blocked", None

    lead = Lead(
        source_post_id=post.id,
        geo=post.channel.geo if post.channel else None,
        intent=post.intent,
        notes=f"Лид из Lead Radar, источник #{post.id}. Контактные данные нужно заполнить после прямого ответа.",
    )
    session.add(lead)
    post.status = "lead"
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(select(Lead).where(Lead.source_post_id == post_id).limit(1))
        return ("already", existing.id) if existing else ("missing", None)

    await queries.increment_stat(session, "leads_received", 1)
    await session.refresh(lead)
    return "updated", lead.id


async def send_content_ideas(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_content_ideas(session, 20)
    if not posts:
        await message.answer("Идей пока нет.")
        return
    for post in posts:
        channel = post.channel.channel_username if post.channel else "неизвестно"
        score = f"{post.relevance_score:.2f}" if post.relevance_score is not None else "-"
        text = (
            f"Идея #{post.id}\n"
            f"Канал: {escape(channel)}\n"
            f"Категория: {escape(intent_label(post.intent))}\n"
            f"Оценка: {escape(score)}\n"
            f"Кратко: {escape(post.content_summary or '-')}\n"
            f"Как раскрыть: {escape(post.suggested_angle or '-')}\n"
            f"Ссылка: {escape(post.post_url or '-')}\n\n"
            f"Текст:\n{escape(cut(post.post_text))}"
        )
        await message.answer(text, reply_markup=saved_actions(post.id, post.post_url), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("result:"))
async def result_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = callback.data.split(":")
    if len(parts) != 3 or parts[1] not in RESULT_STATUS_MAP or not parts[2].isdigit():
        await callback.answer("Неизвестное действие", show_alert=True)
        return
    result = parts[1]
    post_id = int(parts[2])
    async with session_factory() as session:
        if result == "lead":
            state, lead_id = await mark_as_lead(session, post_id)
            if state == "updated":
                label = f"Создан лид #{lead_id}"
            elif state == "already":
                label = f"Лид #{lead_id} уже существует"
            else:
                label = state_feedback(state, RESULT_LABELS[result])
        else:
            state = await apply_result_once(session, post_id, RESULT_STATUS_MAP[result])
            label = state_feedback(state, RESULT_LABELS[result])
    await callback.answer(label, show_alert=state in {"blocked", "missing"})


@router.message(Command("content_ideas"))
async def content_ideas_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_content_ideas(message, session_factory)


@router.callback_query(F.data == "nav:content_ideas")
async def content_ideas_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_content_ideas(callback.message, session_factory)
