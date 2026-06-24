from __future__ import annotations

from html import escape

from bot.presentation import intent_label


ELLIPSIS = "..."


def escape_and_trim(value: str | None, limit: int) -> str:
    """Escape text for Telegram HTML and keep the encoded fragment within limit."""
    text = value or ""
    if limit <= 0:
        return ""

    encoded_parts: list[str] = []
    encoded_length = 0
    cutoff = max(0, limit - len(ELLIPSIS))
    truncated = False
    for character in text:
        encoded = escape(character)
        if encoded_length + len(encoded) > cutoff:
            truncated = True
            break
        encoded_parts.append(encoded)
        encoded_length += len(encoded)

    if not truncated:
        return "".join(encoded_parts)
    return "".join(encoded_parts) + ELLIPSIS


def fallback_text(value: str | None, fallback: str) -> str:
    return value if value and value.strip() else fallback


def render_reviewer_card(
    *,
    draft_id: int,
    post_id: int,
    channel: str,
    url: str | None,
    source_text: str | None,
    draft_text: str,
    score: float | None,
    intent: str | None,
    reason: str | None,
    summary: str | None,
    angle: str | None,
) -> str:
    source = escape_and_trim(source_text, 800)
    draft = escape_and_trim(draft_text, 1600)
    score_text = escape_and_trim(f"{score:.2f}" if score is not None else "-", 32)
    reason_text = escape_and_trim(fallback_text(reason, "Пост отмечен как потенциально полезный."), 300)
    summary_text = escape_and_trim(fallback_text(summary, "Краткое резюме не сформировано."), 350)
    angle_text = escape_and_trim(fallback_text(angle, "Можно аккуратно зайти с полезным уточнением или советом."), 350)
    return (
        f"Лид-радар: пост #{post_id}\n"
        f"Черновик #{draft_id}\n"
        f"Канал: {escape_and_trim(channel, 200)}\n"
        f"Категория: {escape_and_trim(intent_label(intent), 100)}\n"
        f"Оценка: {score_text}\n"
        f"Почему релевантно: {reason_text}\n"
        f"Кратко: {summary_text}\n"
        f"Как зайти в диалог: {angle_text}\n"
        f"Ссылка: {escape_and_trim(url or '-', 500)}\n\n"
        f"Текст источника:\n{source}\n\n"
        f"Черновик комментария:\n<code>{draft}</code>"
    )
