from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(..., alias="BOT_TOKEN")
    admin_ids_raw: str = Field(..., alias="ADMIN_IDS")
    reviewer_chat_ids_raw: str | None = Field(None, alias="REVIEWER_CHAT_IDS")
    database_url: str = Field(..., alias="DATABASE_URL")

    timezone: str = Field("Asia/Bangkok", alias="TIMEZONE")
    auto_approve: bool = Field(False, alias="AUTO_APPROVE")
    reviewer_mode: bool = Field(True, alias="REVIEWER_MODE")

    tg_api_id: int | None = Field(None, alias="TG_API_ID")
    tg_api_hash: str | None = Field(None, alias="TG_API_HASH")
    tg_phone: str | None = Field(None, alias="TG_PHONE")
    tg_session_name: str = Field("concierge_session", alias="TG_SESSION_NAME")

    parser_enabled: bool = Field(False, alias="PARSER_ENABLED")
    parser_interval_minutes: int = Field(10, alias="PARSER_INTERVAL_MINUTES")
    parser_limit_per_channel: int = Field(20, alias="PARSER_LIMIT_PER_CHANNEL")
    relevance_threshold: float = Field(0.65, alias="RELEVANCE_THRESHOLD")

    anthropic_api_key: str | None = Field(None, alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-5-haiku-20241022", alias="ANTHROPIC_MODEL")

    @field_validator("tg_api_id", "tg_api_hash", "tg_phone", "anthropic_api_key", mode="before")
    @classmethod
    def empty_optional_to_none(cls, value: Any) -> Any:
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("admin_ids_raw")
    @classmethod
    def validate_admin_ids(cls, value: str) -> str:
        ids = [item.strip() for item in value.split(",") if item.strip()]
        if not ids or not all(item.isdigit() for item in ids):
            raise ValueError("ADMIN_IDS must be a comma-separated list of Telegram numeric IDs")
        return value

    @field_validator("reviewer_chat_ids_raw")
    @classmethod
    def validate_reviewer_chat_ids(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return value
        ids = [item.strip() for item in value.split(",") if item.strip()]
        if not ids or not all(item.lstrip("-").isdigit() for item in ids):
            raise ValueError("REVIEWER_CHAT_IDS must be a comma-separated list of Telegram numeric chat IDs")
        return value

    @property
    def admin_ids(self) -> set[int]:
        """Return configured Telegram owner IDs."""
        return {int(item.strip()) for item in self.admin_ids_raw.split(",") if item.strip()}

    @property
    def reviewer_chat_ids(self) -> set[int]:
        """Return reviewer chat IDs, falling back to admins if not configured."""
        if not self.reviewer_chat_ids_raw:
            return self.admin_ids
        return {int(item.strip()) for item in self.reviewer_chat_ids_raw.split(",") if item.strip()}

    @property
    def parser_ready(self) -> bool:
        """Return True when read-only Telegram monitoring can be started."""
        return bool(self.parser_enabled and self.tg_api_id and self.tg_api_hash)

    @property
    def claude_ready(self) -> bool:
        """Return True when Claude API is configured."""
        return bool(self.anthropic_api_key)


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
