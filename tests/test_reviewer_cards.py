from __future__ import annotations

import unittest

from services.reviewer_cards import escape_and_trim, render_reviewer_card


class ReviewerCardTests(unittest.TestCase):
    def test_escape_and_trim_preserves_complete_entities(self) -> None:
        self.assertEqual(escape_and_trim("abc", 10), "abc")
        self.assertEqual(escape_and_trim("<>&", 20), "&lt;&gt;&amp;")
        truncated = escape_and_trim("&" * 20, 20)
        self.assertLessEqual(len(truncated), 20)
        self.assertTrue(truncated.endswith("..."))
        self.assertNotIn("&am...", truncated)

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

    def test_card_stays_bounded_with_special_character_heavy_input(self) -> None:
        card = render_reviewer_card(
            draft_id=1,
            post_id=1,
            channel="@channel",
            url=None,
            source_text="&" * 5000,
            draft_text="<" * 5000,
            score=None,
            intent="unknown",
            reason=None,
            summary=None,
            angle=None,
        )
        self.assertLess(len(card), 4096)
        self.assertIn("&amp;", card)
        self.assertIn("&lt;", card)


if __name__ == "__main__":
    unittest.main()
