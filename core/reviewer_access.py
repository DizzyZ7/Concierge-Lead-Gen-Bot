from __future__ import annotations

import os
from typing import Final

from dotenv import dotenv_values

from core.config import Settings

REVIEWER_USER_IDS_ENV: Final = "REVIEWER_USER_IDS"


def configured_reviewer_user_ids_raw() -> str | None:
    """Read explicit reviewer users from container env or the local .env file."""
    value = os.getenv(REVIEWER_USER_IDS_ENV)
    if value is not None:
        return value
    dotenv_value = dotenv_values(".env").get(REVIEWER_USER_IDS_ENV)
    return str(dotenv_value) if dotenv_value is not None else None


def parse_reviewer_user_ids(value: str | None) -> set[int]:
    """Parse a comma-separated list of positive Telegram user IDs."""
    if value is None or not value.strip():
        return set()
    parts = [item.strip() for item in value.split(",") if item.strip()]
    if not parts or not all(item.isdigit() and int(item) > 0 for item in parts):
        raise ValueError("REVIEWER_USER_IDS must be a comma-separated list of positive Telegram user IDs")
    return {int(item) for item in parts}


def reviewer_user_ids(settings: Settings) -> set[int]:
    """Return humans allowed to use reviewer actions.

    Explicit REVIEWER_USER_IDS is required for group delivery chats. For backwards
    compatibility, positive reviewer chat IDs are treated as user IDs when the
    explicit variable is omitted; negative group/channel IDs are never authorized.
    """
    explicit = parse_reviewer_user_ids(configured_reviewer_user_ids_raw())
    if explicit:
        return explicit
    return {chat_id for chat_id in settings.reviewer_chat_ids if chat_id > 0}


def allowed_operator_ids(settings: Settings) -> set[int]:
    """Return all owners and authorized reviewers."""
    return settings.admin_ids | reviewer_user_ids(settings)
