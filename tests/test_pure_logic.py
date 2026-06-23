from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from bot.handlers.leads import DEFAULT_FOLLOWUP_HOURS, format_activity
from bot.keyboards.inline import main_menu
from services.parser import current_day_start_utc, has_blocked_keyword, is_stale, split_csv
from services.post_state import APPROVABLE_STATUSES, FINAL_OUTCOME_STATUSES, can_approve
from services.text_tools import normalize_text, text_hash


class TextToolsTests(unittest.TestCase):
    def test_normalize_removes_url_punctuation_and_extra_spaces(self) -> None:
        self.assertEqual(normalize_text("  Phuket!!! https://t.me/example  "), "phuket")

    def test_same_normalized_content_has_same_hash(self) -> None:
        self.assertEqual(text_hash("Пхукет!!!"), text_hash("пхукет"))


class ParserHelpersTests(unittest.TestCase):
    def test_csv_filters_are_normalized_and_deduplicated(self) -> None:
        self.assertEqual(split_csv("realty, visa,realty"), {"realty", "visa"})

    def test_blocked_keyword_detects_case_insensitively(self) -> None:
        self.assertTrue(has_blocked_keyword("Crypto offer", "casino,crypto"))
        self.assertFalse(has_blocked_keyword("Thailand apartment", "casino,crypto"))

    def test_stale_post_guard(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertTrue(is_stale(now - timedelta(hours=25), 24))
        self.assertFalse(is_stale(now - timedelta(hours=23), 24))

    def test_day_start_is_utc_aware(self) -> None:
        self.assertEqual(current_day_start_utc("Asia/Bangkok").tzinfo, timezone.utc)


class WorkflowGuardTests(unittest.TestCase):
    def test_approval_allowed_only_for_unprocessed_eligible_statuses(self) -> None:
        self.assertTrue(can_approve("pending", False))
        self.assertTrue(can_approve("queued_by_limit", False))
        self.assertFalse(can_approve("approved", True))
        self.assertFalse(can_approve("lead", False))

    def test_workflow_status_sets_are_consistent(self) -> None:
        self.assertIn("pending", APPROVABLE_STATUSES)
        self.assertIn("lead", FINAL_OUTCOME_STATUSES)
        self.assertTrue(APPROVABLE_STATUSES.isdisjoint(FINAL_OUTCOME_STATUSES))


class LeadFollowupTests(unittest.TestCase):
    def test_default_followup_window(self) -> None:
        self.assertEqual(DEFAULT_FOLLOWUP_HOURS, 48)

    def test_activity_format_contains_utc_and_elapsed_time(self) -> None:
        rendered = format_activity(datetime.now(timezone.utc) - timedelta(hours=3))
        self.assertIn("UTC", rendered)
        self.assertIn("ч. назад", rendered)


class MainMenuTests(unittest.TestCase):
    def test_daily_limit_queue_is_present(self) -> None:
        callback_data = {
            button.callback_data
            for row in main_menu().inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertIn("nav:limit_queue", callback_data)
        self.assertIn("nav:failed_queue", callback_data)


if __name__ == "__main__":
    unittest.main()
