from __future__ import annotations

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import reviewer_actions
from core.config import Settings
from core.logger import get_logger
from db import queries
from services.reviewer_cards import render_reviewer_card
from services.runtime_ops import RuntimeOps

log = get_logger(__name__)


class ReviewerDispatcher:
    """Sends approved drafts to configured human reviewers."""

    def __init__(
        self,
        *,
        bot: Bot,
        session_factory: async_sessionmaker[AsyncSession],
        settings: Settings,
        runtime_ops: RuntimeOps | None = None,
    ) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.settings = settings
        self.runtime_ops = runtime_ops

    async def run_once(self) -> None:
        try:
            async with self.session_factory() as session:
                if await queries.is_paused(session):
                    if self.runtime_ops:
                        await self.runtime_ops.heartbeat("reviewer", "paused")
                    return
                drafts = await queries.due_review_drafts(session, 10)
                reviewers = sorted(self.settings.reviewer_chat_ids)
                if not reviewers:
                    if self.runtime_ops:
                        await self.runtime_ops.failure("reviewer", RuntimeError("Не настроены REVIEWER_CHAT_IDS"))
                    return
                delivered = 0
                for draft in drafts:
                    post = draft.post
                    reviewer_id = reviewers[draft.id % len(reviewers)]
                    text = render_reviewer_card(
                        draft_id=draft.id,
                        post_id=post.id,
                        channel=post.channel.channel_username,
                        url=post.post_url,
                        source_text=post.post_text,
                        draft_text=draft.draft_text,
                        score=post.relevance_score,
                        intent=post.intent,
                        reason=post.relevance_reason,
                        summary=post.content_summary,
                        angle=post.suggested_angle,
                    )
                    try:
                        sent = await self.bot.send_message(
                            reviewer_id,
                            text,
                            reply_markup=reviewer_actions(post.id, post.post_url),
                            disable_web_page_preview=True,
                        )
                    except Exception as error:
                        log.warning("reviewer_send_failed", reviewer_id=reviewer_id, draft_id=draft.id, error=str(error))
                        if self.runtime_ops:
                            await self.runtime_ops.failure("reviewer", error, f"Не отправлен черновик #{draft.id} в чат {reviewer_id}")
                        continue
                    await queries.mark_draft_sent(session, draft.id, reviewer_id, sent.message_id)
                    delivered += 1
            if self.runtime_ops:
                await self.runtime_ops.heartbeat("reviewer", f"due={len(drafts)} delivered={delivered}")
        except Exception as error:
            if self.runtime_ops:
                await self.runtime_ops.failure("reviewer", error, "Ошибка цикла отправки reviewer-у")
            else:
                log.warning("reviewer_dispatcher_failed", error=str(error))
