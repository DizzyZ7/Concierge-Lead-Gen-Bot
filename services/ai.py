from __future__ import annotations

import json
import random
from typing import Any

from anthropic import AsyncAnthropic
from sqlalchemy.ext.asyncio import AsyncSession

from core.config import Settings
from core.logger import get_logger
from db import queries

log = get_logger(__name__)

KEYWORDS: dict[str, tuple[str, ...]] = {
    "relocation": ("переезд", "релокация", "переехать", "relocation", "relocate"),
    "realty": ("жилье", "аренда", "квартира", "вилла", "condo", "real estate", "rent"),
    "visa": ("виза", "визаран", "work permit", "permit", "внж"),
    "tourism": ("тур", "экскурсия", "отдых", "маршрут", "trip"),
    "investment": ("инвестиции", "купить", "доходность", "investment", "инвестор"),
    "business": ("бизнес", "предприниматель", "компания", "партнерство", "franchise", "стартап"),
    "finance": ("финансы", "деньги", "налоги", "банк", "платеж", "валюта", "доход"),
    "expat_life": ("экспат", "жизнь в таиланде", "местные", "быт", "комьюнити"),
}

COMMENT_STYLES = (
    "коротко, по-человечески, без продаж, с одним уточняющим вопросом",
    "дружелюбно и экспертно, как человек с опытом по Таиланду",
    "мягкий заход: сначала полезная мысль, потом аккуратное предложение помочь",
    "лаконичный комментарий без эмодзи и без рекламного тона",
    "живой разговорный стиль, но без фамильярности и давления",
)

DRAFTS: dict[str, str] = {
    "thailand": "По Таиланду лучше заранее проверить район, документы и условия аренды. Если нужно быстро сориентироваться по шагам, можно написать в личку 🙏",
    "bali": "На Бали много нюансов с районами, визами и долгой арендой. Если хотите, можно написать в личку, подскажу, на что смотреть 🌴",
    "vietnam": "По Вьетнаму важно заранее проверить район, визу и условия проживания. Если есть вопросы, можно написать в личку, подскажу 🇻🇳",
    "default": "По переезду и жилью в ЮВА есть много нюансов. Если нужно, можно написать в личку, помогу сориентироваться 👋",
}


class AIService:
    """Reviewer-first AI service. Uses Claude when configured, otherwise falls back to local rules."""

    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key) if settings.claude_ready else None

    async def score_post(self, post_text: str, geo: str) -> dict[str, Any]:
        """Score source text relevance for the concierge workflow."""
        if self.client:
            try:
                prompt = (
                    "Return compact JSON only with fields: score, intent, reason, summary, angle. "
                    "score must be 0..1. "
                    "intent must be exactly one of: relocation, realty, visa, tourism, investment, business, finance, expat_life, unknown. "
                    "Relevant topics: Thailand relocation, housing, visa, real estate, tourism, investment, business, finance, expat life. "
                    "reason: one short Russian sentence explaining why this item matters. "
                    "summary: one short Russian sentence summarizing the source item. "
                    "angle: one short Russian sentence suggesting how a human reviewer can enter the conversation naturally. "
                    f"Geo: {geo}. Text: {post_text[:3500]}"
                )
                raw = await self._claude(prompt, 320, temperature=0.35)
                parsed = self._parse_json(raw)
                return {
                    "score": max(0.0, min(float(parsed.get("score", 0.5)), 1.0)),
                    "intent": str(parsed.get("intent", "unknown")).lower(),
                    "reason": str(parsed.get("reason", "Пост может быть полезен для ручной проверки.")),
                    "summary": str(parsed.get("summary", "Краткое резюме не сформировано.")),
                    "angle": str(parsed.get("angle", "Можно аккуратно зайти с полезным уточнением или советом.")),
                }
            except Exception as error:
                log.warning("claude_score_failed", error=str(error))
        return self._fallback_score(post_text, geo)

    async def generate_draft(self, post_text: str, geo: str, intent: str, db_session: AsyncSession) -> tuple[str, str]:
        """Generate a short draft for a human reviewer."""
        if self.client:
            try:
                style = random.choice(COMMENT_STYLES)
                prompt = (
                    "Prepare one natural Russian reply draft for a human reviewer. "
                    "The reviewer will decide manually whether to send it. "
                    "Do not sound like an advertisement, a bot, or a sales script. "
                    "Do not repeat the same structure every time. "
                    "Max 3 short sentences. "
                    f"Style: {style}. Geo: {geo}. Intent: {intent}. Text: {post_text[:3500]}"
                )
                text = (await self._claude(prompt, 300, temperature=0.65)).strip().strip('"')
                if len(text) >= 10:
                    return text, "ai"
            except Exception as error:
                log.warning("claude_draft_failed", error=str(error))
                await queries.increment_ai_failure(db_session)
        template = await queries.get_random_template(db_session, geo, intent)
        if template:
            return template.template_text, "template"
        return DRAFTS.get(geo, DRAFTS["default"]), "hardcoded"

    async def _claude(self, user_prompt: str, max_tokens: int, temperature: float = 0.4) -> str:
        if not self.client:
            raise RuntimeError("Claude client is not configured")
        message = await self.client.messages.create(
            model=self.settings.anthropic_model,
            max_tokens=max_tokens,
            temperature=temperature,
            messages=[{"role": "user", "content": user_prompt}],
        )
        chunks: list[str] = []
        for block in message.content:
            if getattr(block, "type", None) == "text":
                chunks.append(block.text)
        return "\n".join(chunks).strip()

    @staticmethod
    def _parse_json(raw: str) -> dict[str, Any]:
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            start = raw.find("{")
            end = raw.rfind("}")
            if start >= 0 and end > start:
                return json.loads(raw[start : end + 1])
            return {
                "score": 0.5,
                "intent": "unknown",
                "reason": "Пост требует ручной проверки.",
                "summary": "Краткое резюме не сформировано.",
                "angle": "Можно аккуратно зайти с полезным уточнением или советом.",
            }

    @staticmethod
    def _fallback_score(post_text: str, geo: str) -> dict[str, Any]:
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
        reason = "Есть совпадения с приоритетными темами источника." if hits else "Пост сохранен для ручной проверки."
        summary = "Пост связан с потенциальным вопросом по выбранной тематике." if hits else "Пост требует ручной оценки."
        angle = "Можно зайти с практическим советом и уточняющим вопросом." if hits else "Лучше проверить вручную перед реакцией."
        return {"score": score, "intent": best_intent, "reason": reason, "summary": summary, "angle": angle}
