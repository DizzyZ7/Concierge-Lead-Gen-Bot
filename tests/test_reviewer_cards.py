from __future__ import annotations

import unittest

from services.reviewer_cards import render_reviewer_card, trim


class ReviewerCardTests(unittest.TestCase):
    def test_trim_keeps_limit_and_marks_truncation(self) -> None:
        self.assertEqual(trim("abc", 10), "abc")
        self.assertEqual(trim("abcdef", 4), "abc...")

    def test_card_escapes_untrusted_html_and_contains_context(self) -> None:
        card = render_reviewer_card(
            draft_id=7,
            post_id=11,
            channel="@test<channel>",
            url="https://t.me/test/11",
            source_text="Нужно <помочь> & проверить",
            draft_text="Напишите <мне> & обсудим",
            score=0.82,
            intent="realty",
            reason="Есть <запрос>",
            summary="Кратко & понятно",
            angle="Уточнить район",
        )
        self.assertIn("Лид-радар: пост #11", card)
        self.assertIn("Черновик #7", card)
        self.assertIn("@test&lt;channel&gt;", card)
        self.assertIn("Нужно &lt;помочь&gt; &amp; проверить", card)
        self.assertIn("Напишите &lt;мне&gt; &amp; обсудим", card)
        self.assertIn("Оценка: 0.82", card)


if __name__ == "__main__":
    unittest.main()
