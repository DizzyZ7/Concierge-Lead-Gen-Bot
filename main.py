from __future__ import annotations

import asyncio
from pathlib import Path

from telethon import TelegramClient

from bot.main import create_bot, create_dispatcher
from core.config import get_settings
from core.logger import get_logger, setup_logging
from core.scheduler import create_scheduler
from db.session import create_engine, create_session_factory
from services.ai import AIService
from services.limit_queue_promoter import LimitQueuePromoter
from services.parser import ParserService
from services.reviewer_dispatcher import ReviewerDispatcher
from services.runtime_ops import RuntimeOps

log = get_logger(__name__)


async def build_parser(settings, session_factory, ai_service, runtime_ops) -> tuple[TelegramClient | None, ParserService | None]:
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

    async def run_limit_queue_promoter() -> None:
        async with source_workflow_lock:
            await limit_queue_promoter.run_once()

    async def run_parser() -> None:
        if not parser:
            return
        async with source_workflow_lock:
            await parser.run_once()

    scheduler = create_scheduler(settings)
    scheduler.add_job(reviewer.run_once, "interval", minutes=1, id="reviewer_dispatcher", max_instances=1, coalesce=True)
    scheduler.add_job(
        run_limit_queue_promoter,
        "interval",
        minutes=5,
        id="limit_queue_promoter",
        max_instances=1,
        coalesce=True,
    )
    if parser:
        scheduler.add_job(
            run_parser,
            "interval",
            minutes=settings.parser_interval_minutes,
            id="read_only_parser",
            max_instances=1,
            coalesce=True,
        )
        log.info("parser_enabled", interval_minutes=settings.parser_interval_minutes)
    scheduler.start()

    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        if telegram_client:
            await telegram_client.disconnect()
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
