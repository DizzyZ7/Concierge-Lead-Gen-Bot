from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from db import queries
from db.models import Lead
from services.contact_candidates import contact_candidates_note
from services.post_state import can_mark_as_lead


def initial_lead_notes(post_id: int, source_text: str | None) -> str:
    """Build neutral lead notes without treating public handles as verified contacts."""
    base = (
        f"Лид из Lead Radar, источник #{post_id}. "
        "Контактные данные нужно заполнить после прямого ответа."
    )
    contacts = contact_candidates_note(source_text)
    return f"{base}\n{contacts}" if contacts else base


async def mark_post_as_lead(session: AsyncSession, post_id: int) -> tuple[str, int | None]:
    """Create one CRM lead for a source post and keep the operation idempotent.

    Returns one of: ``updated``, ``already``, ``blocked`` or ``missing`` together
    with the lead ID when it is known.
    """
    post = await queries.get_post_with_details(session, post_id)
    if not post:
        return "missing", None

    existing = await session.scalar(select(Lead).where(Lead.source_post_id == post_id).limit(1))
    if existing:
        if post.status != "lead":
            post.status = "lead"
            await session.commit()
            return "updated", existing.id
        return "already", existing.id

    if not can_mark_as_lead(post.status):
        return "blocked", None

    lead = Lead(
        source_post_id=post.id,
        geo=post.channel.geo if post.channel else None,
        intent=post.intent,
        notes=initial_lead_notes(post.id, post.post_text),
    )
    session.add(lead)
    post.status = "lead"
    try:
        await session.flush()
    except IntegrityError:
        await session.rollback()
        existing = await session.scalar(select(Lead).where(Lead.source_post_id == post_id).limit(1))
        return ("already", existing.id) if existing else ("missing", None)

    await queries.increment_stat(session, "leads_received", 1)
    await session.refresh(lead)
    return "updated", lead.id
