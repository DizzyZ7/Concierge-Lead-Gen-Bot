from __future__ import annotations

import unittest

from scripts.validate_channels import render_validation_lines, validation_details, validation_exit_code
from services.channel_validation import ChannelValidationResult


class ValidateChannelsScriptTests(unittest.TestCase):
    def test_successful_results_render_ok_lines_and_zero_exit(self) -> None:
        results = [
            ChannelValidationResult(channel_id=1, username="@one", ok=True, title="One"),
            ChannelValidationResult(channel_id=2, username="@two", ok=True),
        ]

        self.assertEqual(validation_details(results), "checked=2 failed=0")
        self.assertEqual(validation_exit_code(results), 0)
        self.assertEqual(
            render_validation_lines(results),
            [
                "Telegram source validation",
                "checked=2 failed=0",
                "OK #1 @one - One",
                "OK #2 @two",
            ],
        )

    def test_failed_results_render_fail_lines_and_nonzero_exit(self) -> None:
        results = [
            ChannelValidationResult(channel_id=1, username="@one", ok=True, title="One"),
            ChannelValidationResult(channel_id=2, username="@private", ok=False, error="ChannelPrivateError"),
        ]

        self.assertEqual(validation_details(results), "checked=2 failed=1")
        self.assertEqual(validation_exit_code(results), 1)
        self.assertIn("FAIL #2 @private: ChannelPrivateError", render_validation_lines(results))


if __name__ == "__main__":
    unittest.main()
