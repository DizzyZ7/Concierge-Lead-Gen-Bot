from __future__ import annotations

INTENT_LABELS = {
    "relocation": "Переезд",
    "realty": "Недвижимость",
    "visa": "Визы",
    "tourism": "Туризм",
    "investment": "Инвестиции",
    "business": "Бизнес",
    "finance": "Финансы",
    "expat_life": "Жизнь экспатов",
    "manual": "Добавлено вручную",
    "unknown": "Не определено",
}

STATUS_LABELS = {
    "pending": "На ручной проверке",
    "approved": "Одобрено",
    "queued_by_limit": "Отложено по дневному лимиту",
    "sent_to_reviewer": "Отправлено reviewer-у",
    "saved": "Сохранено",
    "content_idea": "Идея для контента",
    "commented": "Комментарий написан",
    "lead": "Лид",
    "not_relevant": "Нерелевантно",
    "reviewer_done": "Обработано",
    "processing_failed": "Ошибка обработки",
    "skipped": "Пропущено",
    "new": "Новый",
    "contacted": "В работе",
    "converted": "Сделка",
    "dead": "Неактуально",
}


def intent_label(value: str | None) -> str:
    return INTENT_LABELS.get((value or "unknown").lower(), value or INTENT_LABELS["unknown"])


def status_label(value: str | None) -> str:
    return STATUS_LABELS.get((value or "unknown").lower(), value or INTENT_LABELS["unknown"])
