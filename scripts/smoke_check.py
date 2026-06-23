from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bot.handlers.all_handlers import build_router
from bot.handlers.failed import router as failed_router
from bot.main import create_bot, create_dispatcher
from bot.presentation import intent_label, status_label
from core.config import Settings
from db.models import Lead, ParsedPost, TargetChannel
from services.ai import AIService
from services.channel_cursor import advance_channel_cursor, iter_unseen_messages, reset_channel_cursor
from services.failed_items import mark_processing_failed
from services.parser import ParserService, current_day_start_utc, has_blocked_keyword, is_stale, split_csv, to_float
from services.runtime_ops import RuntimeOps, parse_iso, runtime_key
from services.text_tools import normalize_text, text_hash


def main() -> None:
    now = datetime.now(timezone.utc)
    assert split_csv("realty, visa,realty") == {"realty", "visa"}
    assert has_blocked_keyword("Crypto offer", "casino,crypto")
    assert not has_blocked_keyword("Thailand apartment", "casino,crypto")
    assert to_float(None, 0.7) == 0.7
    assert is_stale(now - timedelta(hours=25), 24)
    assert not is_stale(now - timedelta(hours=23), 24)
    assert current_day_start_utc("Asia/Bangkok").tzinfo == timezone.utc
    assert parse_iso(now.isoformat()) == now
    assert runtime_key("parser", "last_success_at") == "runtime.parser.last_success_at"
    assert intent_label("realty") == "Недвижимость"
    assert status_label("queued_by_limit") == "Отложено по дневному лимиту"
    assert status_label("processing_failed") == "Ошибка обработки"
    assert normalize_text("HTTPS://t.me/test  Phuket!!!") == "phuket"
    assert len(text_hash("Thailand relocation")) == 64
    assert TargetChannel.__tablename__ == "target_channels"
    assert hasattr(TargetChannel, "last_seen_message_id")
    assert ParsedPost.__tablename__ == "parsed_posts"
    assert Lead.__tablename__ == "leads"
    assert ParserService is not None
    assert AIService is not None
    assert RuntimeOps is not None
    assert mark_processing_failed is not None
    assert advance_channel_cursor is not None
    assert reset_channel_cursor is not None
    assert iter_unseen_messages is not None
    assert failed_router is not None
    assert Settings is not None
    assert create_bot is not None
    assert create_dispatcher is not None
    assert build_router() is not None
    print("Smoke check passed")


if __name__ == "__main__":
    main()
