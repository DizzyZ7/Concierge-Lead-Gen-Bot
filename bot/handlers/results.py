from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import saved_actions
from bot.presentation import intent_label
from bot.ui import callback_message_or_alert
from core.logger import get_logger
from db import queries
from services.lead_conversion import mark_post_as_lead
from services.post_audit import actor_from_user, record_post_action
from services.post_state import apply_result_once

router = Router(name=__name__)
log = get_logger(__name__)

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


async def audit_outcome(
    session: AsyncSession,
    *,
    post_id: int,
    result: str,
    previous_status: str | None,
    actor: CallbackQuery,
    lead_id: int | None = None,
) -> None:
    try:
        details = f"lead_id={lead_id}" if lead_id is not None else None
        await record_post_action(
            session,
            post_id=post_id,
            action=f"result:{result}",
            previous_status=previous_status,
            new_status=RESULT_STATUS_MAP[result],
            actor=actor_from_user(actor.from_user),
            details=details,
        )
    except Exception as error:
        log.warning("post_action_audit_failed", post_id=post_id, action=result, error=str(error))


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
        post = await queries.get_post_with_details(session, post_id)
        previous_status = post.status if post else None
        if result == "lead":
            state, lead_id = await mark_post_as_lead(session, post_id)
            if state == "updated":
                await audit_outcome(
                    session,
                    post_id=post_id,
                    result=result,
                    previous_status=previous_status,
                    actor=callback,
                    lead_id=lead_id,
                )
                label = f"Создан лид #{lead_id}"
            elif state == "already":
                label = f"Лид #{lead_id} уже существует"
            else:
                label = state_feedback(state, RESULT_LABELS[result])
        else:
            state = await apply_result_once(session, post_id, RESULT_STATUS_MAP[result])
            if state == "updated":
                await audit_outcome(
                    session,
                    post_id=post_id,
                    result=result,
                    previous_status=previous_status,
                    actor=callback,
                )
            label = state_feedback(state, RESULT_LABELS[result])
    await callback.answer(label, show_alert=state in {"blocked", "missing"})


@router.message(Command("content_ideas"))
async def content_ideas_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_content_ideas(message, session_factory)


@router.callback_query(F.data == "nav:content_ideas")
async def content_ideas_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    message = await callback_message_or_alert(callback)
    if not message:
        return
    await callback.answer()
    await send_content_ideas(message, session_factory)
