from __future__ import annotations

from types import SimpleNamespace
import unittest

from bot.handlers.post_action_callbacks import feedback
from services.post_audit import actor_from_user


class PostAuditTests(unittest.TestCase):
    def test_actor_from_user_keeps_public_reviewer_identity(self) -> None:
        user = SimpleNamespace(id=123, username="Reviewer_A", full_name="Reviewer Alpha")
        actor = actor_from_user(user)
        self.assertEqual(actor.user_id, 123)
        self.assertEqual(actor.username, "Reviewer_A")
        self.assertEqual(actor.name, "Reviewer Alpha")

    def test_actor_from_none_is_anonymous(self) -> None:
        actor = actor_from_user(None)
        self.assertIsNone(actor.user_id)
        self.assertIsNone(actor.username)
        self.assertIsNone(actor.name)

    def test_callback_feedback_preserves_state_semantics(self) -> None:
        self.assertEqual(feedback("updated", "ok"), "ok")
        self.assertIn("уже", feedback("already", "ok"))
        self.assertIn("закрыт", feedback("blocked", "ok"))
        self.assertIn("не найден", feedback("missing", "ok"))


if __name__ == "__main__":
    unittest.main()
