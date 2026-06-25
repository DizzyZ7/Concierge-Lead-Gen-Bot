from __future__ import annotations

import unittest
from pathlib import Path


class CiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")

    def test_ci_uses_valid_test_bot_token(self) -> None:
        self.assertIn("BOT_TOKEN: 123456:test-token", self.workflow)

    def test_ci_keeps_launch_quality_gates(self) -> None:
        required_commands = [
            "docker compose config",
            "docker compose -f compose.external-db.yaml config",
            "python -m compileall -q .",
            "alembic upgrade head && alembic current",
            "python -m unittest discover -s tests -v",
            "python -m scripts.smoke_check",
            "python -m scripts.preflight_check",
        ]
        for command in required_commands:
            with self.subTest(command=command):
                self.assertIn(command, self.workflow)


if __name__ == "__main__":
    unittest.main()
