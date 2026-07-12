from __future__ import annotations

import unittest

from scripts.workflow_check import mutation_enabled


class WorkflowCheckSafetyTests(unittest.TestCase):
    def test_mutation_flag_is_explicit(self) -> None:
        for value in (None, "", "0", "false", "no", "off"):
            self.assertFalse(mutation_enabled(value))
        for value in ("1", "true", "TRUE", "yes", " Yes "):
            self.assertTrue(mutation_enabled(value))


if __name__ == "__main__":
    unittest.main()
