from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import main_menu
from db import queries

router = Router(name=__name__)


async def render_dashboard(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        stats = await queries.get_today_stats(session)
    return (
        "Dashboard today\n\n"
        f"Parsed items: {stats.posts_parsed}\n"
        f"Drafts sent: {stats.drafts_sent}\n"
        f"Reviewed: {stats.reviewer_done}\n"
        f"New leads: {stats.leads_received}\n"
        f"Deals closed: {stats.deals_closed}\n"
        f"Revenue: {stats.revenue}\n"
        f"AI drafts: {stats.ai_drafts}\n"
        f"Template drafts: {stats.template_drafts}\n"
        f"AI failures: {stats.ai_failures}"
    )


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    await message.answer("Concierge reviewer bot is ready.", reply_markup=main_menu())


@router.message(Command("stats"))
async def stats_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_dashboard(session_factory), reply_markup=main_menu())


@router.callback_query(F.data == "nav:dashboard")
async def dashboard_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await callback.message.answer(await render_dashboard(session_factory), reply_markup=main_menu())
