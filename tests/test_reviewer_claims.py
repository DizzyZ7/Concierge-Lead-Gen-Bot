from __future__ import annotations

import unittest
from datetime import timedelta
from types import SimpleNamespace

from services.reviewer_claims import (
    REVIEWER_CLAIM_TIMEOUT,
    claim_owner_label,
    claim_status_line,
    evaluate_claim_access,
    is_active_claim,
    snapshot_from_draft,
    utc_now,
)


def draft_with_claim(*, user_id: int | None, expires_delta: timedelta | None) -> SimpleNamespace:
    now = utc_now()
    return SimpleNamespace(
        claimed_by_user_id=user_id,
        claimed_by_username="reviewer_one" if user_id else None,
        claimed_by_name="Reviewer One" if user_id else None,
        claimed_at=now if user_id else None,
        claim_expires_at=(now + expires_delta) if expires_delta is not None else None,
    )


class ReviewerClaimTests(unittest.TestCase):
    def test_free_draft_has_no_active_claim(self) -> None:
        draft = draft_with_claim(user_id=None, expires_delta=None)
        self.assertFalse(is_active_claim(draft))
        self.assertIn("возьми", claim_status_line(draft))

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

    def test_live_reviewer_card_requires_claim(self) -> None:
        access = evaluate_claim_access(
            post_status="sent_to_reviewer",
            draft=draft_with_claim(user_id=None, expires_delta=None),
            actor_user_id=101,
            is_admin=False,
        )
        self.assertEqual(access.code, "claim_required")

    def test_claim_owner_is_allowed_and_other_reviewer_is_blocked(self) -> None:
        draft = draft_with_claim(user_id=101, expires_delta=timedelta(minutes=10))
        owner = evaluate_claim_access(
            post_status="sent_to_reviewer",
            draft=draft,
            actor_user_id=101,
            is_admin=False,
        )
        other = evaluate_claim_access(
            post_status="sent_to_reviewer",
            draft=draft,
            actor_user_id=202,
            is_admin=False,
        )
        self.assertEqual(owner.code, "allowed")
        self.assertEqual(other.code, "taken")

    def test_admin_bypasses_claim_and_non_live_posts_are_unaffected(self) -> None:
        draft = draft_with_claim(user_id=101, expires_delta=timedelta(minutes=10))
        admin = evaluate_claim_access(
            post_status="sent_to_reviewer",
            draft=draft,
            actor_user_id=999,
            is_admin=True,
        )
        pending = evaluate_claim_access(
            post_status="pending",
            draft=None,
            actor_user_id=202,
            is_admin=False,
        )
        self.assertEqual(admin.code, "allowed")
        self.assertEqual(pending.code, "allowed")


if __name__ == "__main__":
    unittest.main()
