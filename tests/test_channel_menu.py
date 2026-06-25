from __future__ import annotations

import unittest

from bot.handlers.channels import format_channel_detail, format_channels_overview
from bot.keyboards.inline import channel_actions, channels_menu
from db.models import TargetChannel


class ChannelMenuTests(unittest.TestCase):
    def test_channels_overview_is_compact(self) -> None:
        channels = [
            TargetChannel(id=1, channel_username="@phuket_f", geo="thailand", category="realty", is_active=True),
            TargetChannel(id=2, channel_username="@ru_chat_thailand", geo="thailand", category="expat_life", is_active=False),
        ]

        rendered = format_channels_overview(channels)

        self.assertIn("Всего: 2", rendered)
        self.assertIn("Мониторинг включен: 1", rendered)
        self.assertIn("#1 @phuket_f", rendered)
        self.assertIn("#2 @ru_chat_thailand", rendered)

    def test_channel_detail_keeps_full_configuration(self) -> None:
        channel = TargetChannel(
            id=7,
            channel_username="@nowtrendbrand",
            geo="thailand",
            category="business",
            is_active=True,
            daily_draft_limit=3,
            review_delay_min=10,
            review_delay_max=40,
            min_score=0.8,
            allowed_intents="investment,business,finance",
        )

        rendered = format_channel_detail(channel)

        self.assertIn("Канал #7", rendered)
        self.assertIn("Username: @nowtrendbrand", rendered)
        self.assertIn("Лимит черновиков в день: 3", rendered)
        self.assertIn("Разрешенные intent: investment,business,finance", rendered)

    def test_channel_keyboards_support_single_message_navigation(self) -> None:
        overview_callbacks = [
            button.callback_data
            for row in channels_menu([1, 2]).inline_keyboard
            for button in row
            if button.callback_data
        ]
        detail_callbacks = [
            button.callback_data
            for row in channel_actions(1).inline_keyboard
            for button in row
            if button.callback_data
        ]

        self.assertIn("channel:view:1", overview_callbacks)
        self.assertIn("channel:view:2", overview_callbacks)
        self.assertIn("channel:toggle:1", detail_callbacks)
        self.assertIn("nav:channels", detail_callbacks)
        self.assertIn("nav:dashboard", detail_callbacks)


if __name__ == "__main__":
    unittest.main()
