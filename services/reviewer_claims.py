from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import ParsedPost, ReviewDraft
from services.post_audit import ActionActor

REVIEWER_CLAIM_TIMEOUT = timedelta(minutes=45)
REVIEWER_ACTION_LEASE = timedelta(minutes=5)


@dataclass(frozen=True)
class ClaimSnapshot:
    user_id: int | None
    username: str | None
    name: str | None
    claimed_at: datetime | None
    expires_at: datetime | None


@dataclass(frozen=True)
class ClaimResult:
    code: str
    claim: ClaimSnapshot | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def normalized_time(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def snapshot_from_draft(draft: ReviewDraft | None) -> ClaimSnapshot | None:
    if draft is None or draft.claimed_by_user_id is None:
        return None
    return ClaimSnapshot(
        user_id=draft.claimed_by_user_id,
        username=draft.claimed_by_username,
        name=draft.claimed_by_name,
        claimed_at=normalized_time(draft.claimed_at),
        expires_at=normalized_time(draft.claim_expires_at),
    )


def is_active_claim(draft: ReviewDraft | None, *, now: datetime | None = None) -> bool:
    snapshot = snapshot_from_draft(draft)
    if snapshot is None or snapshot.expires_at is None:
        return False
    return snapshot.expires_at > (now or utc_now())


def claim_owner_label(snapshot: ClaimSnapshot | None) -> str:
    if snapshot is None:
        return "неизвестный reviewer"
    if snapshot.username:
        return f"@{snapshot.username}"
    if snapshot.name:
        return snapshot.name
    if snapshot.user_id:
        return str(snapshot.user_id)
    return "неизвестный reviewer"


def claim_status_line(draft: ReviewDraft | None, *, now: datetime | None = None) -> str:
    snapshot = snapshot_from_draft(draft)
    if snapshot is None:
        return "Карточка свободна. Перед действием возьми ее в работу."
    if not is_active_claim(draft, now=now):
        return "Предыдущий захват истек. Перед действием возьми карточку в работу."
    expires_at = snapshot.expires_at
    expires_text = expires_at.astimezone(timezone.utc).strftime("%H:%M UTC") if expires_at else "-"
    return f"В работе: {claim_owner_label(snapshot)} до {expires_text}."


def evaluate_claim_access(
    *,
    post_status: str | None,
    draft: ReviewDraft | None,
    actor_user_id: int | None,
    is_admin: bool,
    now: datetime | None = None,
) -> ClaimResult:
    """Return whether a human action may change the post under claim rules."""
    if post_status != "sent_to_reviewer":
        return ClaimResult("allowed")
    if is_admin:
        return ClaimResult("allowed", snapshot_from_draft(draft))
    if draft is None:
        return ClaimResult("claim_unavailable")

    snapshot = snapshot_from_draft(draft)
    if snapshot is None or not is_active_claim(draft, now=now):
        return ClaimResult("claim_required", snapshot)
    if snapshot.user_id == actor_user_id:
        return ClaimResult("allowed", snapshot)
    return ClaimResult("taken", snapshot)


async def get_claim_access(
    session: AsyncSession,
    *,
    post_id: int,
    actor_user_id: int | None,
    is_admin: bool,
) -> ClaimResult:
    post = await session.scalar(select(ParsedPost).where(ParsedPost.id == post_id))
    if post is None:
        return ClaimResult("missing")
    draft = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
    return evaluate_claim_access(
        post_status=post.status,
        draft=draft,
        actor_user_id=actor_user_id,
        is_admin=is_admin,
    )


async def secure_claim_for_action(
    session: AsyncSession,
    *,
    post_id: int,
    actor_user_id: int | None,
    is_admin: bool,
    action_lease: timedelta = REVIEWER_ACTION_LEASE,
) -> ClaimResult:
    """Atomically verify ownership and keep the claim alive while an action executes."""
    post = await session.scalar(select(ParsedPost).where(ParsedPost.id == post_id))
    if post is None:
        return ClaimResult("missing")
    if post.status != "sent_to_reviewer":
        return ClaimResult("allowed")

    draft = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
    if is_admin:
        return ClaimResult("allowed", snapshot_from_draft(draft))
    if draft is None:
        return ClaimResult("claim_unavailable")
    if actor_user_id is None:
        return ClaimResult("claim_required", snapshot_from_draft(draft))

    now = utc_now()
    action_expires_at = now + action_lease
    result = await session.execute(
        update(ReviewDraft)
        .where(
            ReviewDraft.post_id == post_id,
            ReviewDraft.claimed_by_user_id == actor_user_id,
            ReviewDraft.claim_expires_at.is_not(None),
            ReviewDraft.claim_expires_at > now,
        )
        .values(
            claim_expires_at=func.greatest(
                ReviewDraft.claim_expires_at,
                action_expires_at,
            )
        )
    )
    if result.rowcount:
        await session.commit()
        refreshed = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
        return ClaimResult("allowed", snapshot_from_draft(refreshed))

    current = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
    return evaluate_claim_access(
        post_status=post.status,
        draft=current,
        actor_user_id=actor_user_id,
        is_admin=False,
        now=now,
    )


async def claim_reviewer_card(
    session: AsyncSession,
    *,
    post_id: int,
    actor: ActionActor,
    timeout: timedelta = REVIEWER_CLAIM_TIMEOUT,
) -> ClaimResult:
    if actor.user_id is None:
        return ClaimResult("actor_missing")

    post = await session.scalar(select(ParsedPost).where(ParsedPost.id == post_id))
    if post is None:
        return ClaimResult("missing")
    if post.status != "sent_to_reviewer":
        return ClaimResult("not_reviewing")

    now = utc_now()
    expires_at = now + timeout
    current = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
    if current is None:
        return ClaimResult("missing")
    was_own_active_claim = is_active_claim(current, now=now) and current.claimed_by_user_id == actor.user_id

    result = await session.execute(
        update(ReviewDraft)
        .where(
            ReviewDraft.post_id == post_id,
            or_(
                ReviewDraft.claimed_by_user_id.is_(None),
                ReviewDraft.claim_expires_at.is_(None),
                ReviewDraft.claim_expires_at <= now,
                ReviewDraft.claimed_by_user_id == actor.user_id,
            ),
        )
        .values(
            claimed_by_user_id=actor.user_id,
            claimed_by_username=actor.username,
            claimed_by_name=actor.name,
            claimed_at=now,
            claim_expires_at=expires_at,
        )
    )
    if result.rowcount:
        await session.commit()
        return ClaimResult(
            "renewed" if was_own_active_claim else "claimed",
            ClaimSnapshot(actor.user_id, actor.username, actor.name, now, expires_at),
        )

    current = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
    return ClaimResult("taken", snapshot_from_draft(current))


async def release_reviewer_claim(
    session: AsyncSession,
    *,
    post_id: int,
    actor_user_id: int | None,
    is_admin: bool,
) -> ClaimResult:
    draft = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
    if draft is None:
        return ClaimResult("missing")
    snapshot = snapshot_from_draft(draft)
    if snapshot is None:
        return ClaimResult("not_claimed")
    if is_active_claim(draft) and not is_admin and snapshot.user_id != actor_user_id:
        return ClaimResult("taken", snapshot)

    draft.claimed_by_user_id = None
    draft.claimed_by_username = None
    draft.claimed_by_name = None
    draft.claimed_at = None
    draft.claim_expires_at = None
    await session.commit()
    return ClaimResult("released", snapshot)


async def clear_reviewer_claim(session: AsyncSession, post_id: int) -> None:
    draft = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
    if draft is None or snapshot_from_draft(draft) is None:
        return
    draft.claimed_by_user_id = None
    draft.claimed_by_username = None
    draft.claimed_by_name = None
    draft.claimed_at = None
    draft.claim_expires_at = None
    await session.commit()
