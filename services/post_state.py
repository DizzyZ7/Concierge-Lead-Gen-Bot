from __future__ import annotations

from datetime import datetime, timezone
from typing import Final, Literal

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from db import queries
from db.models import ParsedPost, ReviewDraft

TransitionResult = Literal["updated", "already", "blocked", "missing"]

FINAL_OUTCOME_STATUSES: Final[frozenset[str]] = frozenset(
    {"lead", "commented", "content_idea", "not_relevant", "skipped"}
)
LEAD_BLOCKED_STATUSES: Final[frozenset[str]] = frozenset({"not_relevant", "skipped"})
APPROVABLE_STATUSES: Final[frozenset[str]] = frozenset(
    {"pending", "queued_by_limit", "saved", "processing_failed"}
)


def can_approve(status: str, has_draft: bool) -> bool:
    return status in APPROVABLE_STATUSES and not has_draft


def can_mark_as_lead(status: str) -> bool:
    return status not in LEAD_BLOCKED_STATUSES


async def _current_status(session: AsyncSession, post_id: int) -> str | None:
    return await session.scalar(select(ParsedPost.status).where(ParsedPost.id == post_id))


async def mark_reviewer_done_once(session: AsyncSession, post_id: int) -> TransitionResult:
    result = await session.execute(
        update(ParsedPost)
        .where(ParsedPost.id == post_id, ParsedPost.status == "sent_to_reviewer")
        .values(status="reviewer_done")
    )
    if result.rowcount:
        await session.execute(
            update(ReviewDraft)
            .where(ReviewDraft.post_id == post_id)
            .values(marked_done_at=datetime.now(timezone.utc))
        )
        await queries.increment_stat(session, "reviewer_done", 1)
        return "updated"

    current = await _current_status(session, post_id)
    if current is None:
        return "missing"
    if current == "reviewer_done":
        return "already"
    return "blocked"


async def apply_result_once(session: AsyncSession, post_id: int, target_status: str) -> TransitionResult:
    if target_status not in FINAL_OUTCOME_STATUSES:
        raise ValueError(f"Unsupported final post status: {target_status}")

    result = await session.execute(
        update(ParsedPost)
        .where(ParsedPost.id == post_id, ~ParsedPost.status.in_(FINAL_OUTCOME_STATUSES))
        .values(status=target_status)
    )
    if result.rowcount:
        await session.commit()
        return "updated"

    current = await _current_status(session, post_id)
    if current is None:
        return "missing"
    if current == target_status:
        return "already"
    return "blocked"


async def save_post_once(session: AsyncSession, post_id: int) -> TransitionResult:
    result = await session.execute(
        update(ParsedPost)
        .where(
            ParsedPost.id == post_id,
            ParsedPost.status != "saved",
            ~ParsedPost.status.in_(FINAL_OUTCOME_STATUSES),
        )
        .values(status="saved")
    )
    if result.rowcount:
        await session.commit()
        return "updated"

    current = await _current_status(session, post_id)
    if current is None:
        return "missing"
    if current == "saved":
        return "already"
    return "blocked"


async def skip_post_once(session: AsyncSession, post_id: int) -> TransitionResult:
    return await apply_result_once(session, post_id, "skipped")
