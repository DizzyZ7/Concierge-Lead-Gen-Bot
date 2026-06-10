from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings


class AIService:
    """Thin AI service interface. Full local version is in the release ZIP."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def score_post(self, post_text: str, geo: str) -> dict[str, Any]:
        return {"score": 0.5, "intent": "unknown"}

    async def generate_draft(self, post_text: str, geo: str, intent: str, db_session: AsyncSession) -> tuple[str, str]:
        return "Подготовлен черновик для ручной проверки.", "hardcoded"
