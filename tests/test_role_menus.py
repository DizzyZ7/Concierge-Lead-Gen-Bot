from __future__ import annotations

import unittest

from bot.keyboards.inline import main_menu


def menu_texts(is_admin: bool) -> set[str]:
    markup = main_menu(is_admin=is_admin)
    return {button.text for row in markup.inline_keyboard for button in row}


class RoleMenuTests(unittest.TestCase):
    def test_reviewer_menu_hides_administration(self) -> None:
        texts = menu_texts(is_admin=False)
        self.assertIn("На проверке", texts)
        self.assertIn("Очередь reviewer-а", texts)
        self.assertNotIn("Каналы", texts)
        self.assertNotIn("Настройки", texts)
        self.assertNotIn("Лиды", texts)
        self.assertNotIn("Шаблоны", texts)

    def test_admin_menu_includes_administration(self) -> None:
        texts = menu_texts(is_admin=True)
        self.assertIn("Каналы", texts)
        self.assertIn("Настройки", texts)
        self.assertIn("Лиды", texts)
        self.assertIn("Шаблоны", texts)


if __name__ == "__main__":
    unittest.main()
