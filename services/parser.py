from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import func, select
from telethon import TelegramClient
from telethon.errors import FloodWaitError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.logger import get_logger
from db import queries
from db.models import ParsedPost, ReviewDraft
from services.ai import AIService
from services.text_tools import text_hash

log = get_logger(__name__)


def split_csv(value: str | None) -> set[str]:
    if not value:
        return set()
    return {part.strip().lower() for part in value.split(",") if part.strip()}


def has_blocked_keyword(text: str, blocked_keywords: str | None) -> bool:
    words = split_csv(blocked_keywords)
    lowered = text.lower()
    return any(word in lowered for word in words)


def to_float(value: Decimal | float | int | None, default: float) -> float:
    if value is None:
        return default
    return float(value)


def is_stale(message_date: datetime | None, max_age_hours: int) -> bool:
    if message_date is None:
        return False
    published_at = message_date if message_date.tzinfo else message_date.replace(tzinfo=timezone.utc)
    return datetime.now(timezone.utc) - published_at > timedelta(hours=max_age_hours)


def current_day_start_utc(timezone_name: str) -> datetime:
    try:
        local_zone = ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        local_zone = timezone.utc
    local_now = datetime.now(local_zone)
    return local_now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc)


async def count_channel_drafts_since(session: AsyncSession, channel_id: int, window_start: datetime) -> int:
    value = await session.scalar(
        select(func.count(ReviewDraft.id))
        .join(ReviewDraft.post)
        .where(ParsedPost.channel_id == channel_id, ReviewDraft.created_at >= window_start)
    )
    return int(value or 0)


class ParserService:
    """Read-only Telegram channel monitor that creates reviewer drafts for relevant posts."""

    def __init__(
        self,
        *,
        client: TelegramClient,
        session_factory: async_sessionmaker[AsyncSession],
        ai_service: AIService,
        settings: Settings,
    ) -> None:
        self.client = client
        self.session_factory = session_factory
        self.ai_service = ai_service
        self.settings = settings

    async def run_once(self) -> None:
        """Check active channels and route relevant posts to reviewer workflow."""
        day_start = current_day_start_utc(self.settings.timezone)
        async with self.session_factory() as session:
            if await queries.is_paused(session):
                return
            channels = await queries.list_active_channels(session)
            for channel in channels:
                await self._scan_channel(
                    session,
                    channel_id=channel.id,
                    username=channel.channel_username,
                    geo=channel.geo,
                    delay_min=channel.review_delay_min,
                    delay_max=channel.review_delay_max,
                    daily_draft_limit=channel.daily_draft_limit,
                    min_score=to_float(channel.min_score, self.settings.relevance_threshold),
                    allowed_intents=channel.allowed_intents,
                    blocked_keywords=channel.blocked_keywords,
                    max_post_age_hours=getattr(self.settings, "parser_max_post_age_hours", 24),
                    day_start=day_start,
                )

    async def _scan_channel(
        self,
        session: AsyncSession,
        *,
        channel_id: int,
        username: str,
        geo: str,
        delay_min: int,
        delay_max: int,
        daily_draft_limit: int,
        min_score: float,
        allowed_intents: str | None,
        blocked_keywords: str | None,
        max_post_age_hours: int,
        day_start: datetime,
    ) -> None:
        allowed = split_csv(allowed_intents)
        drafts_today = await count_channel_drafts_since(session, channel_id, day_start)
        limit = max(daily_draft_limit, 0)
        try:
            entity = await self.client.get_entity(username)
            async for message in self.client.iter_messages(entity, limit=self.settings.parser_limit_per_channel):
                text = message.message or ""
                if not text.strip():
                    continue
                if is_stale(getattr(message, "date", None), max_post_age_hours):
                    log.info("stale_post_skipped", channel=username, message_id=int(message.id), max_age_hours=max_post_age_hours)
                    continue
                if has_blocked_keyword(text, blocked_keywords):
                    log.info("blocked_keyword_post_skipped", channel=username, message_id=int(message.id))
                    continue
                message_id = int(message.id)
                if await queries.post_exists(session, channel_id, message_id):
                    continue
                hash_value = text_hash(text)
                if await queries.text_hash_exists(session, hash_value):
                    log.info("duplicate_post_skipped", channel=username, message_id=message_id)
                    continue
                score = await self.ai_service.score_post(text, geo)
                value = float(score.get("score", 0.5))
                intent = str(score.get("intent", "unknown")).lower()
                if allowed and intent not in allowed:
                    log.info("intent_filtered_post_skipped", channel=username, message_id=message_id, intent=intent)
                    continue
                reason = str(score.get("reason", "Пост требует ручной проверки."))
                summary = str(score.get("summary", "Краткое резюме не сформировано."))
                angle = str(score.get("angle", "Можно аккуратно зайти с полезным уточнением или советом."))
                if value < min_score:
                    status = "pending"
                elif drafts_today >= limit:
                    status = "queued_by_limit"
                else:
                    status = "approved"
                post_url = f"https://t.me/{username.lstrip('@')}/{message_id}"
                post = await queries.create_post(
                    session,
                    channel_id=channel_id,
                    tg_message_id=message_id,
                    post_text=text,
                    post_url=post_url,
                    score=value,
                    intent=intent,
                    status=status,
                    relevance_reason=reason,
                    content_summary=summary,
                    suggested_angle=angle,
                    text_hash=hash_value,
                )
                if status == "approved":
                    draft_text, source = await self.ai_service.generate_draft(text, geo, intent, session)
                    await queries.approve_post(
                        session,
                        post_id=post.id,
                        draft_text=draft_text,
                        source=source,
                        delay_min=delay_min,
                        delay_max=delay_max,
                    )
                    drafts_today += 1
                    if source == "ai":
                        await queries.increment_stat(session, "ai_drafts", 1)
                    else:
                        await queries.increment_stat(session, "template_drafts", 1)
                    log.info(
                        "relevant_post_routed",
                        channel=username,
                        post_id=post.id,
                        score=value,
                        intent=intent,
                        min_score=min_score,
                        daily_draft_limit=limit,
                        delay_min=delay_min,
                        delay_max=delay_max,
                    )
                elif status == "queued_by_limit":
                    log.info(
                        "post_queued_by_daily_limit",
                        channel=username,
                        post_id=post.id,
                        score=value,
                        intent=intent,
                        daily_draft_limit=limit,
                    )
                else:
                    log.info(
                        "post_saved_for_manual_review",
                        channel=username,
                        post_id=post.id,
                        score=value,
                        intent=intent,
                        min_score=min_score,
                    )
        except FloodWaitError as error:
            log.warning("parser_flood_wait", channel=username, seconds=error.seconds)
        except Exception as error:
            log.warning("parser_channel_failed", channel=username, error=str(error))
