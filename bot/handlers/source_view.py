from __future__ import annotations

from html import escape

from aiogram.filters import Command
from aiogram import Router
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import queries

router = Router(name=__name__)


def cut(text: str | None, limit: int = 1800) -> str:
    value = text or ""
    return value if len(value) <= limit else value[: limit - 1] + "..."


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
    if not post:
        await message.answer("Item not found.")
        return
    channel = post.channel.channel_username if post.channel else "unknown"
    score = f"{post.relevance_score:.2f}" if post.relevance_score is not None else "-"
    text = (
        f"Source item #{post.id}\n"
        f"Status: {escape(post.status)}\n"
        f"Channel: {escape(channel)}\n"
        f"Category: {escape(post.intent)}\n"
        f"Score: {escape(score)}\n"
        f"Reason: {escape(post.relevance_reason or '-')}\n"
        f"URL: {escape(post.post_url or '-')}\n\n"
        f"Text:\n{escape(cut(post.post_text))}"
    )
    await message.answer(text, disable_web_page_preview=True)
