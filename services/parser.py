from __future__ import annotations

from telethon import TelegramClient
from telethon.errors import FloodWaitError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.logger import get_logger
from db import queries
from services.ai import AIService
from services.text_tools import text_hash

log = get_logger(__name__)


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
    ) -> None:
        try:
            entity = await self.client.get_entity(username)
            async for message in self.client.iter_messages(entity, limit=self.settings.parser_limit_per_channel):
                text = message.message or ""
                if not text.strip():
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
                intent = str(score.get("intent", "unknown"))
                reason = str(score.get("reason", "Пост требует ручной проверки."))
                summary = str(score.get("summary", "Краткое резюме не сформировано."))
                angle = str(score.get("angle", "Можно аккуратно зайти с полезным уточнением или советом."))
                status = "pending" if value < self.settings.relevance_threshold else "approved"
                post_url = f"https://t.me/{username.lstrip('@')}/{message_id}"
                post = await queries.create_post(
                    session,
                    channel_id=channel_id,
                    tg_message_id=message_id,
                    post_text=text,
                    post_url=post_url,
                    score=value,
                    intent=intent,
                    status="pending",
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
                        delay_min=delay_min,
                        delay_max=delay_max,
                    )
                else:
                    log.info("post_saved_for_manual_review", channel=username, post_id=post.id, score=value, intent=intent)
        except FloodWaitError as error:
            log.warning("parser_flood_wait", channel=username, seconds=error.seconds)
        except Exception as error:
            log.warning("parser_channel_failed", channel=username, error=str(error))
