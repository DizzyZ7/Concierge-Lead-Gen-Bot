from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers.all_handlers import build_router
from bot.middlewares.admin_check import AdminCheckMiddleware
from core.config import Settings
from services.ai import AIService


def create_bot(app_settings: Settings) -> Bot:
    return Bot(token=app_settings.bot_token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


def create_dispatcher(
    *,
    settings: Settings,
    session_factory: async_sessionmaker[AsyncSession],
    ai_service: AIService,
) -> Dispatcher:
    dispatcher = Dispatcher(session_factory=session_factory, ai_service=ai_service)
    middleware = AdminCheckMiddleware(settings)
    dispatcher.message.middleware(middleware)
    dispatcher.callback_query.middleware(middleware)
    dispatcher.include_router(build_router())
    return dispatcher
