from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import queries

router = Router(name=__name__)


def cut(text: str | None, limit: int = 1800) -> str:
    value = text or ""
    return value if len(value) <= limit else value[: limit - 1] + "..."


def render_source(post) -> str:
    channel = post.channel.channel_username if post.channel else "unknown"
    score = f"{post.relevance_score:.2f}" if post.relevance_score is not None else "-"
    return (
        f"Source item #{post.id}\n"
        f"Status: {escape(post.status)}\n"
        f"Channel: {escape(channel)}\n"
        f"Category: {escape(post.intent)}\n"
        f"Score: {escape(score)}\n"
        f"Reason: {escape(post.relevance_reason or '-')}\n"
        f"Summary: {escape(post.content_summary or '-')}\n"
        f"Angle: {escape(post.suggested_angle or '-')}\n"
        f"URL: {escape(post.post_url or '-')}\n\n"
        f"Text:\n{escape(cut(post.post_text))}"
    )


@router.message(Command("source"))
async def source_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Usage: /source <post_id>")
        return
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, int(parts[1]))
    await message.answer(render_source(post) if post else "Item not found.", disable_web_page_preview=True)


@router.callback_query(F.data.startswith("post:source:"))
async def source_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
    if not post:
        await callback.answer("Not found", show_alert=True)
        return
    await callback.answer()
    await callback.message.answer(render_source(post), disable_web_page_preview=True)
