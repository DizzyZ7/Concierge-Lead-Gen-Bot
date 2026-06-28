from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramUnauthorizedError
from telethon import TelegramClient

from bot.main import create_bot, create_dispatcher
from core.config import Settings, get_settings
from core.logger import get_logger, setup_logging
from core.scheduler import create_scheduler
from db.migration_guard import SchemaNotReadyError, ensure_schema_current, upgrade_schema_to_head
from db.session import check_database_connection, create_engine, create_session_factory
from services.ai import AIService
from services.channel_validation import validate_channels
from services.limit_queue_promoter import LimitQueuePromoter
from services.parser import ParserService
from services.reviewer_dispatcher import ReviewerDispatcher
from services.runtime_ops import RuntimeOps

log = get_logger(__name__)
SOURCE_VALIDATION_INTERVAL_HOURS = 24
DATABASE_CONNECT_ATTEMPTS = 5
DATABASE_CONNECT_RETRY_SECONDS = 3


async def wait_for_database(engine) -> None:
    last_error: Exception | None = None
    for attempt in range(1, DATABASE_CONNECT_ATTEMPTS + 1):
        try:
            await check_database_connection(engine)
            log.info("database_connection_ok", attempt=attempt)
            return
        except Exception as error:
            last_error = error
            log.warning(
                "database_connection_failed",
                attempt=attempt,
                attempts=DATABASE_CONNECT_ATTEMPTS,
                retry_seconds=DATABASE_CONNECT_RETRY_SECONDS,
                error=str(error),
            )
            if attempt < DATABASE_CONNECT_ATTEMPTS:
                await asyncio.sleep(DATABASE_CONNECT_RETRY_SECONDS)
    raise RuntimeError("Database connection failed after retries") from last_error


async def run_startup_migrations(session_factory) -> str:
    try:
        return await ensure_schema_current(session_factory)
    except SchemaNotReadyError as error:
        log.warning("database_schema_upgrade_required", error=str(error))
        await upgrade_schema_to_head()
        revision = await ensure_schema_current(session_factory)
        log.info("database_schema_current", revision=revision)
        return revision


async def prepare_polling(bot: Bot) -> None:
    await bot.delete_webhook(drop_pending_updates=True)
    log.info("telegram_webhook_deleted", drop_pending_updates=True)


async def check_reviewer_chats(bot: Bot, settings: Settings) -> dict[int, str]:
    results: dict[int, str] = {}
    for chat_id in sorted(settings.reviewer_chat_ids):
        try:
            await bot.send_chat_action(chat_id=chat_id, action="typing")
            results[chat_id] = "ok"
            log.info("reviewer_chat_reachable", chat_id=chat_id)
        except (TelegramForbiddenError, TelegramBadRequest) as error:
            results[chat_id] = f"{error.__class__.__name__}: {error}"
            log.warning(
                "reviewer_chat_unreachable",
                chat_id=chat_id,
                error=str(error),
                hint="Add the bot to this reviewer chat and allow it to send messages.",
            )
        except Exception as error:
            results[chat_id] = f"{error.__class__.__name__}: {error}"
            log.warning("reviewer_chat_check_failed", chat_id=chat_id, error=str(error))
    return results


async def startup_self_check(
    *,
    bot: Bot,
    dispatcher: Dispatcher,
    settings: Settings,
    db_revision: str,
) -> None:
    try:
        me = await bot.get_me()
    except TelegramUnauthorizedError as error:
        log.error("bot_token_invalid", error=str(error))
        raise
    reviewer_results = await check_reviewer_chats(bot, settings)
    log.info(
        "startup_self_check",
        bot_username=me.username,
        bot_id=me.id,
        db_revision=db_revision,
        dispatcher_routers=len(dispatcher.sub_routers),
        reviewer_chat_ids=sorted(settings.reviewer_chat_ids),
        reviewer_reachability=reviewer_results,
        parser_enabled=settings.parser_enabled,
        parser_ready=settings.parser_ready,
    )


async def build_parser(
    settings: Settings,
    session_factory,
    ai_service: AIService,
    runtime_ops: RuntimeOps,
) -> tuple[TelegramClient | None, ParserService | None]:
    if not settings.parser_ready:
        return None, None
    session_path = Path("sessions") / settings.tg_session_name
    client = TelegramClient(str(session_path), settings.tg_api_id, settings.tg_api_hash)
    await client.connect()
    if not await client.is_user_authorized():
        log.warning("telegram_session_not_authorized", session=str(session_path))
        await runtime_ops.failure("parser", RuntimeError("Telegram user session is not authorized"), str(session_path))
        await client.disconnect()
        return None, None
    parser = ParserService(
        client=client,
        session_factory=session_factory,
        ai_service=ai_service,
        settings=settings,
        runtime_ops=runtime_ops,
    )
    return client, parser


async def main() -> None:
    setup_logging()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    await wait_for_database(engine)
    db_revision = await run_startup_migrations(session_factory)

    bot = create_bot(settings)
    ai_service = AIService(settings)
    runtime_ops = RuntimeOps(bot=bot, session_factory=session_factory, settings=settings)
    source_workflow_lock = asyncio.Lock()
    dispatcher = create_dispatcher(
        settings=settings,
        session_factory=session_factory,
        ai_service=ai_service,
        runtime_ops=runtime_ops,
        source_workflow_lock=source_workflow_lock,
    )
    reviewer = ReviewerDispatcher(
        bot=bot,
        session_factory=session_factory,
        settings=settings,
        runtime_ops=runtime_ops,
    )
    limit_queue_promoter = LimitQueuePromoter(
        session_factory=session_factory,
        ai_service=ai_service,
        settings=settings,
        runtime_ops=runtime_ops,
    )
    telegram_client, parser = await build_parser(settings, session_factory, ai_service, runtime_ops)
    dispatcher.workflow_data["parser_service"] = parser
    dispatcher.workflow_data["limit_queue_promoter"] = limit_queue_promoter

    async def run_limit_queue_promoter() -> None:
        async with source_workflow_lock:
            await limit_queue_promoter.run_once()

    async def run_parser() -> None:
        if not parser:
            return
        async with source_workflow_lock:
            await parser.run_once()

    async def run_source_validation() -> None:
        if not parser:
            return
        async with source_workflow_lock:
            results = await validate_channels(parser.client, session_factory)
        failed = [result for result in results if not result.ok]
        details = f"checked={len(results)} failed={len(failed)}"
        if failed:
            usernames = ", ".join(result.username for result in failed[:5])
            await runtime_ops.failure(
                "source_validation",
                RuntimeError(f"Недоступные источники: {usernames}"),
                details,
            )
            return
        await runtime_ops.heartbeat("source_validation", details)

    scheduler = create_scheduler(settings)
    first_run = datetime.now(timezone.utc)
    scheduler.add_job(
        reviewer.run_once,
        "interval",
        minutes=1,
        id="reviewer_dispatcher",
        max_instances=1,
        coalesce=True,
        next_run_time=first_run,
    )
    scheduler.add_job(
        run_limit_queue_promoter,
        "interval",
        minutes=5,
        id="limit_queue_promoter",
        max_instances=1,
        coalesce=True,
        next_run_time=first_run,
    )
    if parser:
        scheduler.add_job(
            run_parser,
            "interval",
            minutes=settings.parser_interval_minutes,
            id="read_only_parser",
            max_instances=1,
            coalesce=True,
            next_run_time=first_run,
        )
        scheduler.add_job(
            run_source_validation,
            "interval",
            hours=SOURCE_VALIDATION_INTERVAL_HOURS,
            id="source_validation",
            max_instances=1,
            coalesce=True,
            next_run_time=first_run,
        )
        log.info(
            "parser_enabled",
            interval_minutes=settings.parser_interval_minutes,
            validation_interval_hours=SOURCE_VALIDATION_INTERVAL_HOURS,
        )
    else:
        log.info("parser_disabled_or_not_ready", parser_enabled=settings.parser_enabled, parser_ready=settings.parser_ready)

    try:
        await prepare_polling(bot)
        await startup_self_check(bot=bot, dispatcher=dispatcher, settings=settings, db_revision=db_revision)
        scheduler.start()
        await dispatcher.start_polling(bot)
    except Exception:
        log.exception("polling_loop_failed")
        raise
    finally:
        scheduler.shutdown(wait=False)
        if telegram_client:
            await telegram_client.disconnect()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("shutdown_requested")
    except Exception:
        log.exception("application_stopped_with_error")
        raise
