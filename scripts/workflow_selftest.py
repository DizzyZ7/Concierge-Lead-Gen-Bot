from __future__ import annotations

import asyncio
import sys
from secrets import token_hex

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from core.config import get_settings
from db import queries
from db.migration_guard import ensure_schema_current
from db.models import Base, Lead, ParsedPost, PostAction, ReviewDraft, TargetChannel
from db.session import create_engine, create_session_factory, normalize_database_url
from services.lead_conversion import mark_post_as_lead
from services.post_audit import ActionActor, list_post_actions, record_post_action
from services.reviewer_claims import clear_reviewer_claim, claim_reviewer_card, get_claim_access, utc_now


class WorkflowSelfTestError(RuntimeError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise WorkflowSelfTestError(message)


async def create_isolated_engine(database_url: str, schema_name: str) -> AsyncEngine:
    return create_async_engine(
        normalize_database_url(database_url),
        pool_pre_ping=True,
        connect_args={"server_settings": {"search_path": schema_name}},
    )


async def run_workflow_selftest() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    settings = get_settings()
    admin_engine = create_engine(settings.database_url)
    admin_session_factory = create_session_factory(admin_engine)
    isolated_engine: AsyncEngine | None = None
    schema_name = f"workflow_selftest_{token_hex(6)}"
    schema_created = False

    try:
        revision = await ensure_schema_current(admin_session_factory)
        async with admin_engine.begin() as connection:
            await connection.execute(text(f'CREATE SCHEMA "{schema_name}"'))
        schema_created = True

        isolated_engine = await create_isolated_engine(settings.database_url, schema_name)
        async with isolated_engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        session_factory = create_session_factory(isolated_engine)

        async with session_factory() as session:
            channel = TargetChannel(
                channel_username="@workflow_selftest",
                channel_title="Workflow self-test",
                geo="thailand",
                category="relocation",
                is_active=True,
                daily_draft_limit=5,
                review_delay_min=0,
                review_delay_max=0,
            )
            session.add(channel)
            await session.commit()
            await session.refresh(channel)

            post = ParsedPost(
                channel_id=channel.id,
                tg_message_id=9_000_000_001,
                post_text="Ищу помощь с переездом на Пхукет. Пишите @workflow_contact",
                post_url="https://t.me/workflow_selftest/1",
                relevance_score=0.91,
                relevance_reason="Тестовый релевантный запрос.",
                content_summary="Проверка полного reviewer-first workflow.",
                suggested_angle="Уточнить сроки и район.",
                intent="relocation",
                status="pending",
            )
            session.add(post)
            await session.commit()
            await session.refresh(post)
            post_id = post.id

            approved = await queries.approve_post(
                session,
                post_id=post_id,
                draft_text="Здравствуйте. Подскажите, когда планируете переезд и какой район рассматриваете?",
                source="selftest",
                delay_min=0,
                delay_max=0,
            )
            require(approved is not None, "approve_post did not return a post")
            require(approved.status == "approved", "post did not enter approved status")
            require(approved.draft is not None, "review draft was not created")

            approved.status = "sent_to_reviewer"
            approved.draft.sent_to_reviewer_at = utc_now()
            approved.draft.reviewer_chat_id = 1
            approved.draft.reviewer_message_id = 1
            await session.commit()

        owner = ActionActor(user_id=101, username="workflow_owner", name="Workflow Owner")
        async with session_factory() as session:
            claim = await claim_reviewer_card(session, post_id=post_id, actor=owner)
            require(claim.code == "claimed", f"unexpected claim result: {claim.code}")

            owner_access = await get_claim_access(
                session,
                post_id=post_id,
                actor_user_id=owner.user_id,
                is_admin=False,
            )
            require(owner_access.code == "allowed", f"claim owner access denied: {owner_access.code}")

            other_access = await get_claim_access(
                session,
                post_id=post_id,
                actor_user_id=202,
                is_admin=False,
            )
            require(other_access.code == "taken", f"second reviewer was not blocked: {other_access.code}")

            state, lead_id = await mark_post_as_lead(session, post_id)
            require(state == "updated" and lead_id is not None, f"lead conversion failed: {state}")

            await record_post_action(
                session,
                post_id=post_id,
                action="result:lead",
                previous_status="sent_to_reviewer",
                new_status="lead",
                actor=owner,
                details=f"lead_id={lead_id}; selftest=true",
            )
            await clear_reviewer_claim(session, post_id)

            repeated_state, repeated_lead_id = await mark_post_as_lead(session, post_id)
            require(repeated_state == "already", f"lead conversion was not idempotent: {repeated_state}")
            require(repeated_lead_id == lead_id, "repeated lead conversion returned a different lead")

            lead_count = int(
                await session.scalar(select(func.count(Lead.id)).where(Lead.source_post_id == post_id)) or 0
            )
            require(lead_count == 1, f"expected one lead, found {lead_count}")

            stored_lead = await session.get(Lead, lead_id)
            require(stored_lead is not None, "created lead is missing")
            require("@workflow_contact" in (stored_lead.notes or ""), "public contact hint was not preserved")
            require("Проверь владельца" in (stored_lead.notes or ""), "contact verification warning is missing")

            actions = await list_post_actions(session, post_id)
            require(any(action.action == "result:lead" for action in actions), "lead audit action is missing")

            final_post = await session.get(ParsedPost, post_id)
            require(final_post is not None and final_post.status == "lead", "post did not finish in lead status")

            draft = await session.scalar(select(ReviewDraft).where(ReviewDraft.post_id == post_id))
            require(draft is not None, "review draft disappeared")
            require(draft.claimed_by_user_id is None, "reviewer claim was not cleared after final outcome")

            action_count = int(
                await session.scalar(select(func.count(PostAction.id)).where(PostAction.post_id == post_id)) or 0
            )
            require(action_count >= 1, "post action audit table remained empty")

        print(f"Schema revision: {revision}")
        print("Workflow self-test: passed")
        print("Verified: post -> draft -> reviewer claim -> claim guard -> lead -> audit -> cleanup")
    finally:
        if isolated_engine is not None:
            await isolated_engine.dispose()
        if schema_created:
            async with admin_engine.begin() as connection:
                await connection.execute(text(f'DROP SCHEMA IF EXISTS "{schema_name}" CASCADE'))
        await admin_engine.dispose()


async def main() -> None:
    try:
        await run_workflow_selftest()
    except Exception as error:
        print(f"Workflow self-test failed: {error.__class__.__name__}: {error}")
        raise SystemExit(1) from error


if __name__ == "__main__":
    asyncio.run(main())
