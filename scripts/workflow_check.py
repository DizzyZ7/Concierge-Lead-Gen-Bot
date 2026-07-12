from __future__ import annotations

import asyncio
import os
from dataclasses import dataclass
from datetime import date
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.results import mark_as_lead
from core.config import get_settings
from db import queries
from db.migration_guard import ensure_schema_current
from db.models import DailyStat, Lead, ParsedPost, PostAction, ReviewDraft, TargetChannel
from db.session import create_engine, create_session_factory
from services.post_audit import ActionActor, list_post_actions, record_post_action
from services.reviewer_claims import clear_reviewer_claim, claim_reviewer_card, get_claim_access

ALLOW_MUTATION_ENV = "WORKFLOW_CHECK_ALLOW_MUTATION"
STAT_FIELDS = (
    "posts_parsed",
    "drafts_sent",
    "reviewer_done",
    "leads_received",
    "deals_closed",
    "revenue",
    "ai_drafts",
    "template_drafts",
    "ai_failures",
)


@dataclass(frozen=True)
class StatsSnapshot:
    existed: bool
    values: dict[str, object]


def mutation_enabled(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes"}


async def capture_stats(session: AsyncSession, target_date: date) -> StatsSnapshot:
    row = await session.scalar(select(DailyStat).where(DailyStat.date == target_date))
    if row is None:
        return StatsSnapshot(existed=False, values={})
    return StatsSnapshot(existed=True, values={field: getattr(row, field) for field in STAT_FIELDS})


async def restore_stats(session: AsyncSession, target_date: date, snapshot: StatsSnapshot) -> None:
    row = await session.scalar(select(DailyStat).where(DailyStat.date == target_date))
    if not snapshot.existed:
        if row is not None:
            await session.delete(row)
        return
    if row is None:
        row = DailyStat(date=target_date)
        session.add(row)
        await session.flush()
    for field, value in snapshot.values.items():
        setattr(row, field, value)


async def cleanup(
    session_factory: async_sessionmaker[AsyncSession],
    *,
    channel_id: int | None,
    target_date: date,
    stats_snapshot: StatsSnapshot,
) -> None:
    async with session_factory() as session:
        if channel_id is not None:
            post_ids = select(ParsedPost.id).where(ParsedPost.channel_id == channel_id)
            await session.execute(delete(Lead).where(Lead.source_post_id.in_(post_ids)))
            await session.execute(delete(TargetChannel).where(TargetChannel.id == channel_id))
        await restore_stats(session, target_date, stats_snapshot)
        await session.commit()


async def run_workflow_check() -> None:
    if not mutation_enabled(os.getenv(ALLOW_MUTATION_ENV)):
        raise RuntimeError(
            f"Refusing to mutate the database. Set {ALLOW_MUTATION_ENV}=true only for an isolated test database."
        )

    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    channel_id: int | None = None
    target_date = queries.business_today()

    async with session_factory() as session:
        stats_snapshot = await capture_stats(session, target_date)

    marker = uuid4().hex[:12]
    actor = ActionActor(user_id=910001, username="workflow_check", name="Workflow Check")
    other_actor_id = 910002

    try:
        await ensure_schema_current(session_factory)

        async with session_factory() as session:
            channel = await queries.add_channel(session, f"@workflow_{marker}", "thailand", "relocation")
            channel_id = channel.id
            post = await queries.create_post(
                session,
                channel_id=channel.id,
                tg_message_id=int(marker[:10], 16),
                post_text="Ищу помощь с переездом на Пхукет, связь @workflow_contact",
                post_url=f"https://t.me/workflow_{marker}/1",
                score=0.91,
                intent="relocation",
                status="pending",
                relevance_reason="Интеграционный сценарий релевантного поста.",
                content_summary="Проверка полного reviewer workflow.",
                suggested_angle="Уточнить сроки переезда.",
                text_hash=marker,
            )
            post_id = post.id
            approved = await queries.approve_post(
                session,
                post_id=post_id,
                draft_text="Уточните, пожалуйста, сроки переезда и район.",
                source="workflow_check",
                delay_min=0,
                delay_max=0,
            )
            if approved is None or approved.draft is None:
                raise AssertionError("Draft was not created")
            await queries.mark_draft_sent(
                session,
                approved.draft.id,
                reviewer_chat_id=910000,
                reviewer_message_id=1,
            )

        async with session_factory() as session:
            claim = await claim_reviewer_card(session, post_id=post_id, actor=actor)
            if claim.code != "claimed":
                raise AssertionError(f"Expected claimed, got {claim.code}")

            own_access = await get_claim_access(
                session,
                post_id=post_id,
                actor_user_id=actor.user_id,
                is_admin=False,
            )
            other_access = await get_claim_access(
                session,
                post_id=post_id,
                actor_user_id=other_actor_id,
                is_admin=False,
            )
            if own_access.code != "allowed" or other_access.code != "taken":
                raise AssertionError(
                    f"Claim ownership failed: owner={own_access.code}, other={other_access.code}"
                )

            previous_status = "sent_to_reviewer"
            lead_state, lead_id = await mark_as_lead(session, post_id)
            if lead_state != "updated" or lead_id is None:
                raise AssertionError(f"Lead conversion failed: {lead_state}")
            await record_post_action(
                session,
                post_id=post_id,
                action="result:lead",
                previous_status=previous_status,
                new_status="lead",
                actor=actor,
                details=f"lead_id={lead_id}; workflow_check=true",
            )
            await clear_reviewer_claim(session, post_id)

        async with session_factory() as session:
            post = await queries.get_post_with_details(session, post_id)
            if post is None or post.status != "lead" or post.draft is None:
                raise AssertionError("Post did not reach the lead state")
            if post.draft.claimed_by_user_id is not None or post.draft.claim_expires_at is not None:
                raise AssertionError("Reviewer claim was not cleared")

            lead_count = int(
                await session.scalar(select(func.count(Lead.id)).where(Lead.source_post_id == post_id)) or 0
            )
            if lead_count != 1:
                raise AssertionError(f"Expected one lead, got {lead_count}")

            actions = await list_post_actions(session, post_id)
            if not any(action.action == "result:lead" and action.actor_user_id == actor.user_id for action in actions):
                raise AssertionError("Lead audit action was not recorded")

            duplicate_state, duplicate_lead_id = await mark_as_lead(session, post_id)
            if duplicate_state != "already" or duplicate_lead_id != lead_id:
                raise AssertionError(
                    f"Duplicate lead protection failed: state={duplicate_state}, id={duplicate_lead_id}"
                )

            duplicate_count = int(
                await session.scalar(select(func.count(Lead.id)).where(Lead.source_post_id == post_id)) or 0
            )
            if duplicate_count != 1:
                raise AssertionError(f"Duplicate lead was created: count={duplicate_count}")

        print("Workflow integration check passed")
    finally:
        await cleanup(
            session_factory,
            channel_id=channel_id,
            target_date=target_date,
            stats_snapshot=stats_snapshot,
        )
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(run_workflow_check())
