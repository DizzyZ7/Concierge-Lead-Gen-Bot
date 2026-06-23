from __future__ import annotations

import unittest

from services.ai import AIService, VALID_INTENTS


class AISafetyTests(unittest.TestCase):
    def test_safe_intent_keeps_known_values(self) -> None:
        self.assertEqual(AIService._safe_intent("realty"), "realty")
        self.assertEqual(AIService._safe_intent("VISA"), "visa")

    def test_safe_intent_rejects_unknown_values(self) -> None:
        self.assertEqual(AIService._safe_intent("sell_everything"), "unknown")
        self.assertEqual(AIService._safe_intent(None), "unknown")

    def test_intent_registry_contains_expected_baseline(self) -> None:
        self.assertIn("relocation", VALID_INTENTS)
        self.assertIn("unknown", VALID_INTENTS)

    def test_business_context_prompt_does_not_invent_offer_when_empty(self) -> None:
        prompt = AIService._business_context_prompt("")
        self.assertIn("not configured", prompt)
        self.assertIn("do not assume", prompt)


if __name__ == "__main__":
    unittest.main()
