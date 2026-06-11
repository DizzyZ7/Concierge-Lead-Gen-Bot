from __future__ import annotations

import random
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Sequence

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from db.models import AppSetting, DailyStat, DraftTemplate, Lead, ParsedPost, ReviewDraft, TargetChannel


async def get_today_stats(session: AsyncSession) -> DailyStat:
    today = date.today()
    row = await session.scalar(select(DailyStat).where(DailyStat.date == today))
    if row:
        return row
    row = DailyStat(date=today)
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return row


async def increment_stat(session: AsyncSession, field: str, value: int | Decimal = 1) -> None:
    stats = await get_today_stats(session)
    current = getattr(stats, field)
    setattr(stats, field, current + value)
    await session.commit()


async def get_setting(session: AsyncSession, key: str, default: str | None = None) -> str | None:
    row = await session.get(AppSetting, key)
    return row.value if row else default


async def set_setting(session: AsyncSession, key: str, value: str) -> None:
    row = await session.get(AppSetting, key)
    if row:
        row.value = value
    else:
        session.add(AppSetting(key=key, value=value))
    await session.commit()


async def is_paused(session: AsyncSession) -> bool:
    return (await get_setting(session, "paused", "false")) == "true"


async def is_auto_approve(session: AsyncSession, default: bool) -> bool:
    value = await get_setting(session, "auto_approve", str(default).lower())
    return value == "true"


async def add_channel(session: AsyncSession, username: str, geo: str, category: str | None) -> TargetChannel:
    username = username if username.startswith("@") else f"@{username}"
    channel = TargetChannel(channel_username=username, geo=geo, category=category)
    session.add(channel)
    await session.commit()
    await session.refresh(channel)
    return channel


async def list_channels(session: AsyncSession) -> Sequence[TargetChannel]:
    result = await session.scalars(select(TargetChannel).order_by(TargetChannel.id))
    return result.all()


async def list_active_channels(session: AsyncSession) -> Sequence[TargetChannel]:
    result = await session.scalars(select(TargetChannel).where(TargetChannel.is_active.is_(True)).order_by(TargetChannel.id))
    return result.all()


async def toggle_channel(session: AsyncSession, channel_id: int) -> TargetChannel | None:
    channel = await session.get(TargetChannel, channel_id)
    if not channel:
        return None
    channel.is_active = not channel.is_active
    await session.commit()
    await session.refresh(channel)
    return channel


async def set_channel_limit(session: AsyncSession, channel_id: int, limit: int) -> TargetChannel | None:
    channel = await session.get(TargetChannel, channel_id)
    if not channel:
        return None
    channel.daily_draft_limit = limit
    await session.commit()
    await session.refresh(channel)
    return channel


async def set_channel_delay(session: AsyncSession, channel_id: int, delay_min: int, delay_max: int) -> TargetChannel | None:
    channel = await session.get(TargetChannel, channel_id)
    if not channel:
        return None
    channel.review_delay_min = delay_min
    channel.review_delay_max = delay_max
    await session.commit()
    await session.refresh(channel)
    return channel


async def post_exists(session: AsyncSession, channel_id: int, tg_message_id: int) -> bool:
    row = await session.scalar(
        select(ParsedPost.id).where(ParsedPost.channel_id == channel_id, ParsedPost.tg_message_id == tg_message_id)
    )
    return row is not None


async def text_hash_exists(session: AsyncSession, value: str | None) -> bool:
    if not value:
        return False
    row = await session.scalar(select(ParsedPost.id).where(ParsedPost.text_hash == value).limit(1))
    return row is not None


async def create_post(
    session: AsyncSession,
    *,
    channel_id: int,
    tg_message_id: int,
    post_text: str | None,
    post_url: str | None,
    score: float,
    intent: str,
    status: str,
    relevance_reason: str | None = None,
    content_summary: str | None = None,
    suggested_angle: str | None = None,
    text_hash: str | None = None,
) -> ParsedPost:
    post = ParsedPost(
        channel_id=channel_id,
        tg_message_id=tg_message_id,
        post_text=post_text,
        post_url=post_url,
        text_hash=text_hash,
        relevance_score=score,
        relevance_reason=relevance_reason,
        content_summary=content_summary,
        suggested_angle=suggested_angle,
        intent=intent,
        status=status,
    )
    session.add(post)
    await increment_stat(session, "posts_parsed", 1)
    await session.refresh(post)
    return post


async def list_posts_by_status(session: AsyncSession, status: str, limit: int = 20) -> Sequence[ParsedPost]:
    result = await session.scalars(
        select(ParsedPost)
        .options(selectinload(ParsedPost.channel), selectinload(ParsedPost.draft))
        .where(ParsedPost.status == status)
        .order_by(ParsedPost.created_at.desc())
        .limit(limit)
    )
    return result.all()


async def list_pending_posts(session: AsyncSession, limit: int = 10) -> Sequence[ParsedPost]:
    return await list_posts_by_status(session, "pending", limit)


async def get_post_with_details(session: AsyncSession, post_id: int) -> ParsedPost | None:
    return await session.scalar(
        select(ParsedPost)
        .options(selectinload(ParsedPost.channel), selectinload(ParsedPost.draft))
        .where(ParsedPost.id == post_id)
    )


async def approve_post(
    session: AsyncSession,
    *,
    post_id: int,
    draft_text: str,
    source: str,
    delay_min: int,
    delay_max: int,
) -> ParsedPost | None:
    post = await get_post_with_details(session, post_id)
    if not post:
        return None
    minutes = random.randint(delay_min, delay_max)
    due_at = datetime.now(timezone.utc) + timedelta(minutes=minutes)
    post.status = "approved"
    if post.draft:
        post.draft.draft_text = draft_text
        post.draft.draft_source = source
        post.draft.due_at = due_at
    else:
        session.add(ReviewDraft(post_id=post.id, draft_text=draft_text, draft_source=source, due_at=due_at))
    await session.commit()
    return await get_post_with_details(session, post_id)


async def dispatch_now(session: AsyncSession, post_id: int) -> bool:
    post = await get_post_with_details(session, post_id)
    if not post or not post.draft or post.status not in {"approved", "sent_to_reviewer"}:
        return False
    if post.status == "sent_to_reviewer":
        return True
    post.draft.due_at = datetime.now(timezone.utc)
    await session.commit()
    return True


async def mark_post_status(session: AsyncSession, post_id: int, status: str) -> bool:
    post = await session.get(ParsedPost, post_id)
    if not post:
        return False
    post.status = status
    await session.commit()
    return True


async def mark_post_saved(session: AsyncSession, post_id: int) -> bool:
    return await mark_post_status(session, post_id, "saved")


async def skip_post(session: AsyncSession, post_id: int) -> bool:
    return await mark_post_status(session, post_id, "skipped")


async def update_draft_text(session: AsyncSession, post_id: int, text: str) -> bool:
    post = await get_post_with_details(session, post_id)
    if not post or not post.draft:
        return False
    post.draft.draft_text = text
    await session.commit()
    return True


async def due_review_drafts(session: AsyncSession, limit: int = 10) -> Sequence[ReviewDraft]:
    now = datetime.now(timezone.utc)
    result = await session.scalars(
        select(ReviewDraft)
        .options(selectinload(ReviewDraft.post).selectinload(ParsedPost.channel))
        .join(ReviewDraft.post)
        .where(
            ParsedPost.status == "approved",
            ReviewDraft.sent_to_reviewer_at.is_(None),
            ReviewDraft.due_at <= now,
        )
        .order_by(ReviewDraft.due_at)
        .limit(limit)
    )
    return result.all()


async def mark_draft_sent(session: AsyncSession, draft_id: int, reviewer_chat_id: int, reviewer_message_id: int) -> None:
    draft = await session.get(ReviewDraft, draft_id)
    if not draft:
        return
    draft.sent_to_reviewer_at = datetime.now(timezone.utc)
    draft.reviewer_chat_id = reviewer_chat_id
    draft.reviewer_message_id = reviewer_message_id
    post = await session.get(ParsedPost, draft.post_id)
    if post:
        post.status = "sent_to_reviewer"
    await increment_stat(session, "drafts_sent", 1)


async def mark_reviewer_done(session: AsyncSession, post_id: int) -> bool:
    post = await get_post_with_details(session, post_id)
    if not post or not post.draft:
        return False
    post.status = "reviewer_done"
    post.draft.marked_done_at = datetime.now(timezone.utc)
    await increment_stat(session, "reviewer_done", 1)
    return True


async def list_review_queue(session: AsyncSession, limit: int = 20) -> Sequence[ParsedPost]:
    return await list_posts_by_status(session, "sent_to_reviewer", limit)


async def list_saved_posts(session: AsyncSession, limit: int = 20) -> Sequence[ParsedPost]:
    return await list_posts_by_status(session, "saved", limit)


async def list_content_ideas(session: AsyncSession, limit: int = 20) -> Sequence[ParsedPost]:
    return await list_posts_by_status(session, "content_idea", limit)


async def count_drafts_today(session: AsyncSession, channel_id: int | None = None) -> int:
    today = date.today()
    stmt = select(func.count(ReviewDraft.id)).join(ReviewDraft.post).where(func.date(ReviewDraft.created_at) == today)
    if channel_id is not None:
        stmt = stmt.where(ParsedPost.channel_id == channel_id)
    return int(await session.scalar(stmt) or 0)


async def get_random_template(session: AsyncSession, geo: str | None, category: str | None) -> DraftTemplate | None:
    result = await session.scalars(
        select(DraftTemplate).where(
            DraftTemplate.is_active.is_(True),
            and_(DraftTemplate.geo.in_([geo, None]), DraftTemplate.category.in_([category, None])),
        )
    )
    rows = list(result.all())
    return random.choice(rows) if rows else None


async def list_templates(session: AsyncSession) -> Sequence[DraftTemplate]:
    result = await session.scalars(select(DraftTemplate).order_by(DraftTemplate.id))
    return result.all()


async def add_template(session: AsyncSession, geo: str | None, category: str | None, text: str) -> DraftTemplate:
    template = DraftTemplate(geo=geo, category=category, template_text=text)
    session.add(template)
    await session.commit()
    await session.refresh(template)
    return template


async def disable_template(session: AsyncSession, template_id: int) -> bool:
    template = await session.get(DraftTemplate, template_id)
    if not template:
        return False
    template.is_active = False
    await session.commit()
    return True


async def increment_ai_failure(session: AsyncSession) -> None:
    await increment_stat(session, "ai_failures", 1)


async def create_lead(
    session: AsyncSession,
    *,
    tg_user_id: int | None,
    tg_username: str | None,
    first_name: str | None,
    source_post_id: int | None,
    geo: str | None,
    intent: str | None,
    notes: str | None = None,
) -> Lead:
    lead = Lead(
        tg_user_id=tg_user_id,
        tg_username=tg_username,
        first_name=first_name,
        source_post_id=source_post_id,
        geo=geo,
        intent=intent,
        notes=notes,
    )
    session.add(lead)
    await increment_stat(session, "leads_received", 1)
    await session.refresh(lead)
    return lead


async def list_new_leads(session: AsyncSession, limit: int = 20) -> Sequence[Lead]:
    result = await session.scalars(select(Lead).where(Lead.status == "new").order_by(Lead.created_at.desc()).limit(limit))
    return result.all()


async def update_lead_status(session: AsyncSession, lead_id: int, status: str) -> bool:
    lead = await session.get(Lead, lead_id)
    if not lead:
        return False
    lead.status = status
    await session.commit()
    return True


async def close_deal(session: AsyncSession, lead_id: int, amount: Decimal) -> bool:
    lead = await session.get(Lead, lead_id)
    if not lead:
        return False
    lead.status = "converted"
    lead.deal_amount = amount
    await increment_stat(session, "deals_closed", 1)
    await increment_stat(session, "revenue", amount * Decimal("0.40"))
    return True
