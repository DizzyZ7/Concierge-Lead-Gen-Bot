from __future__ import annotations

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import main_menu
from db import queries

router = Router(name=__name__)

HELP_TEXT = """Commands

Main:
/start
/help
/health
/stats
/settings
/pause
/resume

Channels:
/channels
/add_channel @manual thailand relocation
/set_channel_limit 1 5

Items:
/add_item <channel_id> <url_or_dash> <text>
/pending
/edit_draft <post_id> <new text>
/review_queue

Leads:
/leads
/add_lead <tg_user_id_or_0> <username_or_dash> <geo> <intent> <notes>
/lead_status <lead_id> <new|contacted|converted|dead>
/deal <lead_id> <amount>

Templates:
/templates
/add_template <geo> <category> <text>
/disable_template <template_id>
"""


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


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("health"))
async def health_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    try:
        async with session_factory() as session:
            await session.execute(text("select 1"))
            paused = await queries.get_setting(session, "paused", "false")
        await message.answer(f"OK\nDatabase: connected\nPaused: {paused}")
    except Exception as error:
        await message.answer(f"Health check failed: {error}")


@router.message(Command("stats"))
async def stats_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_dashboard(session_factory), reply_markup=main_menu())


@router.callback_query(F.data == "nav:dashboard")
async def dashboard_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await callback.message.answer(await render_dashboard(session_factory), reply_markup=main_menu())
