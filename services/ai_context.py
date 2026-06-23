from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from db import queries

BUSINESS_CONTEXT_KEY = "business_context"
BUSINESS_CONTEXT_LIMIT = 2500


async def get_business_context(session: AsyncSession | None) -> str:
    if session is None:
        return ""
    value = await queries.get_setting(session, BUSINESS_CONTEXT_KEY, "")
    return " ".join((value or "").split())[:BUSINESS_CONTEXT_LIMIT]


def business_context_prompt(value: str) -> str:
    if not value:
        return "Business context: not configured. Keep the response useful and do not assume a specific offer."
    return f"Business context: {value}"
