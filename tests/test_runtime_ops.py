from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone

from services.runtime_ops import needs_recovery_notification


class RuntimeRecoveryTests(unittest.TestCase):
    def test_recovery_requires_unresolved_error(self) -> None:
        now = datetime.now(timezone.utc)
        self.assertFalse(needs_recovery_notification(now, None))
        self.assertFalse(needs_recovery_notification(now, now - timedelta(minutes=1)))
        self.assertTrue(needs_recovery_notification(now - timedelta(minutes=1), now))
        self.assertTrue(needs_recovery_notification(None, now))


if __name__ == "__main__":
    unittest.main()
