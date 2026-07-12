from __future__ import annotations

import os
import unittest
from datetime import datetime, timezone
from unittest.mock import patch
from zoneinfo import ZoneInfo

from db.queries import business_today


class BusinessTimeTests(unittest.TestCase):
    def test_explicit_timezone_does_not_require_full_runtime_settings(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            result = business_today("Asia/Bangkok")
        self.assertEqual(result, datetime.now(ZoneInfo("Asia/Bangkok")).date())

    def test_environment_timezone_is_used(self) -> None:
        with patch.dict(os.environ, {"TIMEZONE": "UTC"}, clear=True):
            result = business_today()
        self.assertEqual(result, datetime.now(timezone.utc).date())

    def test_invalid_timezone_falls_back_to_utc(self) -> None:
        result = business_today("Invalid/Timezone")
        self.assertEqual(result, datetime.now(timezone.utc).date())


if __name__ == "__main__":
    unittest.main()
