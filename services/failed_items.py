from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db import queries


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
    reason = f"Ошибка обработки: {error.__class__.__name__}"[:400]
    existing = await queries.get_post_with_details(session, tg_message_id)
    if existing and existing.channel_id == channel_id:
        existing.status = "processing_failed"
        existing.relevance_reason = reason
        existing.content_summary = "Пост не обработан автоматически и требует повторного запуска."
        existing.suggested_angle = None
        await session.commit()
        return

    if await queries.post_exists(session, channel_id, tg_message_id):
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
