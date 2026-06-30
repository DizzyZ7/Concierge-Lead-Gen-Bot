from __future__ import annotations

from pathlib import Path
import unittest


class CallbackSafetyTests(unittest.TestCase):
    def test_handlers_do_not_access_callback_message_directly(self) -> None:
        handlers_dir = Path("bot/handlers")
        forbidden = (
            "callback.message.answer",
            "callback.message.edit_text",
            "(callback.message,",
            " callback.message,",
        )
        offenders: list[str] = []
        for path in handlers_dir.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            for marker in forbidden:
                if marker in text:
                    offenders.append(f"{path}:{marker}")
        self.assertEqual(offenders, [])


if __name__ == "__main__":
    unittest.main()
