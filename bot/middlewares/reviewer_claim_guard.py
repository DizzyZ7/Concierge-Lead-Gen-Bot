from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.logger import get_logger
from db import queries
from services.reviewer_claims import claim_owner_label, clear_reviewer_claim, get_claim_access

log = get_logger(__name__)

PROTECTED_CALLBACK_PREFIXES = (
    "review:done:",
    "review:skip:",
    "post:skip:",
    "post:save:",
    "result:",
)


def protected_post_id(event: TelegramObject) -> int | None:
    if isinstance(event, CallbackQuery):
        data = event.data or ""
        if not any(data.startswith(prefix) for prefix in PROTECTED_CALLBACK_PREFIXES):
            return None
        value = data.rsplit(":", 1)[-1]
        return int(value) if value.isdigit() else None

    if isinstance(event, Message):
        parts = (event.text or "").split(maxsplit=2)
        if len(parts) >= 2 and parts[0].split("@", 1)[0] == "/edit_draft" and parts[1].isdigit():
            return int(parts[1])
    return None


class ReviewerClaimGuardMiddleware(BaseMiddleware):
    """Prevent reviewers from changing an actively claimed card owned by someone else."""

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:
        post_id = protected_post_id(event)
        session_factory: async_sessionmaker[AsyncSession] | None = data.get("session_factory")
        settings: Settings | None = data.get("settings")
        if post_id is None or session_factory is None or settings is None:
            return await handler(event, data)

        actor_user = event.from_user if isinstance(event, (CallbackQuery, Message)) else None
        actor_id = actor_user.id if actor_user else None
        is_admin = actor_id in settings.admin_ids if actor_id is not None else False
        try:
            async with session_factory() as session:
                access = await get_claim_access(
                    session,
                    post_id=post_id,
                    actor_user_id=actor_id,
                    is_admin=is_admin,
                )
        except Exception as error:
            log.warning("reviewer_claim_guard_check_failed", post_id=post_id, error=str(error))
            return await handler(event, data)

        if access.code == "taken":
            message = f"Карточка уже в работе у {claim_owner_label(access.claim)}."
            if isinstance(event, CallbackQuery):
                await event.answer(message, show_alert=True)
            elif isinstance(event, Message):
                await event.answer(message)
            return None

        result = await handler(event, data)

        if isinstance(event, CallbackQuery):
            try:
                async with session_factory() as session:
                    post = await queries.get_post_with_details(session, post_id)
                    if post and post.status != "sent_to_reviewer":
                        await clear_reviewer_claim(session, post_id)
            except Exception as error:
                log.warning("reviewer_claim_clear_failed", post_id=post_id, error=str(error))
        return result
