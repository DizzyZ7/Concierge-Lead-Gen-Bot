from __future__ import annotations

import unittest

from bot.keyboards.inline import reviewer_actions
from services.reviewer_cards import render_reviewer_card


class ReviewerClaimUiTests(unittest.TestCase):
    def test_reviewer_actions_include_claim_controls(self) -> None:
        markup = reviewer_actions(42, None)
        callbacks = {
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertIn("review:claim:42", callbacks)
        self.assertIn("review:release:42", callbacks)

    def test_reviewer_card_includes_claim_status(self) -> None:
        card = render_reviewer_card(
            draft_id=1,
            post_id=42,
            channel="@test",
            url=None,
            source_text="source",
            draft_text="draft",
            score=0.8,
            intent="realty",
            reason="reason",
            summary="summary",
            angle="angle",
            claim_line="В работе: @reviewer до 12:00 UTC.",
        )
        self.assertIn("Статус работы: В работе: @reviewer до 12:00 UTC.", card)


if __name__ == "__main__":
    unittest.main()
