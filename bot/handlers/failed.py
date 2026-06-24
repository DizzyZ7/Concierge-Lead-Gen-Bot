from __future__ import annotations

from decimal import Decimal

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import failed_actions
from bot.presentation import intent_label
from core.config import Settings
from db import queries
from services.ai import AIService
from services.reviewer_cards import escape_and_trim

router = Router(name=__name__)


def channel_min_score(value: Decimal | float | int | None, default: float) -> float:
    return float(value) if value is not None else default


async def send_failed_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_posts_by_status(session, "processing_failed", 20)
    if not posts:
        await message.answer("Ошибок обработки нет.")
        return
    for post in posts:
        channel = post.channel.channel_username if post.channel else "неизвестно"
        text = (
            f"Ошибка обработки: пост #{post.id}\n"
            f"Канал: {escape_and_trim(channel, 200)}\n"
            f"Причина: {escape_and_trim(post.relevance_reason or '-', 500)}\n"
            f"Ссылка: {escape_and_trim(post.post_url or '-', 500)}\n\n"
            f"Текст:\n{escape_and_trim(post.post_text, 700)}"
        )
        await message.answer(text, reply_markup=failed_actions(post.id, post.post_url), disable_web_page_preview=True)


@router.message(Command("failed_queue"))
async def failed_queue_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_failed_queue(message, session_factory)


@router.callback_query(F.data == "nav:failed_queue")
async def failed_queue_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_failed_queue(callback.message, session_factory)


@router.callback_query(F.data.startswith("failed:retry:"))
async def retry_failed_callback(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    ai_service: AIService,
    settings: Settings,
) -> None:
    post_id = int(callback.data.split(":")[-1])
    try:
        async with session_factory() as session:
            post = await queries.get_post_with_details(session, post_id)
            if not post or not post.channel:
                await callback.answer("Пост не найден", show_alert=True)
                return
            score = await ai_service.score_post(post.post_text or "", post.channel.geo, session)
            value = float(score.get("score", 0.5))
            intent = str(score.get("intent", "unknown")).lower()
            post.relevance_score = value
            post.intent = intent
            post.relevance_reason = str(score.get("reason", "Пост требует ручной проверки."))
            post.content_summary = str(score.get("summary", "Краткое резюме не сформировано."))
            post.suggested_angle = str(score.get("angle", "Можно аккуратно зайти с полезным уточнением или советом."))
            min_score = channel_min_score(post.channel.min_score, settings.relevance_threshold)
            if value < min_score:
                post.status = "pending"
                await session.commit()
                await callback.message.edit_text(
                    f"Пост #{post.id} повторно обработан и возвращен на ручную проверку.\n"
                    f"Категория: {escape_and_trim(intent_label(intent), 100)}\n"
                    f"Оценка: {value:.2f}"
                )
                await callback.answer("Повторная обработка выполнена")
                return

            draft_text, source = await ai_service.generate_draft(post.post_text or "", post.channel.geo, intent, session)
            await queries.approve_post(
                session,
                post_id=post.id,
                draft_text=draft_text,
                source=source,
                delay_min=post.channel.review_delay_min,
                delay_max=post.channel.review_delay_max,
            )
            if source == "ai":
                await queries.increment_stat(session, "ai_drafts", 1)
            else:
                await queries.increment_stat(session, "template_drafts", 1)
        await callback.message.edit_text(f"Пост #{post_id} повторно обработан и отправлен в reviewer pipeline.")
        await callback.answer("Повторная обработка выполнена")
    except Exception as error:
        await callback.answer("Повторная обработка не удалась", show_alert=True)
        await callback.message.answer(f"Ошибка повторной обработки: {escape_and_trim(error.__class__.__name__, 120)}")
