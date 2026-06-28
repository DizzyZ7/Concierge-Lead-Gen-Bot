from __future__ import annotations

import unittest
from unittest.mock import AsyncMock, patch

from core.config import Settings
from db.migration_guard import SchemaNotReadyError
from main import check_reviewer_chats, prepare_polling, run_startup_migrations, wait_for_database


class FakeBot:
    def __init__(self) -> None:
        self.deleted_webhook = False
        self.drop_pending_updates = None
        self.chat_actions: list[tuple[int, str]] = []

    async def delete_webhook(self, *, drop_pending_updates: bool) -> None:
        self.deleted_webhook = True
        self.drop_pending_updates = drop_pending_updates

    async def send_chat_action(self, *, chat_id: int, action: str) -> None:
        self.chat_actions.append((chat_id, action))
        if chat_id == -100404:
            raise RuntimeError("chat not reachable")


class BotHostStartupTests(unittest.IsolatedAsyncioTestCase):
    def settings(self, **values: object) -> Settings:
        base = {
            "BOT_TOKEN": "123:token",
            "ADMIN_IDS": "1",
            "REVIEWER_CHAT_IDS": "1,-100404",
            "DATABASE_URL": "postgresql://user:pass@example.com/db",
        }
        base.update(values)
        return Settings(**base)

    async def test_prepare_polling_deletes_webhook_and_pending_updates(self) -> None:
        bot = FakeBot()
        await prepare_polling(bot)  # type: ignore[arg-type]
        self.assertTrue(bot.deleted_webhook)
        self.assertTrue(bot.drop_pending_updates)

    async def test_reviewer_chat_check_keeps_running_after_unreachable_chat(self) -> None:
        bot = FakeBot()
        result = await check_reviewer_chats(bot, self.settings())  # type: ignore[arg-type]
        self.assertEqual(result[1], "ok")
        self.assertIn("RuntimeError", result[-100404])
        self.assertEqual(bot.chat_actions, [(-100404, "typing"), (1, "typing")])

    async def test_startup_migrations_upgrade_schema_when_revision_is_stale(self) -> None:
        with (
            patch("main.ensure_schema_current", new=AsyncMock(side_effect=[SchemaNotReadyError("stale"), "0010_reviewer_claims"])) as ensure,
            patch("main.upgrade_schema_to_head", new=AsyncMock()) as upgrade,
        ):
            revision = await run_startup_migrations(object())

        self.assertEqual(revision, "0010_reviewer_claims")
        self.assertEqual(ensure.await_count, 2)
        upgrade.assert_awaited_once()

    async def test_database_wait_retries_transient_driver_errors(self) -> None:
        with (
            patch("main.check_database_connection", new=AsyncMock(side_effect=[OSError("dns"), None])) as check,
            patch("main.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            await wait_for_database(object())

        self.assertEqual(check.await_count, 2)
        sleep.assert_awaited_once()

    async def test_database_wait_raises_after_retry_budget(self) -> None:
        with (
            patch("main.check_database_connection", new=AsyncMock(side_effect=OSError("down"))) as check,
            patch("main.asyncio.sleep", new=AsyncMock()) as sleep,
        ):
            with self.assertRaises(RuntimeError):
                await wait_for_database(object())

        self.assertEqual(check.await_count, 5)
        self.assertEqual(sleep.await_count, 4)


if __name__ == "__main__":
    unittest.main()
