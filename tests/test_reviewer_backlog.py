from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from bot.handlers.review_extras import (
    DEFAULT_REVIEWER_BACKLOG_HOURS,
    MAX_REVIEWER_BACKLOG_HOURS,
    clamp_backlog_hours,
    wait_hours,
)


class ReviewerBacklogTests(unittest.TestCase):
    def test_default_and_range_validation(self) -> None:
        self.assertEqual(clamp_backlog_hours(None), DEFAULT_REVIEWER_BACKLOG_HOURS)
        self.assertEqual(clamp_backlog_hours("1"), 1)
        self.assertEqual(clamp_backlog_hours(str(MAX_REVIEWER_BACKLOG_HOURS)), MAX_REVIEWER_BACKLOG_HOURS)
        self.assertIsNone(clamp_backlog_hours("0"))
        self.assertIsNone(clamp_backlog_hours(str(MAX_REVIEWER_BACKLOG_HOURS + 1)))
        self.assertIsNone(clamp_backlog_hours("tomorrow"))

    def test_wait_hours_handles_utc_and_naive_timestamps(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertGreaterEqual(wait_hours(now - timedelta(hours=3)), 2)
        self.assertGreaterEqual(wait_hours((now - timedelta(hours=3)).replace(tzinfo=None)), 2)
        self.assertEqual(wait_hours(None), 0)


if __name__ == "__main__":
    unittest.main()
