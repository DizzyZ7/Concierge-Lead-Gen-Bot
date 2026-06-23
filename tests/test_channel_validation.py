from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from services.channel_validation import VALIDATION_MAX_AGE, is_channel_validation_fresh


class ChannelValidationFreshnessTests(unittest.TestCase):
    def test_missing_validation_is_not_fresh(self) -> None:
        self.assertFalse(is_channel_validation_fresh(None, None))

    def test_recent_success_is_fresh(self) -> None:
        now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)
        self.assertTrue(
            is_channel_validation_fresh(
                now - timedelta(days=1),
                None,
                now=now,
            )
        )

    def test_error_or_expired_validation_is_not_fresh(self) -> None:
        now = datetime(2026, 6, 23, 12, 0, tzinfo=timezone.utc)
        self.assertFalse(
            is_channel_validation_fresh(
                now - timedelta(days=1),
                "ChannelPrivateError",
                now=now,
            )
        )
        self.assertFalse(
            is_channel_validation_fresh(
                now - VALIDATION_MAX_AGE - timedelta(seconds=1),
                None,
                now=now,
            )
        )


if __name__ == "__main__":
    unittest.main()
