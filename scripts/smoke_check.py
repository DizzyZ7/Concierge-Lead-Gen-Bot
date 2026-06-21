from __future__ import annotations

from datetime import datetime, timedelta, timezone

from bot.handlers.all_handlers import build_router
from bot.main import create_bot, create_dispatcher
from core.config import Settings
from db.models import Lead, ParsedPost, TargetChannel
from services.ai import AIService
from services.parser import ParserService, has_blocked_keyword, is_stale, split_csv, to_float
from services.text_tools import normalize_text, text_hash


def main() -> None:
    assert split_csv("realty, visa,realty") == {"realty", "visa"}
    assert has_blocked_keyword("Crypto offer", "casino,crypto")
    assert not has_blocked_keyword("Thailand apartment", "casino,crypto")
    assert to_float(None, 0.7) == 0.7
    assert is_stale(datetime.now(timezone.utc) - timedelta(hours=25), 24)
    assert not is_stale(datetime.now(timezone.utc) - timedelta(hours=23), 24)
    assert normalize_text("HTTPS://t.me/test  Phuket!!!") == "phuket"
    assert len(text_hash("Thailand relocation")) == 64
    assert TargetChannel.__tablename__ == "target_channels"
    assert ParsedPost.__tablename__ == "parsed_posts"
    assert Lead.__tablename__ == "leads"
    assert ParserService is not None
    assert AIService is not None
    assert Settings is not None
    assert create_bot is not None
    assert create_dispatcher is not None
    assert build_router() is not None
    print("Smoke check passed")


if __name__ == "__main__":
    main()
