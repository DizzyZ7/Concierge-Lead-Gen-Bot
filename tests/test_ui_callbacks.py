from __future__ import annotations

import unittest

from bot.ui import callback_message_or_alert, edit_callback_message_or_alert


class FakeCallback:
    message = None

    def __init__(self) -> None:
        self.answers: list[tuple[str, bool]] = []

    async def answer(self, text: str | None = None, *, show_alert: bool | None = None, **_: object) -> None:
        self.answers.append((text or "", bool(show_alert)))


class CallbackUiTests(unittest.IsolatedAsyncioTestCase):
    async def test_edit_callback_message_or_alert_handles_missing_message(self) -> None:
        callback = FakeCallback()
        edited = await edit_callback_message_or_alert(callback, "Недоступное сообщение")  # type: ignore[arg-type]
        self.assertFalse(edited)
        self.assertEqual(callback.answers, [("Недоступное сообщение", True)])

    async def test_callback_message_or_alert_handles_missing_message(self) -> None:
        callback = FakeCallback()
        message = await callback_message_or_alert(callback, "Открой заново")  # type: ignore[arg-type]
        self.assertIsNone(message)
        self.assertEqual(callback.answers, [("Открой заново", True)])


if __name__ == "__main__":
    unittest.main()
