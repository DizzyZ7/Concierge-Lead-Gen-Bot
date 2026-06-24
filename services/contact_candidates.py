from __future__ import annotations

import re

MAX_CONTACT_CANDIDATES = 5

HANDLE_PATTERN = re.compile(r"(?<![\w@])@([A-Za-z][A-Za-z0-9_]{4,31})\b")
TME_PATTERN = re.compile(
    r"(?:https?://)?(?:www\.)?t\.me/(?:s/)?([A-Za-z][A-Za-z0-9_]{4,31})(?![\w/])",
    re.IGNORECASE,
)


def extract_public_telegram_handles(text: str | None, limit: int = MAX_CONTACT_CANDIDATES) -> tuple[str, ...]:
    """Return unique public Telegram handle candidates mentioned in source text.

    Results are only hints for manual verification. Private invite links and phone
    numbers are deliberately ignored.
    """
    if not text or limit < 1:
        return ()
    seen: set[str] = set()
    result: list[str] = []
    for match in (*HANDLE_PATTERN.finditer(text), *TME_PATTERN.finditer(text)):
        handle = f"@{match.group(1).lower()}"
        if handle in seen:
            continue
        seen.add(handle)
        result.append(handle)
        if len(result) >= limit:
            break
    return tuple(result)


def contact_candidates_note(text: str | None) -> str | None:
    handles = extract_public_telegram_handles(text)
    if not handles:
        return None
    return "Публичные Telegram-упоминания из текста: " + ", ".join(handles) + ". Проверь владельца перед контактом."
