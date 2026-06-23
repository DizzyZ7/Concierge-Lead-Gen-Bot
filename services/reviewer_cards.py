from __future__ import annotations

from html import escape

from bot.presentation import intent_label


def trim(value: str | None, limit: int) -> str:
    text = value or ""
    return text if len(text) <= limit else text[: limit - 1] + "..."


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
    source = trim(source_text, 800)
    draft = trim(draft_text, 1600)
    score_text = f"{score:.2f}" if score is not None else "-"
    reason_text = trim(reason, 300) or "Пост отмечен как потенциально полезный."
    summary_text = trim(summary, 350) or "Краткое резюме не сформировано."
    angle_text = trim(angle, 350) or "Можно аккуратно зайти с полезным уточнением или советом."
    return (
        f"Лид-радар: пост #{post_id}\n"
        f"Черновик #{draft_id}\n"
        f"Канал: {escape(channel)}\n"
        f"Категория: {escape(intent_label(intent))}\n"
        f"Оценка: {escape(score_text)}\n"
        f"Почему релевантно: {escape(reason_text)}\n"
        f"Кратко: {escape(summary_text)}\n"
        f"Как зайти в диалог: {escape(angle_text)}\n"
        f"Ссылка: {escape(url or '-')}\n\n"
        f"Текст источника:\n{escape(source)}\n\n"
        f"Черновик комментария:\n<code>{escape(draft)}</code>"
    )
