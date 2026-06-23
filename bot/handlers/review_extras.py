from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.keyboards.inline import approved_actions, reviewer_actions
from bot.presentation import intent_label, status_label
from db import queries
from db.models import ParsedPost, ReviewDraft
from services.ai import AIService
from services.post_state import can_approve

router = Router(name=__name__)

DEFAULT_REVIEWER_BACKLOG_HOURS = 24
MAX_REVIEWER_BACKLOG_HOURS = 24 * 30


def cut(text: str | None, limit: int = 1000) -> str:
    value = text or ""
    return escape(value if len(value) <= limit else value[: limit - 1] + "...")


def clamp_backlog_hours(value: str | None) -> int | None:
    if value is None:
        return DEFAULT_REVIEWER_BACKLOG_HOURS
    if not value.isdigit():
        return None
    hours = int(value)
    if hours < 1 or hours > MAX_REVIEWER_BACKLOG_HOURS:
        return None
    return hours


def wait_hours(sent_at: datetime | None) -> int:
    if sent_at is None:
        return 0
    normalized = sent_at if sent_at.tzinfo else sent_at.replace(tzinfo=timezone.utc)
    return max(0, int((datetime.now(timezone.utc) - normalized).total_seconds() // 3600))


def render_draft_card(post: ParsedPost) -> str:
    channel = post.channel.channel_username if post.channel else "неизвестно"
    draft = post.draft.draft_text if post.draft else "Черновик еще не создан. Сначала одобри пост."
    source = post.draft.draft_source if post.draft else "-"
    return (
        f"Черновик для поста #{post.id}\n"
        f"Статус: {escape(status_label(post.status))}\n"
        f"Канал: {escape(channel)}\n"
        f"Источник текста: {escape(source)}\n"
        f"Ссылка: {escape(post.post_url or '-')}\n\n"
        f"<code>{cut(draft, 1800)}</code>"
    )


def render_backlog_card(post: ParsedPost) -> str:
    channel = post.channel.channel_username if post.channel else "неизвестно"
    draft = post.draft
    sent_at = draft.sent_to_reviewer_at if draft else None
    sent_text = "-"
    if sent_at is not None:
        normalized = sent_at if sent_at.tzinfo else sent_at.replace(tzinfo=timezone.utc)
        sent_text = normalized.strftime("%d.%m %H:%M UTC")
    score_text = f"{post.relevance_score:.2f}" if post.relevance_score is not None else "-"
    return (
        f"Просроченная reviewer-карточка #{post.id}\n"
        f"Ждет решения: {wait_hours(sent_at)} ч.\n"
        f"Отправлена: {escape(sent_text)}\n"
        f"Канал: {escape(channel)}\n"
        f"Категория: {escape(intent_label(post.intent))}\n"
        f"Оценка: {escape(score_text)}\n"
        f"Ссылка: {escape(post.post_url or '-')}\n\n"
        f"Кратко: {cut(post.content_summary, 400)}\n\n"
        f"Черновик:\n<code>{cut(draft.draft_text if draft else '', 900)}</code>"
    )


async def approve_now_flow(
    post_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    ai_service: AIService,
) -> str:
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        if not post or not post.channel:
            return "missing"
        if not can_approve(post.status, post.draft is not None):
            return "blocked"
        text, source = await ai_service.generate_draft(post.post_text or "", post.channel.geo, post.intent, session)
        approved = await queries.approve_post(
            session,
            post_id=post.id,
            draft_text=text,
            source=source,
            delay_min=0,
            delay_max=0,
        )
        if not approved:
            return "missing"
        if source == "ai":
            await queries.increment_stat(session, "ai_drafts", 1)
        else:
            await queries.increment_stat(session, "template_drafts", 1)
        return "updated"


async def send_approved_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_posts_by_status(session, "approved", 20)
    if not posts:
        await message.answer("Одобренная очередь пуста.")
        return
    for post in posts:
        draft = post.draft
        due = draft.due_at.isoformat() if draft and draft.due_at else "-"
        text = (
            f"Одобрено #{post.id}\n"
            f"Время отправки: {escape(due)}\n"
            f"Ссылка: {escape(post.post_url or '-')}\n\n"
            f"Черновик:\n<code>{cut(draft.draft_text if draft else '', 900)}</code>"
        )
        await message.answer(text, reply_markup=approved_actions(post.id, post.post_url), disable_web_page_preview=True)


async def send_reviewer_backlog(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    older_than_hours: int,
) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
    async with session_factory() as session:
        result = await session.scalars(
            select(ParsedPost)
            .options(selectinload(ParsedPost.channel), selectinload(ParsedPost.draft))
            .join(ParsedPost.draft)
            .where(
                ParsedPost.status == "sent_to_reviewer",
                ReviewDraft.sent_to_reviewer_at.is_not(None),
                ReviewDraft.sent_to_reviewer_at <= cutoff,
                ReviewDraft.marked_done_at.is_(None),
            )
            .order_by(ReviewDraft.sent_to_reviewer_at.asc())
            .limit(20)
        )
        posts = result.all()
    if not posts:
        await message.answer(f"Reviewer-карточек без решения более {older_than_hours} ч. нет.")
        return
    await message.answer(f"Просроченные reviewer-карточки: {len(posts)}. Порог: {older_than_hours} ч.")
    for post in posts:
        await message.answer(
            render_backlog_card(post),
            reply_markup=reviewer_actions(post.id, post.post_url),
            disable_web_page_preview=True,
        )


@router.callback_query(F.data.startswith("post:approve_now:"))
async def approve_now_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession], ai_service: AIService) -> None:
    post_id = int(callback.data.split(":")[-1])
    result = await approve_now_flow(post_id, session_factory=session_factory, ai_service=ai_service)
    if result == "updated":
        await callback.message.edit_text(f"Пост #{post_id} одобрен и будет отправлен reviewer-у в ближайший scheduler tick.")
        await callback.answer()
        return
    if result == "blocked":
        await callback.answer("Этот пост уже был одобрен или закрыт", show_alert=True)
        return
    await callback.answer("Пост не найден", show_alert=True)


@router.callback_query(F.data.startswith("post:dispatch:"))
async def dispatch_now_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        ok = await queries.dispatch_now(session, post_id)
    await callback.answer("Поставлено на немедленную отправку" if ok else "Одобренный черновик не найден", show_alert=not ok)


@router.callback_query(F.data.startswith("post:draft:"))
async def show_draft_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
    if not post:
        await callback.answer("Пост не найден", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(render_draft_card(post))


@router.message(Command("draft"))
async def draft_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /draft <post_id>")
        return
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, int(parts[1]))
    await message.answer(render_draft_card(post) if post else "Пост не найден.")


@router.message(Command("approved_queue"))
async def approved_queue_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_approved_queue(message, session_factory)


@router.message(Command("reviewer_backlog"))
async def reviewer_backlog_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=1)
    hours = clamp_backlog_hours(parts[1] if len(parts) == 2 else None)
    if hours is None:
        await message.answer(f"Формат: /reviewer_backlog [hours], где hours от 1 до {MAX_REVIEWER_BACKLOG_HOURS}.")
        return
    await send_reviewer_backlog(message, session_factory, hours)


@router.callback_query(F.data == "nav:approved_queue")
async def approved_queue_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_approved_queue(callback.message, session_factory)
