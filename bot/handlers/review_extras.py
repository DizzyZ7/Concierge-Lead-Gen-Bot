from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import approved_actions
from db import queries
from services.ai import AIService

router = Router(name=__name__)


def cut(text: str | None, limit: int = 1000) -> str:
    if not text:
        return ""
    return escape(text if len(text) <= limit else text[: limit - 1] + "...")


def render_draft_card(post) -> str:
    channel = post.channel.channel_username if post.channel else "unknown"
    draft = post.draft.draft_text if post.draft else "No draft yet. Approve item first."
    source = post.draft.draft_source if post.draft else "-"
    return (
        f"Draft for item #{post.id}\n"
        f"Status: {escape(post.status)}\n"
        f"Channel: {escape(channel)}\n"
        f"Source: {escape(source)}\n"
        f"URL: {escape(post.post_url or '-')}\n\n"
        f"<code>{cut(draft, 1800)}</code>"
    )


async def approve_now_flow(
    post_id: int,
    *,
    session_factory: async_sessionmaker[AsyncSession],
    ai_service: AIService,
) -> bool:
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        if not post or not post.channel:
            return False
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
            return False
        if source == "ai":
            await queries.increment_stat(session, "ai_drafts", 1)
        else:
            await queries.increment_stat(session, "template_drafts", 1)
        return True


async def send_approved_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_posts_by_status(session, "approved", 20)
    if not posts:
        await message.answer("Approved queue is empty.")
        return
    for post in posts:
        draft = post.draft
        due = draft.due_at.isoformat() if draft and draft.due_at else "-"
        text = (
            f"Approved #{post.id}\n"
            f"Due at: {escape(due)}\n"
            f"URL: {escape(post.post_url or '-')}\n\n"
            f"Draft:\n<code>{cut(draft.draft_text if draft else '', 900)}</code>"
        )
        await message.answer(text, reply_markup=approved_actions(post.id, post.post_url))


@router.callback_query(F.data.startswith("post:approve_now:"))
async def approve_now_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession], ai_service: AIService) -> None:
    post_id = int(callback.data.split(":")[-1])
    ok = await approve_now_flow(post_id, session_factory=session_factory, ai_service=ai_service)
    if ok:
        await callback.message.edit_text(f"Approved #{post_id}. It will be routed on the next scheduler tick.")
        await callback.answer()
    else:
        await callback.answer("Not found", show_alert=True)


@router.callback_query(F.data.startswith("post:dispatch:"))
async def dispatch_now_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        ok = await queries.dispatch_now(session, post_id)
    await callback.answer("Scheduled" if ok else "Not found", show_alert=not ok)


@router.callback_query(F.data.startswith("post:draft:"))
async def show_draft_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
    if not post:
        await callback.answer("Not found", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(render_draft_card(post))


@router.message(Command("draft"))
async def draft_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /draft <post_id>")
        return
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, int(parts[1]))
    await message.answer(render_draft_card(post) if post else "Item not found.")


@router.message(Command("approved_queue"))
async def approved_queue_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_approved_queue(message, session_factory)


@router.callback_query(F.data == "nav:approved_queue")
async def approved_queue_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_approved_queue(callback.message, session_factory)
