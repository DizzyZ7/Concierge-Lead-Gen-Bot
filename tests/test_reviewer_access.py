from __future__ import annotations

import unittest

from core.reviewer_access import parse_reviewer_user_ids


class ReviewerAccessTests(unittest.TestCase):
    def test_parse_explicit_reviewer_users(self) -> None:
        self.assertEqual(parse_reviewer_user_ids("101, 202,101"), {101, 202})
        self.assertEqual(parse_reviewer_user_ids(None), set())
        self.assertEqual(parse_reviewer_user_ids("  "), set())

    def test_reject_group_ids_and_invalid_values(self) -> None:
        with self.assertRaises(ValueError):
            parse_reviewer_user_ids("-100123456")
        with self.assertRaises(ValueError):
            parse_reviewer_user_ids("101,alice")
        with self.assertRaises(ValueError):
            parse_reviewer_user_ids("0")


if __name__ == "__main__":
    unittest.main()
