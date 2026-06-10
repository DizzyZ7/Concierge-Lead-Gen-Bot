from __future__ import annotations

import asyncio

from bot.main import create_bot, create_dispatcher
from core.config import get_settings
from core.logger import setup_logging
from core.scheduler import create_scheduler
from db.session import create_engine, create_session_factory
from services.ai import AIService
from services.reviewer_dispatcher import ReviewerDispatcher


async def main() -> None:
    setup_logging()
    settings = get_settings()
    engine = create_engine(settings.database_url)
    session_factory = create_session_factory(engine)
    bot = create_bot(settings)
    ai_service = AIService(settings)
    dispatcher = create_dispatcher(settings=settings, session_factory=session_factory, ai_service=ai_service)
    reviewer = ReviewerDispatcher(bot=bot, session_factory=session_factory, settings=settings)

    scheduler = create_scheduler(settings)
    scheduler.add_job(reviewer.run_once, "interval", minutes=1, id="reviewer_dispatcher", max_instances=1, coalesce=True)
    scheduler.start()

    try:
        await dispatcher.start_polling(bot)
    finally:
        scheduler.shutdown(wait=False)
        await bot.session.close()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
