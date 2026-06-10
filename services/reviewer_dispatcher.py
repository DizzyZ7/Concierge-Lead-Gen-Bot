from __future__ import annotations

from html import escape

from aiogram import Bot
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import reviewer_actions
from core.config import Settings
from core.logger import get_logger
from db import queries

log = get_logger(__name__)


def trim(value: str | None, limit: int) -> str:
    text = value or ""
    return text if len(text) <= limit else text[: limit - 1] + "..."


class ReviewerDispatcher:
    """Sends approved drafts to configured human reviewers."""

    def __init__(self, *, bot: Bot, session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> None:
        self.bot = bot
        self.session_factory = session_factory
        self.settings = settings

    async def run_once(self) -> None:
        async with self.session_factory() as session:
            if await queries.is_paused(session):
                return
            drafts = await queries.due_review_drafts(session, 10)
            reviewers = sorted(self.settings.reviewer_chat_ids)
            if not reviewers:
                return
            for draft in drafts:
                post = draft.post
                reviewer_id = reviewers[draft.id % len(reviewers)]
                text = self._render_card(draft.id, post.id, post.channel.channel_username, post.post_url, post.post_text, draft.draft_text)
                try:
                    sent = await self.bot.send_message(
                        reviewer_id,
                        text,
                        reply_markup=reviewer_actions(post.id, post.post_url),
                        disable_web_page_preview=True,
                    )
                except Exception as error:
                    log.warning("reviewer_send_failed", reviewer_id=reviewer_id, draft_id=draft.id, error=str(error))
                    continue
                await queries.mark_draft_sent(session, draft.id, reviewer_id, sent.message_id)

    @staticmethod
    def _render_card(
        draft_id: int,
        post_id: int,
        channel: str,
        url: str | None,
        source_text: str | None,
        draft_text: str,
    ) -> str:
        source = trim(source_text, 900)
        draft = trim(draft_text, 1800)
        return (
            f"Review draft #{draft_id} for item #{post_id}\n"
            f"Channel: {escape(channel)}\n"
            f"URL: {escape(url or '-')}\n\n"
            f"Source:\n{escape(source)}\n\n"
            f"Draft to check and send manually:\n<code>{escape(draft)}</code>"
        )
