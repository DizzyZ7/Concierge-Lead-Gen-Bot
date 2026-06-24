from __future__ import annotations

from datetime import timezone
from html import escape

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import queries
from services.post_audit import list_post_actions

router = Router(name=__name__)


def action_label(action: str) -> str:
    labels = {
        "result:lead": "Стал лидом",
        "result:commented": "Комментарий написан",
        "result:content_idea": "Сохранено как идея",
        "result:not_relevant": "Отмечено нерелевантным",
        "saved": "Сохранено",
        "skipped": "Пропущено",
        "reviewer_done": "Отмечено обработанным",
    }
    return labels.get(action, action)


def actor_label(action) -> str:
    if action.actor_username:
        return f"@{action.actor_username}"
    if action.actor_name:
        return action.actor_name
    if action.actor_user_id:
        return str(action.actor_user_id)
    return "не указан"


@router.message(Command("post_history"))
async def post_history_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /post_history <post_id>")
        return
    post_id = int(parts[1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        if not post:
            await message.answer("Пост не найден.")
            return
        actions = await list_post_actions(session, post_id)

    if not actions:
        await message.answer(f"История поста #{post_id} пока пуста.")
        return

    lines = [f"История поста #{post_id}", ""]
    for action in actions:
        timestamp = action.created_at
        normalized = timestamp if timestamp.tzinfo else timestamp.replace(tzinfo=timezone.utc)
        time_text = normalized.astimezone(timezone.utc).strftime("%d.%m %H:%M UTC")
        transition = f"{action.previous_status or '-'} → {action.new_status or '-'}"
        lines.append(
            f"{time_text} — {escape(action_label(action.action))}\n"
            f"  {escape(actor_label(action))} | {escape(transition)}"
        )
        if action.details:
            lines.append(f"  {escape(action.details)}")
    await message.answer("\n".join(lines))
