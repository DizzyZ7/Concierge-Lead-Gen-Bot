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

    def test_thailand_geo_aliases_cover_common_locations(self) -> None:
        self.assertTrue(AIService._geo_matches("ищу аренду на пхукете", "thailand"))
        self.assertTrue(AIService._geo_matches("кто живет в паттайе", "Thailand"))
        self.assertTrue(AIService._geo_matches("районы самуи", "samui"))
        self.assertFalse(AIService._geo_matches("ищу жилье в дубае", "thailand"))

    def test_fallback_score_adds_geo_bonus_for_phuket(self) -> None:
        thailand_score = AIService._fallback_score("Пхукет: ищу район для жизни", "thailand")["score"]
        neutral_score = AIService._fallback_score("Ищу район для жизни", "thailand")["score"]
        self.assertGreater(thailand_score, neutral_score)

    def test_circuit_breaker_opens_after_failure_and_resets_after_success(self) -> None:
        service = object.__new__(AIService)
        service.client = object()
        service._claude_failure_streak = 0
        service._claude_disabled_until = 0.0

        first_cooldown = service._register_claude_failure()
        self.assertEqual(first_cooldown, 30)
        self.assertTrue(service.claude_circuit_open)
        self.assertFalse(service._can_call_claude())

        second_cooldown = service._register_claude_failure()
        self.assertEqual(second_cooldown, 60)

        service._register_claude_success()
        self.assertEqual(service._claude_failure_streak, 0)
        self.assertFalse(service.claude_circuit_open)
        self.assertTrue(service._can_call_claude())


if __name__ == "__main__":
    unittest.main()
