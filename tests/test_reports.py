from __future__ import annotations

import unittest

from bot.handlers.reports import clamp_days, quality_recommendation


class SourceQualityTests(unittest.TestCase):
    def test_days_are_clamped_to_safe_range(self) -> None:
        self.assertEqual(clamp_days(None), 7)
        self.assertEqual(clamp_days("bad"), 7)
        self.assertEqual(clamp_days("0"), 1)
        self.assertEqual(clamp_days("120"), 90)
        self.assertEqual(clamp_days("14"), 14)

    def test_quality_recommendations_cover_source_states(self) -> None:
        self.assertEqual(
            quality_recommendation(total=2, leads=0, commented=0, noise=0, open_items=0),
            "нужно больше данных",
        )
        self.assertIn(
            "шумный",
            quality_recommendation(total=10, leads=0, commented=0, noise=7, open_items=0),
        )
        self.assertIn(
            "незакрытого",
            quality_recommendation(total=10, leads=0, commented=0, noise=1, open_items=6),
        )
        self.assertIn(
            "сильный",
            quality_recommendation(total=10, leads=1, commented=1, noise=1, open_items=1),
        )


if __name__ == "__main__":
    unittest.main()
