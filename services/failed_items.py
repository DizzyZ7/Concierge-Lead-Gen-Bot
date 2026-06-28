from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.logger import get_logger
from db import queries
from db.models import ParsedPost

log = get_logger(__name__)


async def mark_processing_failed(
    session: AsyncSession,
    *,
    channel_id: int,
    tg_message_id: int,
    post_text: str,
    post_url: str | None,
    text_hash: str | None,
    error: Exception,
) -> None:
    try:
        await session.rollback()
    except Exception as rollback_error:
        log.warning("processing_failed_rollback_failed", error=str(rollback_error))

    reason = f"Ошибка обработки: {error.__class__.__name__}"[:400]
    existing = await session.scalar(
        select(ParsedPost).where(
            ParsedPost.channel_id == channel_id,
            ParsedPost.tg_message_id == tg_message_id,
        )
    )
    if existing:
        existing.status = "processing_failed"
        existing.relevance_reason = reason
        existing.content_summary = "Пост не обработан автоматически и требует повторного запуска."
        existing.suggested_angle = None
        await session.commit()
        return

    await queries.create_post(
        session,
        channel_id=channel_id,
        tg_message_id=tg_message_id,
        post_text=post_text,
        post_url=post_url,
        score=0.0,
        intent="unknown",
        status="processing_failed",
        relevance_reason=reason,
        content_summary="Пост не обработан автоматически и требует повторного запуска.",
        suggested_angle=None,
        text_hash=text_hash,
    )
