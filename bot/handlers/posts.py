from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from aiogram import Bot, F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import pending_actions, reviewer_actions
from bot.presentation import intent_label
from core.logger import get_logger
from db import queries
from services.ai import AIService
from services.post_state import can_approve, mark_reviewer_done_once, skip_post_once
from services.reviewer_cards import render_reviewer_card

router = Router(name=__name__)
log = get_logger(__name__)

EDITABLE_DRAFT_STATUSES = {"approved", "sent_to_reviewer", "saved"}
MAX_MANUAL_DRAFT_CHARS = 1600


def cut(text: str | None, limit: int = 700) -> str:
    value = text or ""
    return escape(value if len(value) <= limit else value[: limit - 1] + "...")


def render_queue_item(item, label: str) -> str:
    channel = item.channel.channel_username if item.channel else "неизвестно"
    score = f"{item.relevance_score:.2f}" if item.relevance_score is not None else "-"
    return (
        f"{label} #{item.id}\n"
        f"Канал: {escape(channel)}\n"
        f"Оценка: {escape(score)}\n"
        f"Категория: {escape(intent_label(item.intent))}\n"
        f"Почему релевантно: {escape(item.relevance_reason or '-')}\n"
        f"Кратко: {escape(item.content_summary or '-')}\n"
        f"Ссылка: {escape(item.post_url or '-')}\n\n"
        f"Текст:\n{cut(item.post_text)}"
    )


def transition_message(result: str, success: str) -> str:
    if result == "updated":
        return success
    if result == "already":
        return "Действие уже было выполнено."
    if result == "blocked":
        return "Этот пост уже закрыт другим результатом."
    return "Пост не найден."


def reviewer_card_text(post) -> str:
    draft = post.draft
    if not draft or not post.channel:
        raise ValueError("Reviewer card requires a draft and source channel")
    return render_reviewer_card(
        draft_id=draft.id,
        post_id=post.id,
        channel=post.channel.channel_username,
        url=post.post_url,
        source_text=post.post_text,
        draft_text=draft.draft_text,
        score=post.relevance_score,
        intent=post.intent,
        reason=post.relevance_reason,
        summary=post.content_summary,
        angle=post.suggested_angle,
    )


async def sync_sent_reviewer_card(bot: Bot, post) -> bool:
    draft = post.draft
    if not draft or draft.reviewer_chat_id is None or draft.reviewer_message_id is None:
        return False
    try:
        await bot.edit_message_text(
            text=reviewer_card_text(post),
            chat_id=draft.reviewer_chat_id,
            message_id=draft.reviewer_message_id,
            reply_markup=reviewer_actions(post.id, post.post_url),
            disable_web_page_preview=True,
        )
        return True
    except Exception as error:
        log.warning(
            "reviewer_card_sync_failed",
            post_id=post.id,
            reviewer_chat_id=draft.reviewer_chat_id,
            reviewer_message_id=draft.reviewer_message_id,
            error=str(error),
        )
        return False


async def send_pending(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        items = await queries.list_pending_posts(session, 10)
    if not items:
        await message.answer("Постов на ручной проверке нет.")
        return
    for item in items:
        await message.answer(
            render_queue_item(item, "На ручной проверке"),
            reply_markup=pending_actions(item.id),
            disable_web_page_preview=True,
        )


async def send_limit_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        items = await queries.list_posts_by_status(session, "queued_by_limit", 20)
    if not items:
        await message.answer("Очередь дневного лимита пуста.")
        return
    for item in items:
        await message.answer(
            render_queue_item(item, "Отложено по дневному лимиту"),
            reply_markup=pending_actions(item.id),
            disable_web_page_preview=True,
        )


@router.message(Command("pending"))
async def pending_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_pending(message, session_factory)


@router.callback_query(F.data == "nav:pending")
async def pending_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_pending(callback.message, session_factory)


@router.message(Command("limit_queue"))
async def limit_queue_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_limit_queue(message, session_factory)


@router.callback_query(F.data == "nav:limit_queue")
async def limit_queue_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_limit_queue(callback.message, session_factory)


@router.message(Command("add_item"))
async def add_item_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) != 4 or not parts[1].isdigit():
        await message.answer("Формат: /add_item <channel_id> <url_or_dash> <text>")
        return
    channel_id = int(parts[1])
    url = None if parts[2] == "-" else parts[2]
    text = parts[3]
    tg_message_id = int(datetime.now(timezone.utc).timestamp() * 1000)
    async with session_factory() as session:
        channels = await queries.list_channels(session)
        if not any(channel.id == channel_id for channel in channels):
            await message.answer("Канал не найден. Сначала добавь его через /add_channel @manual thailand relocation")
            return
        try:
            post = await queries.create_post(
                session,
                channel_id=channel_id,
                tg_message_id=tg_message_id,
                post_text=text,
                post_url=url,
                score=0.5,
                intent="manual",
                status="pending",
            )
        except SQLAlchemyError as error:
            await session.rollback()
            await message.answer(f"Не удалось добавить пост: {error.__class__.__name__}")
            return
    await message.answer(f"Добавлен пост #{post.id} на ручную проверку.")


@router.callback_query(F.data.startswith("post:approve:"))
async def approve_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession], ai_service: AIService) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        if not post or not post.channel:
            await callback.answer("Пост не найден", show_alert=True)
            return
        if not can_approve(post.status, post.draft is not None):
            await callback.answer("Этот пост уже был одобрен или закрыт", show_alert=True)
            return
        text, source = await ai_service.generate_draft(post.post_text or "", post.channel.geo, post.intent, session)
        approved = await queries.approve_post(
            session,
            post_id=post.id,
            draft_text=text,
            source=source,
            delay_min=post.channel.review_delay_min,
            delay_max=post.channel.review_delay_max,
        )
        if not approved:
            await callback.answer("Не удалось одобрить пост", show_alert=True)
            return
        if source == "ai":
            await queries.increment_stat(session, "ai_drafts", 1)
        else:
            await queries.increment_stat(session, "template_drafts", 1)
    await callback.message.edit_text(f"Пост #{post_id} одобрен и попадет в reviewer-очередь по расписанию.")
    await callback.answer()


@router.message(Command("dispatch_now"))
async def dispatch_now_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /dispatch_now <post_id>")
        return
    async with session_factory() as session:
        ok = await queries.dispatch_now(session, int(parts[1]))
    await message.answer("Черновик будет отправлен reviewer-у в ближайший scheduler tick." if ok else "Одобренный черновик не найден.")


@router.callback_query(F.data.startswith("post:skip:"))
async def skip_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        result = await skip_post_once(session, post_id)
    await callback.message.edit_text(transition_message(result, "Пост пропущен."))
    await callback.answer()


@router.callback_query(F.data.startswith("post:edit:"))
async def edit_help_callback(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[-1])
    await callback.answer()
    await callback.message.answer(f"Используй: /edit_draft {post_id} новый текст")


@router.message(Command("edit_draft"))
async def edit_draft_command(message: Message, session_factory: async_sessionmaker[AsyncSession], bot: Bot) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Формат: /edit_draft <post_id> <new text>")
        return
    new_text = parts[2].strip()
    if not new_text:
        await message.answer("Черновик не должен быть пустым.")
        return
    if len(new_text) > MAX_MANUAL_DRAFT_CHARS:
        await message.answer(f"Черновик слишком длинный. Максимум: {MAX_MANUAL_DRAFT_CHARS} символов.")
        return

    async with session_factory() as session:
        post = await queries.get_post_with_details(session, int(parts[1]))
        if not post or not post.draft:
            await message.answer("Черновик не найден.")
            return
        if post.status not in EDITABLE_DRAFT_STATUSES:
            await message.answer("Этот черновик уже закрыт итоговым статусом и больше не редактируется.")
            return
        post.draft.draft_text = new_text
        was_sent_to_reviewer = post.status == "sent_to_reviewer"
        await session.commit()

    if was_sent_to_reviewer:
        if await sync_sent_reviewer_card(bot, post):
            await message.answer("Черновик обновлен и исходная reviewer-карточка синхронизирована.")
        else:
            await message.answer("Черновик обновлен в системе, но исходную reviewer-карточку обновить не удалось. Проверь /draft <post_id>.")
        return
    await message.answer("Черновик обновлен.")


async def send_review_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_review_queue(session, 20)
    if not posts:
        await message.answer("Reviewer-очередь пуста.")
        return
    for post in posts:
        draft = post.draft
        text = (
            f"На обработке #{post.id}\n"
            f"Ссылка: {escape(post.post_url or '-')}\n\n"
            f"Черновик:\n<code>{cut(draft.draft_text if draft else '', 900)}</code>"
        )
        await message.answer(text, reply_markup=reviewer_actions(post.id, post.post_url), disable_web_page_preview=True)


@router.message(Command("review_queue"))
async def review_queue_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_review_queue(message, session_factory)


@router.callback_query(F.data == "nav:review_queue")
async def review_queue_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_review_queue(callback.message, session_factory)


@router.callback_query(F.data.startswith("review:done:"))
async def reviewer_done_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        result = await mark_reviewer_done_once(session, post_id)
    await callback.message.edit_text(transition_message(result, "Отмечено как обработанное."))
    await callback.answer()


@router.callback_query(F.data.startswith("review:skip:"))
async def reviewer_skip_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        result = await skip_post_once(session, post_id)
    await callback.message.edit_text(transition_message(result, "Пост пропущен."))
    await callback.answer()
