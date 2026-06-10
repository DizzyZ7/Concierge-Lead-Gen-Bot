from __future__ import annotations

from datetime import date
from functools import lru_cache
from typing import Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


Geo = Literal["thailand", "bali", "vietnam"]
Intent = Literal["relocation", "realty", "tourism", "investment", "visa", "unknown"]


class Settings(BaseSettings):
    """Application configuration loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    bot_token: str = Field(..., alias="BOT_TOKEN")

    tg_api_id: int = Field(..., alias="TG_API_ID")
    tg_api_hash: str = Field(..., alias="TG_API_HASH")
    tg_phone: str = Field(..., alias="TG_PHONE")
    tg_session_name: str = Field("concierge_session", alias="TG_SESSION_NAME")

    admin_ids_raw: str = Field(..., alias="ADMIN_IDS")
    reviewer_chat_ids_raw: str | None = Field(None, alias="REVIEWER_CHAT_IDS")

    database_url: str = Field(..., alias="DATABASE_URL")

    anthropic_api_key: str = Field(..., alias="ANTHROPIC_API_KEY")
    anthropic_model: str = Field("claude-3-5-haiku-20241022", alias="ANTHROPIC_MODEL")

    timezone: str = Field("Asia/Bangkok", alias="TIMEZONE")
    auto_approve: bool = Field(False, alias="AUTO_APPROVE")
    max_daily_comments: int = Field(30, alias="MAX_DAILY_COMMENTS")
    warmup_mode: bool = Field(True, alias="WARMUP_MODE")
    account_started_at: date | None = Field(None, alias="ACCOUNT_STARTED_AT")
    min_comment_hour: int = Field(9, alias="MIN_COMMENT_HOUR")
    max_comment_hour: int = Field(22, alias="MAX_COMMENT_HOUR")
    parser_limit_per_channel: int = Field(20, alias="PARSER_LIMIT_PER_CHANNEL")

    reviewer_mode: bool = Field(True, alias="REVIEWER_MODE")
    posting_enabled: bool = Field(False, alias="POSTING_ENABLED")

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
        """Return private reviewer chat IDs, falling back to admins if not configured."""
        if not self.reviewer_chat_ids_raw:
            return self.admin_ids
        return {int(item.strip()) for item in self.reviewer_chat_ids_raw.split(",") if item.strip()}


@lru_cache
def get_settings() -> Settings:
    """Return cached settings instance."""
    return Settings()
