from __future__ import annotations

import unittest

from services.limit_queue_promoter import available_daily_capacity, promotion_fetch_limit


class LimitQueueTests(unittest.TestCase):
    def test_daily_capacity_is_bounded(self) -> None:
        self.assertEqual(available_daily_capacity(5, 0), 5)
        self.assertEqual(available_daily_capacity(5, 3), 2)
        self.assertEqual(available_daily_capacity(5, 5), 0)
        self.assertEqual(available_daily_capacity(0, 0), 0)
        self.assertEqual(available_daily_capacity(-3, 0), 0)

    def test_fetch_limit_keeps_minimum_observation_window(self) -> None:
        self.assertEqual(promotion_fetch_limit(0), 5)
        self.assertEqual(promotion_fetch_limit(3), 15)


if __name__ == "__main__":
    unittest.main()
