from __future__ import annotations

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.handlers import channels, dashboard, leads, posts, review_extras, saved, settings as settings_handlers, source_view, templates
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
    dispatcher.include_router(dashboard.router)
    dispatcher.include_router(channels.router)
    dispatcher.include_router(posts.router)
    dispatcher.include_router(review_extras.router)
    dispatcher.include_router(source_view.router)
    dispatcher.include_router(saved.router)
    dispatcher.include_router(leads.router)
    dispatcher.include_router(templates.router)
    dispatcher.include_router(settings_handlers.router)
    return dispatcher
