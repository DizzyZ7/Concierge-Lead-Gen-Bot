from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bot.handlers.all_handlers import build_router
from bot.handlers.failed import router as failed_router
from bot.handlers.leads import DEFAULT_FOLLOWUP_HOURS, format_activity
from bot.main import create_bot, create_dispatcher
from bot.presentation import intent_label, status_label
from core.config import Settings
from core.reviewer_access import parse_reviewer_user_ids
from db.migration_guard import REQUIRED_ALEMBIC_REVISION
from db.models import Lead, ParsedPost, PostAction, ReviewDraft, TargetChannel
from db.session import normalize_database_url
from services.ai import AIService
from services.channel_cursor import advance_channel_cursor, iter_unseen_messages, reset_channel_cursor
from services.channel_validation import is_channel_validation_fresh
from services.failed_items import mark_processing_failed
from services.parser import ParserService, current_day_start_utc, has_blocked_keyword, is_stale, split_csv, to_float
from services.post_audit import actor_from_user, list_post_actions, record_post_action
from services.post_state import APPROVABLE_STATUSES, FINAL_OUTCOME_STATUSES, apply_result_once, can_approve, mark_reviewer_done_once, skip_post_once
from services.reviewer_cards import render_reviewer_card
from services.reviewer_claims import REVIEWER_CLAIM_TIMEOUT, claim_status_line, is_active_claim
from services.runtime_ops import RuntimeOps, needs_recovery_notification, parse_iso, runtime_key
from services.text_tools import normalize_text, text_hash
from scripts import preflight_check, validate_channels


def main() -> None:
    now = datetime.now(timezone.utc)
    assert REQUIRED_ALEMBIC_REVISION == "0010_reviewer_claims"
    assert normalize_database_url("postgresql://u:p@host:5432/db").startswith("postgresql+asyncpg://")
    assert normalize_database_url("postgresql+asyncpg://u:p@host:5432/db") == "postgresql+asyncpg://u:p@host:5432/db"
    assert split_csv("realty, visa,realty") == {"realty", "visa"}
    assert has_blocked_keyword("Crypto offer", "casino,crypto")
    assert not has_blocked_keyword("Thailand apartment", "casino,crypto")
    assert to_float(None, 0.7) == 0.7
    assert is_stale(now - timedelta(hours=25), 24)
    assert not is_stale(now - timedelta(hours=23), 24)
    assert current_day_start_utc("Asia/Bangkok").tzinfo == timezone.utc
    assert parse_iso(now.isoformat()) == now
    assert runtime_key("parser", "last_success_at") == "runtime.parser.last_success_at"
    assert needs_recovery_notification(now - timedelta(minutes=1), now)
    assert not needs_recovery_notification(now, now - timedelta(minutes=1))
    assert parse_reviewer_user_ids("101,202") == {101, 202}
    assert intent_label("realty") == "Недвижимость"
    assert status_label("queued_by_limit") == "Отложено по дневному лимиту"
    assert status_label("processing_failed") == "Ошибка обработки"
    assert can_approve("pending", False)
    assert can_approve("queued_by_limit", False)
    assert not can_approve("approved", True)
    assert "lead" in FINAL_OUTCOME_STATUSES
    assert "pending" in APPROVABLE_STATUSES
    assert DEFAULT_FOLLOWUP_HOURS == 48
    assert REVIEWER_CLAIM_TIMEOUT == timedelta(minutes=45)
    assert "UTC" in format_activity(now - timedelta(hours=2))
    assert normalize_text("HTTPS://t.me/test  Phuket!!!") == "phuket"
    assert len(text_hash("Thailand relocation")) == 64
    assert "Лид-радар" in render_reviewer_card(
        draft_id=1,
        post_id=1,
        channel="@test",
        url=None,
        source_text="source",
        draft_text="draft",
        score=0.7,
        intent="realty",
        reason="reason",
        summary="summary",
        angle="angle",
        claim_line="Карточка свободна.",
    )
    assert TargetChannel.__tablename__ == "target_channels"
    assert hasattr(TargetChannel, "last_seen_message_id")
    assert hasattr(TargetChannel, "last_validation_at")
    assert hasattr(TargetChannel, "last_validation_error")
    assert is_channel_validation_fresh(now, None, now=now)
    assert not is_channel_validation_fresh(now, "ChannelPrivateError", now=now)
    assert ParsedPost.__tablename__ == "parsed_posts"
    assert ReviewDraft.__tablename__ == "review_drafts"
    assert hasattr(ReviewDraft, "claimed_by_user_id")
    assert hasattr(ReviewDraft, "claim_expires_at")
    assert PostAction.__tablename__ == "post_actions"
    assert Lead.__tablename__ == "leads"
    assert hasattr(Lead, "updated_at")
    assert actor_from_user(None).user_id is None
    assert list_post_actions is not None
    assert record_post_action is not None
    assert claim_status_line is not None
    assert is_active_claim is not None
    assert ParserService is not None
    assert AIService is not None
    assert RuntimeOps is not None
    assert mark_processing_failed is not None
    assert advance_channel_cursor is not None
    assert reset_channel_cursor is not None
    assert iter_unseen_messages is not None
    assert apply_result_once is not None
    assert mark_reviewer_done_once is not None
    assert skip_post_once is not None
    assert failed_router is not None
    assert Settings is not None
    assert create_bot is not None
    assert create_dispatcher is not None
    assert build_router() is not None
    assert preflight_check.main is not None
    assert preflight_check.launch_check_ready("✅ Можно запускать\n") is True
    assert preflight_check.launch_check_ready("⚠️ Перед запуском нужно исправить пункты ниже\n") is False
    safe_settings = Settings(BOT_TOKEN="123:token", ADMIN_IDS="1", DATABASE_URL="postgresql://u:p@host/db")
    assert preflight_check.config_blockers(safe_settings) == []
    unsafe_settings = Settings(
        BOT_TOKEN="123:token",
        ADMIN_IDS="1",
        REVIEWER_CHAT_IDS="-100123",
        DATABASE_URL="postgresql://u:p@host/db",
        OUTBOUND_ENABLED="true",
        AUTO_APPROVE="true",
        REVIEWER_MODE="false",
        PARSER_ENABLED="true",
    )
    assert len(preflight_check.config_blockers(unsafe_settings)) == 5
    assert validate_channels.main is not None
    assert validate_channels.validation_details([]) == "checked=0 failed=0"
    print("Smoke check passed")


if __name__ == "__main__":
    main()
