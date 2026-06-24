from __future__ import annotations

from asyncio import Lock

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.all_handlers import build_router
from bot.middlewares.admin_check import AdminCheckMiddleware
from core.config import Settings
from services.ai import AIService
from services.runtime_ops import RuntimeOps


def create_bot(app_settings: Settings) -> Bot:
    return Bot(token=app_settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    ai_service: AIService,
    runtime_ops: RuntimeOps,
    source_workflow_lock: Lock,
) -> Dispatcher:
    dispatcher = Dispatcher(
        settings=settings,
        session_factory=session_factory,
        ai_service=ai_service,
        runtime_ops=runtime_ops,
        source_workflow_lock=source_workflow_lock,
    )
    middleware = AdminCheckMiddleware(settings)
    dispatcher.message.middleware(middleware)
    dispatcher.callback_query.middleware(middleware)
    dispatcher.include_router(build_router(settings))
    return dispatcher
