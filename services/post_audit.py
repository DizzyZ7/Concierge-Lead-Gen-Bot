from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from aiogram.types import User
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import PostAction

MAX_ACTION_LENGTH = 80
MAX_USERNAME_LENGTH = 128
MAX_ACTOR_NAME_LENGTH = 256
MAX_DETAILS_LENGTH = 1000


@dataclass(frozen=True)
class ActionActor:
    user_id: int | None
    username: str | None
    name: str | None


def actor_from_user(user: User | None) -> ActionActor:
    if user is None:
        return ActionActor(user_id=None, username=None, name=None)
    username = user.username[:MAX_USERNAME_LENGTH] if user.username else None
    name = user.full_name[:MAX_ACTOR_NAME_LENGTH] if user.full_name else None
    return ActionActor(user_id=user.id, username=username, name=name)


async def record_post_action(
    session: AsyncSession,
    *,
    post_id: int,
    action: str,
    previous_status: str | None,
    new_status: str | None,
    actor: ActionActor,
    details: str | None = None,
) -> PostAction:
    row = PostAction(
        post_id=post_id,
        action=action[:MAX_ACTION_LENGTH],
        previous_status=previous_status,
        new_status=new_status,
        actor_user_id=actor.user_id,
        actor_username=actor.username,
        actor_name=actor.name,
        details=(details or "")[:MAX_DETAILS_LENGTH] or None,
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def list_post_actions(session: AsyncSession, post_id: int, limit: int = 50) -> Sequence[PostAction]:
    result = await session.scalars(
        select(PostAction)
        .where(PostAction.post_id == post_id)
        .order_by(PostAction.created_at.desc(), PostAction.id.desc())
        .limit(limit)
    )
    return result.all()
