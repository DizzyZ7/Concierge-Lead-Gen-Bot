from __future__ import annotations

import unittest

from services.contact_candidates import contact_candidates_note, extract_public_telegram_handles


class ContactCandidateTests(unittest.TestCase):
    def test_extracts_public_usernames_and_tme_links(self) -> None:
        text = "Пишите @Agent_Thailand или https://t.me/agent_thailand, еще @Second_User"
        self.assertEqual(
            extract_public_telegram_handles(text),
            ("@agent_thailand", "@second_user"),
        )

    def test_ignores_private_links_and_phone_numbers(self) -> None:
        text = "Инвайт https://t.me/+private_code, телефон +66 123 456 789"
        self.assertEqual(extract_public_telegram_handles(text), ())
        self.assertIsNone(contact_candidates_note(text))

    def test_note_reminds_human_to_verify_owner(self) -> None:
        note = contact_candidates_note("@helpdesk_th")
        self.assertIsNotNone(note)
        self.assertIn("@helpdesk_th", note)
        self.assertIn("Проверь владельца", note)


if __name__ == "__main__":
    unittest.main()
