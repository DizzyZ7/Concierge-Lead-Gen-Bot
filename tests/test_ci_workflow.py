from __future__ import annotations

import unittest
from pathlib import Path


class CiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workflow = Path(".github/workflows/ci.yml").read_text(encoding="utf-8")
        cls.workflow_selftest = Path(".github/workflows/workflow-selftest.yml").read_text(encoding="utf-8")

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

    def test_workflow_selftest_uses_only_database_runtime_requirements(self) -> None:
        self.assertIn("alembic upgrade head && alembic current", self.workflow_selftest)
        self.assertIn("python -m scripts.workflow_selftest", self.workflow_selftest)
        self.assertIn("DATABASE_URL:", self.workflow_selftest)
        self.assertNotIn("BOT_TOKEN:", self.workflow_selftest)
        self.assertNotIn("REVIEWER_CHAT_IDS:", self.workflow_selftest)


if __name__ == "__main__":
    unittest.main()
