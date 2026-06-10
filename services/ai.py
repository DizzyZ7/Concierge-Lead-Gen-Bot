from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from db import queries

KEYWORDS: dict[str, tuple[str, ...]] = {
    "relocation": ("переезд", "релокация", "переехать", "relocation", "relocate"),
    "realty": ("жилье", "аренда", "квартира", "вилла", "condo", "real estate", "rent"),
    "visa": ("виза", "визаран", "work permit", "permit", "внж"),
    "tourism": ("тур", "экскурсия", "отдых", "маршрут", "trip"),
    "investment": ("инвестиции", "купить", "доходность", "investment"),
}

DRAFTS: dict[str, str] = {
    "thailand": "По Таиланду лучше заранее проверить район, документы и условия аренды. Если нужно быстро сориентироваться по шагам, можно написать в личку 🙏",
    "bali": "На Бали много нюансов с районами, визами и долгой арендой. Если хотите, можно написать в личку, подскажу, на что смотреть 🌴",
    "vietnam": "По Вьетнаму важно заранее проверить район, визу и условия проживания. Если есть вопросы, можно написать в личку, подскажу 🇻🇳",
    "default": "По переезду и жилью в ЮВА есть много нюансов. Если нужно, можно написать в личку, помогу сориентироваться 👋",
}


class AIService:
    """Safe reviewer-first draft service.

    This repository version works without external AI calls. The fuller Claude wrapper can be plugged in later through the same methods.
    """

    def __init__(self, settings: Settings) -> None:
        self.settings = settings

    async def score_post(self, post_text: str, geo: str) -> dict[str, Any]:
        text = post_text.lower()
        best_intent = "unknown"
        hits = 0
        for intent, words in KEYWORDS.items():
            current_hits = sum(1 for word in words if word.lower() in text)
            if current_hits > hits:
                hits = current_hits
                best_intent = intent
        geo_bonus = 1 if geo.lower() in text else 0
        score = min(0.95, 0.5 + hits * 0.12 + geo_bonus * 0.08)
        return {"score": score, "intent": best_intent}

    async def generate_draft(self, post_text: str, geo: str, intent: str, db_session: AsyncSession) -> tuple[str, str]:
        template = await queries.get_random_template(db_session, geo, intent)
        if template:
            return template.template_text, "template"
        return DRAFTS.get(geo, DRAFTS["default"]), "hardcoded"
