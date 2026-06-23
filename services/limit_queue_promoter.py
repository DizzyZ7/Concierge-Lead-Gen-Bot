from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from core.config import Settings
from core.logger import get_logger
from db import queries
from db.models import ParsedPost, TargetChannel
from services.ai import AIService
from services.failed_items import mark_processing_failed
from services.parser import count_channel_drafts_since, current_day_start_utc
from services.runtime_ops import RuntimeOps

log = get_logger(__name__)

PROMOTION_LOOKAHEAD_MULTIPLIER = 5


@dataclass(frozen=True)
class PromotionResult:
    promoted: int
    queued: int
    paused: bool = False


def available_daily_capacity(daily_limit: int, drafts_today: int) -> int:
    return max(0, max(daily_limit, 0) - max(drafts_today, 0))


def promotion_fetch_limit(capacity: int) -> int:
    return max(capacity, 1) * PROMOTION_LOOKAHEAD_MULTIPLIER


class LimitQueuePromoter:
    """Promotes quality posts held by a channel daily cap when new capacity is available."""

    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        ai_service: AIService,
        settings: Settings,
        runtime_ops: RuntimeOps | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.ai_service = ai_service
        self.settings = settings
        self.runtime_ops = runtime_ops

    async def run_once(self) -> PromotionResult | None:
        try:
            async with self.session_factory() as session:
                if await queries.is_paused(session):
                    if self.runtime_ops:
                        await self.runtime_ops.heartbeat("limit_queue", "paused")
                    return PromotionResult(promoted=0, queued=0, paused=True)

                day_start = current_day_start_utc(self.settings.timezone)
                channels = await queries.list_active_channels(session)
                promoted_total = 0
                queued_total = 0
                for channel in channels:
                    promoted, queued = await self._promote_channel(session, channel, day_start)
                    promoted_total += promoted
                    queued_total += queued

            if self.runtime_ops:
                await self.runtime_ops.heartbeat(
                    "limit_queue",
                    f"active_channels={len(channels)} promoted={promoted_total} queued={queued_total}",
                )
            return PromotionResult(promoted=promoted_total, queued=queued_total)
        except Exception as error:
            if self.runtime_ops:
                await self.runtime_ops.failure("limit_queue", error, "Ошибка продвижения очереди дневных лимитов")
            else:
                log.warning("limit_queue_promoter_failed", error=str(error))
            return None

    async def _promote_channel(
        self,
        session: AsyncSession,
        channel: TargetChannel,
        day_start: datetime,
    ) -> tuple[int, int]:
        drafts_today = await count_channel_drafts_since(session, channel.id, day_start)
        capacity = available_daily_capacity(channel.daily_draft_limit, drafts_today)

        queued_posts = await session.scalars(
            select(ParsedPost)
            .options(selectinload(ParsedPost.channel), selectinload(ParsedPost.draft))
            .where(ParsedPost.channel_id == channel.id, ParsedPost.status == "queued_by_limit")
            .order_by(ParsedPost.relevance_score.desc(), ParsedPost.created_at.asc())
            .limit(promotion_fetch_limit(capacity))
        )
        posts = list(queued_posts.all())
        if not posts or capacity == 0:
            return 0, len(posts)

        promoted = 0
        for post in posts[:capacity]:
            if post.draft is not None or post.status != "queued_by_limit":
                continue
            try:
                draft_text, source = await self.ai_service.generate_draft(
                    post.post_text or "",
                    channel.geo,
                    post.intent,
                    session,
                )
                approved = await queries.approve_post(
                    session,
                    post_id=post.id,
                    draft_text=draft_text,
                    source=source,
                    delay_min=channel.review_delay_min,
                    delay_max=channel.review_delay_max,
                )
                if not approved:
                    continue
                promoted += 1
                if source == "ai":
                    await queries.increment_stat(session, "ai_drafts", 1)
                else:
                    await queries.increment_stat(session, "template_drafts", 1)
                log.info(
                    "limit_queue_post_promoted",
                    channel=channel.channel_username,
                    post_id=post.id,
                    score=post.relevance_score,
                    remaining_capacity=capacity - promoted,
                )
            except Exception as error:
                log.warning(
                    "limit_queue_promotion_failed",
                    channel=channel.channel_username,
                    post_id=post.id,
                    error=str(error),
                )
                await mark_processing_failed(
                    session,
                    channel_id=channel.id,
                    tg_message_id=post.tg_message_id,
                    post_text=post.post_text or "",
                    post_url=post.post_url,
                    text_hash=post.text_hash,
                    error=error,
                )
                if self.runtime_ops:
                    await self.runtime_ops.failure(
                        "limit_queue",
                        error,
                        f"Не удалось продвинуть пост #{post.id} из {channel.channel_username}",
                    )

        remaining = max(0, len(posts) - promoted)
        return promoted, remaining
