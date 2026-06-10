from __future__ import annotations

from datetime import datetime, timezone
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import pending_actions, reviewer_actions
from db import queries
from services.ai import AIService

router = Router(name=__name__)


def cut(text: str | None, limit: int = 700) -> str:
    if not text:
        return ""
    return escape(text if len(text) <= limit else text[: limit - 1] + "...")


async def send_pending(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        items = await queries.list_pending_posts(session, 10)
    if not items:
        await message.answer("No pending items.")
        return
    for item in items:
        channel = item.channel.channel_username if item.channel else "unknown"
        text = (
            f"Pending #{item.id}\n"
            f"Channel: {escape(channel)}\n"
            f"Score: {item.relevance_score:.2f}\n"
            f"Intent: {escape(item.intent)}\n"
            f"URL: {escape(item.post_url or '-')}\n\n"
            f"Text:\n{cut(item.post_text)}"
        )
        await message.answer(text, reply_markup=pending_actions(item.id))


@router.message(Command("pending"))
async def pending_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_pending(message, session_factory)


@router.callback_query(F.data == "nav:pending")
async def pending_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_pending(callback.message, session_factory)


@router.message(Command("add_item"))
async def add_item_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=3)
    if len(parts) != 4 or not parts[1].isdigit():
        await message.answer("Usage: /add_item <channel_id> <url_or_dash> <text>")
        return
    channel_id = int(parts[1])
    url = None if parts[2] == "-" else parts[2]
    text = parts[3]
    tg_message_id = int(datetime.now(timezone.utc).timestamp() * 1000)
    async with session_factory() as session:
        channels = await queries.list_channels(session)
        if not any(channel.id == channel_id for channel in channels):
            await message.answer("Channel not found. Create it first with /add_channel @manual thailand relocation")
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
            await message.answer(f"Could not add item: {error.__class__.__name__}")
            return
    await message.answer(f"Added pending item #{post.id}.")


@router.callback_query(F.data.startswith("post:approve:"))
async def approve_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession], ai_service: AIService) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        if not post or not post.channel:
            await callback.answer("Not found", show_alert=True)
            return
        text, source = await ai_service.generate_draft(post.post_text or "", post.channel.geo, post.intent, session)
        post = await queries.approve_post(
            session,
            post_id=post.id,
            draft_text=text,
            source=source,
            delay_min=post.channel.review_delay_min,
            delay_max=post.channel.review_delay_max,
        )
        if source == "ai":
            await queries.increment_stat(session, "ai_drafts", 1)
        else:
            await queries.increment_stat(session, "template_drafts", 1)
    await callback.message.edit_text(f"Approved #{post_id}. It will be sent to reviewer queue.")
    await callback.answer()


@router.message(Command("dispatch_now"))
async def dispatch_now_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /dispatch_now <post_id>")
        return
    async with session_factory() as session:
        ok = await queries.dispatch_now(session, int(parts[1]))
    await message.answer("Draft will be sent to reviewer within one scheduler tick." if ok else "Approved draft not found.")


@router.callback_query(F.data.startswith("post:skip:"))
async def skip_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        ok = await queries.skip_post(session, post_id)
    await callback.message.edit_text("Skipped." if ok else "Not found.")
    await callback.answer()


@router.callback_query(F.data.startswith("post:edit:"))
async def edit_help_callback(callback: CallbackQuery) -> None:
    post_id = int(callback.data.split(":")[-1])
    await callback.answer()
    await callback.message.answer(f"Use: /edit_draft {post_id} new text")


@router.message(Command("edit_draft"))
async def edit_draft_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) < 3 or not parts[1].isdigit():
        await message.answer("Usage: /edit_draft <post_id> <new text>")
        return
    async with session_factory() as session:
        ok = await queries.update_draft_text(session, int(parts[1]), parts[2])
    await message.answer("Updated." if ok else "Draft not found.")


async def send_review_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_review_queue(session, 20)
    if not posts:
        await message.answer("Review queue is empty.")
        return
    for post in posts:
        draft = post.draft
        text = (
            f"Review #{post.id}\n"
            f"URL: {escape(post.post_url or '-')}\n\n"
            f"Draft:\n<code>{cut(draft.draft_text if draft else '', 900)}</code>"
        )
        await message.answer(text, reply_markup=reviewer_actions(post.id, post.post_url))


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
        ok = await queries.mark_reviewer_done(session, post_id)
    await callback.message.edit_text("Marked as done." if ok else "Not found.")
    await callback.answer()


@router.callback_query(F.data.startswith("review:skip:"))
async def reviewer_skip_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        ok = await queries.skip_post(session, post_id)
    await callback.message.edit_text("Skipped." if ok else "Not found.")
    await callback.answer()
