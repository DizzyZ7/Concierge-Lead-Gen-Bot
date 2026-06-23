from __future__ import annotations

from decimal import Decimal
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from db import queries
from db.models import Lead

DealWriteResult = Literal["created", "updated", "unchanged", "missing"]


async def record_deal_revenue(
    session: AsyncSession,
    *,
    lead_id: int,
    revenue: Decimal,
) -> DealWriteResult:
    """Store actual revenue/commission and keep today metrics idempotent."""
    lead = await session.get(Lead, lead_id)
    if not lead:
        return "missing"

    previous_revenue = lead.deal_amount or Decimal("0")
    was_converted = lead.status == "converted"
    lead.status = "converted"
    lead.deal_amount = revenue

    if not was_converted:
        await queries.increment_stat(session, "deals_closed", 1)
        await queries.increment_stat(session, "revenue", revenue)
        return "created"

    delta = revenue - previous_revenue
    if delta == 0:
        await session.commit()
        return "unchanged"

    await queries.increment_stat(session, "revenue", delta)
    return "updated"
