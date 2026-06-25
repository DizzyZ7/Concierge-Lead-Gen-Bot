from __future__ import annotations

from datetime import timezone

from aiogram import F, Router
from aiogram.types import CallbackQuery
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import reviewer_actions
from core.config import Settings
from core.logger import get_logger
from db import queries
from services.post_audit import actor_from_user, record_post_action
from services.reviewer_cards import render_reviewer_card
from services.reviewer_claims import (
    ClaimResult,
    claim_owner_label,
    claim_reviewer_card,
    claim_status_line,
    release_reviewer_claim,
)

router = Router(name=__name__)
log = get_logger(__name__)


def is_admin(callback: CallbackQuery, settings: Settings) -> bool:
    return bool(callback.from_user and callback.from_user.id in settings.admin_ids)


def claim_feedback(result: ClaimResult) -> str:
    if result.code == "claimed":
        return "Карточка взята в работу на 45 минут."
    if result.code == "renewed":
        return "Захват продлен еще на 45 минут."
    if result.code == "released":
        return "Карточка освобождена."
    if result.code == "taken":
        return f"Карточка уже в работе у {claim_owner_label(result.claim)}."
    if result.code == "not_claimed":
        return "Карточка сейчас свободна."
    if result.code == "not_reviewing":
        return "Эта карточка уже не находится в reviewer-очереди."
    if result.code == "actor_missing":
        return "Не удалось определить reviewer-а."
    return "Карточка не найдена."


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


async def refresh_card(callback: CallbackQuery, post) -> None:
    if callback.message is None:
        return
    try:
        await callback.message.edit_text(
            reviewer_card_text(post),
            reply_markup=reviewer_actions(post.id, post.post_url),
            disable_web_page_preview=True,
        )
    except Exception as error:
        log.warning("reviewer_claim_card_refresh_failed", post_id=post.id, error=str(error))


async def audit_claim(
    session: AsyncSession,
    *,
    post_id: int,
    action: str,
    callback: CallbackQuery,
    details: str | None = None,
) -> None:
    try:
        await record_post_action(
            session,
            post_id=post_id,
            action=action,
            previous_status="sent_to_reviewer",
            new_status="sent_to_reviewer",
            actor=actor_from_user(callback.from_user),
            details=details,
        )
    except Exception as error:
        log.warning("reviewer_claim_audit_failed", post_id=post_id, action=action, error=str(error))


@router.callback_query(F.data.startswith("review:claim:"))
async def claim_callback(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    post_id_raw = callback.data.rsplit(":", 1)[-1]
    if not post_id_raw.isdigit():
        await callback.answer("Некорректная карточка", show_alert=True)
        return
    post_id = int(post_id_raw)
    async with session_factory() as session:
        result = await claim_reviewer_card(session, post_id=post_id, actor=actor_from_user(callback.from_user))
        if result.code in {"claimed", "renewed"}:
            expires_at = result.claim.expires_at.astimezone(timezone.utc).strftime("%H:%M UTC") if result.claim and result.claim.expires_at else "-"
            await audit_claim(
                session,
                post_id=post_id,
                action="claim_renewed" if result.code == "renewed" else "claimed",
                callback=callback,
                details=f"expires_at={expires_at}",
            )
        post = await queries.get_post_with_details(session, post_id)
    if post and result.code in {"claimed", "renewed", "released"}:
        await refresh_card(callback, post)
    await callback.answer(claim_feedback(result), show_alert=result.code in {"taken", "missing", "not_reviewing", "actor_missing"})


@router.callback_query(F.data.startswith("review:release:"))
async def release_callback(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    post_id_raw = callback.data.rsplit(":", 1)[-1]
    if not post_id_raw.isdigit():
        await callback.answer("Некорректная карточка", show_alert=True)
        return
    post_id = int(post_id_raw)
    async with session_factory() as session:
        result = await release_reviewer_claim(
            session,
            post_id=post_id,
            actor_user_id=callback.from_user.id if callback.from_user else None,
            is_admin=is_admin(callback, settings),
        )
        if result.code == "released":
            details = f"released_owner={claim_owner_label(result.claim)}"
            await audit_claim(session, post_id=post_id, action="claim_released", callback=callback, details=details)
        post = await queries.get_post_with_details(session, post_id)
    if post and result.code == "released":
        await refresh_card(callback, post)
    await callback.answer(claim_feedback(result), show_alert=result.code in {"taken", "missing"})
