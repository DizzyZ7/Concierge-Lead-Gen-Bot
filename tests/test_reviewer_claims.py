from __future__ import annotations

import unittest
from datetime import timedelta
from types import SimpleNamespace

from services.reviewer_claims import (
    REVIEWER_CLAIM_TIMEOUT,
    claim_owner_label,
    claim_status_line,
    is_active_claim,
    snapshot_from_draft,
    utc_now,
)


class ReviewerClaimTests(unittest.TestCase):
    def test_free_draft_has_no_active_claim(self) -> None:
        draft = SimpleNamespace(
            claimed_by_user_id=None,
            claimed_by_username=None,
            claimed_by_name=None,
            claimed_at=None,
            claim_expires_at=None,
        )
        self.assertFalse(is_active_claim(draft))
        self.assertIn("свободна", claim_status_line(draft))

    def test_active_claim_shows_owner_and_expiration(self) -> None:
        now = utc_now()
        draft = SimpleNamespace(
            claimed_by_user_id=101,
            claimed_by_username="reviewer_one",
            claimed_by_name="Reviewer One",
            claimed_at=now,
            claim_expires_at=now + REVIEWER_CLAIM_TIMEOUT,
        )
        snapshot = snapshot_from_draft(draft)
        self.assertTrue(is_active_claim(draft, now=now))
        self.assertEqual(claim_owner_label(snapshot), "@reviewer_one")
        self.assertIn("В работе", claim_status_line(draft, now=now))

    def test_expired_claim_can_be_taken_again(self) -> None:
        now = utc_now()
        draft = SimpleNamespace(
            claimed_by_user_id=101,
            claimed_by_username=None,
            claimed_by_name="Reviewer One",
            claimed_at=now - timedelta(hours=1),
            claim_expires_at=now - timedelta(seconds=1),
        )
        self.assertFalse(is_active_claim(draft, now=now))
        self.assertIn("истек", claim_status_line(draft, now=now))


if __name__ == "__main__":
    unittest.main()
