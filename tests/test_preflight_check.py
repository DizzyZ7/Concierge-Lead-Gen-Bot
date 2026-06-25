from __future__ import annotations

import os
import unittest
from unittest.mock import patch

from core.config import Settings
from scripts.preflight_check import config_blockers, has_explicit_reviewer_users, launch_check_ready


class PreflightCheckTests(unittest.TestCase):
    def settings(self, **values: object) -> Settings:
        base = {
            "BOT_TOKEN": "123:token",
            "ADMIN_IDS": "1",
            "REVIEWER_CHAT_IDS": "1",
            "DATABASE_URL": "postgresql://user:pass@example.com/db",
        }
        base.update(values)
        return Settings(**base)

    def test_launch_check_ready_uses_first_line(self) -> None:
        self.assertTrue(launch_check_ready("✅ Можно запускать\n\nDetails"))
        self.assertFalse(launch_check_ready("⚠️ Перед запуском нужно исправить пункты ниже\n"))
        self.assertFalse(launch_check_ready(""))

    def test_safe_reviewer_first_config_has_no_blockers(self) -> None:
        self.assertEqual(config_blockers(self.settings()), [])

    def test_unsafe_launch_flags_are_blocked(self) -> None:
        blockers = config_blockers(
            self.settings(
                OUTBOUND_ENABLED="true",
                AUTO_APPROVE="true",
                REVIEWER_MODE="false",
            )
        )
        self.assertIn("OUTBOUND_ENABLED must stay false for reviewer-first launch.", blockers)
        self.assertIn("AUTO_APPROVE must stay false for manual reviewer launch.", blockers)
        self.assertIn("REVIEWER_MODE must stay true for reviewer-first launch.", blockers)

    def test_group_delivery_requires_explicit_reviewer_users(self) -> None:
        with patch.dict(os.environ, {"REVIEWER_USER_IDS": ""}, clear=False):
            blockers = config_blockers(self.settings(REVIEWER_CHAT_IDS="-100123"))
        self.assertIn("Group reviewer delivery requires explicit positive REVIEWER_USER_IDS.", blockers)

    def test_group_delivery_accepts_explicit_reviewer_users(self) -> None:
        with patch.dict(os.environ, {"REVIEWER_USER_IDS": "101,202"}, clear=False):
            self.assertEqual(config_blockers(self.settings(REVIEWER_CHAT_IDS="-100123")), [])

    def test_parser_enabled_requires_telegram_api_credentials(self) -> None:
        blockers = config_blockers(self.settings(PARSER_ENABLED="true"))
        self.assertIn("PARSER_ENABLED=true requires TG_API_ID and TG_API_HASH.", blockers)

    def test_explicit_reviewer_user_helper_rejects_group_ids(self) -> None:
        self.assertTrue(has_explicit_reviewer_users("101"))
        with self.assertRaises(ValueError):
            has_explicit_reviewer_users("-100123")


if __name__ == "__main__":
    unittest.main()
