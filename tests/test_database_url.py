from __future__ import annotations

import unittest

from db.session import normalize_database_url


class DatabaseUrlTests(unittest.TestCase):
    def test_plain_postgresql_url_uses_asyncpg_driver(self) -> None:
        self.assertEqual(
            normalize_database_url("postgresql://user:pass@example.com:5432/app"),
            "postgresql+asyncpg://user:pass@example.com:5432/app",
        )

    def test_explicit_asyncpg_url_is_unchanged(self) -> None:
        self.assertEqual(
            normalize_database_url("postgresql+asyncpg://user:pass@example.com:5432/app"),
            "postgresql+asyncpg://user:pass@example.com:5432/app",
        )


if __name__ == "__main__":
    unittest.main()
