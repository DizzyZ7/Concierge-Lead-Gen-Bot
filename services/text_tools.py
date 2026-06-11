from __future__ import annotations

import hashlib
import re

SPACE_RE = re.compile(r"\s+")
URL_RE = re.compile(r"https?://\S+|t\.me/\S+", re.IGNORECASE)
PUNCT_RE = re.compile(r"[^\w\sа-яА-ЯёЁ]", re.UNICODE)


def normalize_text(value: str | None) -> str:
    text = value or ""
    text = URL_RE.sub(" ", text)
    text = PUNCT_RE.sub(" ", text.lower())
    text = SPACE_RE.sub(" ", text).strip()
    return text


def text_hash(value: str | None) -> str:
    normalized = normalize_text(value)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()
