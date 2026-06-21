from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import saved_actions
from db import queries
from db.models import Lead

router = Router(name=__name__)

RESULT_STATUS_MAP = {
    "commented": "commented",
    "lead": "lead",
    "content_idea": "content_idea",
    "not_relevant": "not_relevant",
}

RESULT_LABELS = {
    "commented": "Marked as commented",
    "lead": "Marked as lead",
    "content_idea": "Saved as content idea",
    "not_relevant": "Marked as not relevant",
}


def cut(text: str | None, limit: int = 700) -> str:
    value = text or ""
    return value if len(value) <= limit else value[: limit - 1] + "..."


async def mark_as_lead(session: AsyncSession, post_id: int) -> tuple[bool, int | None, bool]:
    post = await queries.get_post_with_details(session, post_id)
    if not post:
        return False, None, False

    existing = await session.scalar(select(Lead).where(Lead.source_post_id == post_id).limit(1))
    if existing:
        if post.status != "lead":
            post.status = "lead"
            await session.commit()
        return True, existing.id, False

    lead = Lead(
        source_post_id=post.id,
        geo=post.channel.geo if post.channel else None,
        intent=post.intent,
        notes=f"Lead Radar item #{post.id}. Fill contact details after direct response.",
    )
    session.add(lead)
    post.status = "lead"
    await session.flush()
    await queries.increment_stat(session, "leads_received", 1)
    await session.refresh(lead)
    return True, lead.id, True


async def send_content_ideas(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_content_ideas(session, 20)
    if not posts:
        await message.answer("Content ideas queue is empty.")
        return
    for post in posts:
        channel = post.channel.channel_username if post.channel else "unknown"
        score = f"{post.relevance_score:.2f}" if post.relevance_score is not None else "-"
        text = (
            f"Content idea #{post.id}\n"
            f"Channel: {escape(channel)}\n"
            f"Category: {escape(post.intent)}\n"
            f"Score: {escape(score)}\n"
            f"Summary: {escape(post.content_summary or '-')}\n"
            f"Angle: {escape(post.suggested_angle or '-')}\n"
            f"URL: {escape(post.post_url or '-')}\n\n"
            f"Text:\n{escape(cut(post.post_text))}"
        )
        await message.answer(text, reply_markup=saved_actions(post.id, post.post_url), disable_web_page_preview=True)


@router.callback_query(F.data.startswith("result:"))
async def result_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = callback.data.split(":")
    if len(parts) != 3 or parts[1] not in RESULT_STATUS_MAP or not parts[2].isdigit():
        await callback.answer("Unknown result", show_alert=True)
        return
    result = parts[1]
    post_id = int(parts[2])
    async with session_factory() as session:
        if result == "lead":
            ok, lead_id, created = await mark_as_lead(session, post_id)
            label = f"Lead #{lead_id} created" if created else f"Lead #{lead_id} already exists"
        else:
            ok = await queries.mark_post_status(session, post_id, RESULT_STATUS_MAP[result])
            label = RESULT_LABELS[result]
    await callback.answer(label if ok else "Not found", show_alert=not ok)


@router.message(Command("content_ideas"))
async def content_ideas_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_content_ideas(message, session_factory)


@router.callback_query(F.data == "nav:content_ideas")
async def content_ideas_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_content_ideas(callback.message, session_factory)
