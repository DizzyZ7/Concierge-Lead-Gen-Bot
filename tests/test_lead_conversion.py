from __future__ import annotations

import unittest

from services.lead_conversion import initial_lead_notes


class LeadConversionTests(unittest.TestCase):
    def test_notes_preserve_public_handle_as_unverified_hint(self) -> None:
        notes = initial_lead_notes(42, "Пишите @HelpfulAgent по переезду")
        self.assertIn("источник #42", notes)
        self.assertIn("@helpfulagent", notes)
        self.assertIn("Проверь владельца", notes)
        self.assertIn("Контактные данные нужно заполнить", notes)

    def test_notes_do_not_invent_contact_when_source_has_none(self) -> None:
        notes = initial_lead_notes(7, "Нужна квартира на Пхукете")
        self.assertIn("источник #7", notes)
        self.assertNotIn("Публичные Telegram-упоминания", notes)


if __name__ == "__main__":
    unittest.main()
