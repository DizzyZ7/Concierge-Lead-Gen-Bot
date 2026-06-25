from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import reviewer_actions
from services.reviewer_cards import escape_and_trim
from services.reviewer_claims import claim_status_line
from db import queries

router = Router(name=__name__)


def render_review_queue_item(post) -> str:
    draft = post.draft
    channel = post.channel.channel_username if post.channel else "неизвестно"
    return (
        f"На обработке #{post.id}\n"
        f"Канал: {escape_and_trim(channel, 200)}\n"
        f"Статус работы: {escape_and_trim(claim_status_line(draft), 260)}\n"
        f"Ссылка: {escape_and_trim(post.post_url or '-', 500)}\n\n"
        f"Черновик:\n<code>{escape_and_trim(draft.draft_text if draft else '', 900)}</code>"
    )


async def send_reviewer_queue(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        posts = await queries.list_review_queue(session, 20)
    if not posts:
        await message.answer("Reviewer-очередь пуста.")
        return
    for post in posts:
        await message.answer(
            render_review_queue_item(post),
            reply_markup=reviewer_actions(post.id, post.post_url),
            disable_web_page_preview=True,
        )


@router.message(Command("review_queue"))
async def review_queue_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_reviewer_queue(message, session_factory)


@router.callback_query(F.data == "nav:review_queue")
async def review_queue_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_reviewer_queue(callback.message, session_factory)
