from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.logger import get_logger
from db import queries
from services.post_audit import actor_from_user, record_post_action
from services.post_state import mark_reviewer_done_once, skip_post_once

router = Router(name=__name__)
log = get_logger(__name__)


def feedback(result: str, success: str) -> str:
    if result == "updated":
        return success
    if result == "already":
        return "Действие уже было выполнено."
    if result == "blocked":
        return "Этот пост уже закрыт другим результатом."
    return "Пост не найден."


async def audit_status_change(
    session: AsyncSession,
    *,
    post_id: int,
    action: str,
    previous_status: str | None,
    new_status: str,
    callback: CallbackQuery,
) -> None:
    try:
        await record_post_action(
            session,
            post_id=post_id,
            action=action,
            previous_status=previous_status,
            new_status=new_status,
            actor=actor_from_user(callback.from_user),
        )
    except Exception as error:
        log.warning("post_action_audit_failed", post_id=post_id, action=action, error=str(error))


async def process_skip(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        previous_status = post.status if post else None
        result = await skip_post_once(session, post_id)
        if result == "updated":
            await audit_status_change(
                session,
                post_id=post_id,
                action="skipped",
                previous_status=previous_status,
                new_status="skipped",
                callback=callback,
            )
    await callback.message.edit_text(feedback(result, "Пост пропущен."))
    await callback.answer()


@router.callback_query(F.data.startswith("post:skip:"))
async def post_skip_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await process_skip(callback, session_factory)


@router.callback_query(F.data.startswith("review:skip:"))
async def reviewer_skip_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await process_skip(callback, session_factory)


@router.callback_query(F.data.startswith("review:done:"))
async def reviewer_done_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    post_id = int(callback.data.split(":")[-1])
    async with session_factory() as session:
        post = await queries.get_post_with_details(session, post_id)
        previous_status = post.status if post else None
        result = await mark_reviewer_done_once(session, post_id)
        if result == "updated":
            await audit_status_change(
                session,
                post_id=post_id,
                action="reviewer_done",
                previous_status=previous_status,
                new_status="reviewer_done",
                callback=callback,
            )
    await callback.message.edit_text(feedback(result, "Отмечено как обработанное."))
    await callback.answer()
