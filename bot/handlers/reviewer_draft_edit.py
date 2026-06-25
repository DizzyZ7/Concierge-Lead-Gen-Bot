from __future__ import annotations

from aiogram import Bot, Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import reviewer_actions
from core.logger import get_logger
from db import queries
from services.reviewer_cards import render_reviewer_card
from services.reviewer_claims import claim_status_line

router = Router(name=__name__)
log = get_logger(__name__)

EDITABLE_DRAFT_STATUSES = {"approved", "sent_to_reviewer", "saved"}
MAX_MANUAL_DRAFT_CHARS = 1600


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
        claim_line=claim_status_line(draft),
    )


async def sync_original_reviewer_card(bot: Bot, post) -> bool:
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
            "reviewer_claim_draft_sync_failed",
            post_id=post.id,
            reviewer_chat_id=draft.reviewer_chat_id,
            reviewer_message_id=draft.reviewer_message_id,
            error=str(error),
        )
        return False


@router.message(Command("edit_draft"))
async def edit_draft_command(
    message: Message,
    bot: Bot,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    parts = (message.text or "").split(maxsplit=2)
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

    if not was_sent_to_reviewer:
        await message.answer("Черновик обновлен.")
        return
    if await sync_original_reviewer_card(bot, post):
        await message.answer("Черновик обновлен и reviewer-карточка синхронизирована.")
    else:
        await message.answer("Черновик обновлен в системе, но исходную reviewer-карточку обновить не удалось. Проверь /draft <post_id>.")
