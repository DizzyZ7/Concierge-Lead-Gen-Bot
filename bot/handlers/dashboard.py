from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.keyboards.inline import main_menu
from bot.presentation import status_label
from core.config import Settings
from db import queries
from db.models import ParsedPost
from services.runtime_ops import get_component_runtime_state, parse_iso

router = Router(name=__name__)

HELP_TEXT = """Команды

Основное:
/start
/help
/health
/stats
/queue_stats
/daily_report
/channel_stats
/settings
/pause
/resume

Каналы:
/channels
/add_channel @manual thailand relocation
/set_channel_limit 1 5
/set_channel_delay 1 0 0
/set_channel_min_score 1 0.70
/set_channel_intents 1 realty,visa,relocation
/set_channel_blocklist 1 crypto,casino

Посты:
/add_item <channel_id> <url_or_dash> <text>
/pending
/approved_queue
/limit_queue
/review_queue
/saved_queue
/content_ideas
/failed_queue
/source <post_id>
/draft <post_id>
/dispatch_now <post_id>
/edit_draft <post_id> <new text>

Лиды:
/leads
/add_lead <tg_user_id_or_0> <username_or_dash> <geo> <intent> <notes>
/lead_status <lead_id> <new|contacted|converted|dead>
/deal <lead_id> <amount>

Шаблоны:
/templates
/add_template <geo> <category> <text>
/disable_template <template_id>
"""


def local_zone(timezone_name: str):
    try:
        return ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        return timezone.utc


def format_runtime_component(name: str, state: dict[str, str | None], stale_after: timedelta, zone) -> tuple[str, bool]:
    last_success = parse_iso(state.get("last_success_at"))
    last_error = parse_iso(state.get("last_error_at"))
    now = datetime.now(timezone.utc)
    if last_success is None:
        status = "нет данных"
        stale = True
        timestamp = "-"
    else:
        stale = now - last_success > stale_after
        status = "устарело" if stale else "работает"
        timestamp = last_success.astimezone(zone).strftime("%d.%m %H:%M:%S")

    lines = [f"{name}: {status} ({timestamp})"]
    details = state.get("last_details")
    if details:
        lines.append(f"  Детали: {details}")
    if last_error and (last_success is None or last_error >= last_success):
        error_time = last_error.astimezone(zone).strftime("%d.%m %H:%M:%S")
        lines.append(f"  Последняя ошибка: {error_time} — {state.get('last_error') or '-'}")
    return "\n".join(lines), stale


async def render_dashboard(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        stats = await queries.get_today_stats(session)
    return (
        "Главная за сегодня\n\n"
        f"Обработано постов: {stats.posts_parsed}\n"
        f"Черновиков отправлено: {stats.drafts_sent}\n"
        f"Отмечено обработанными: {stats.reviewer_done}\n"
        f"Новых лидов: {stats.leads_received}\n"
        f"Сделок: {stats.deals_closed}\n"
        f"Доход: {stats.revenue}\n"
        f"AI-черновиков: {stats.ai_drafts}\n"
        f"Шаблонных черновиков: {stats.template_drafts}\n"
        f"Сбоев AI: {stats.ai_failures}"
    )


async def render_queue_stats(session_factory: async_sessionmaker[AsyncSession]) -> str:
    statuses = [
        "pending",
        "approved",
        "queued_by_limit",
        "sent_to_reviewer",
        "saved",
        "content_idea",
        "commented",
        "lead",
        "not_relevant",
        "reviewer_done",
        "processing_failed",
        "skipped",
    ]
    async with session_factory() as session:
        rows = await session.execute(
            select(ParsedPost.status, func.count(ParsedPost.id)).group_by(ParsedPost.status)
        )
    counts = {status: count for status, count in rows.all()}
    lines = ["Статусы очередей"]
    for status in statuses:
        lines.append(f"{status_label(status)}: {counts.get(status, 0)}")
    return "\n".join(lines)


def parser_config_state(settings: Settings) -> str:
    if settings.parser_ready:
        return "включен"
    if settings.parser_enabled:
        return "ошибка настройки"
    return "выключен"


@router.message(Command("start"))
async def start_command(message: Message) -> None:
    await message.answer("Thailand Lead Radar готов к работе.", reply_markup=main_menu())


@router.message(Command("help"))
async def help_command(message: Message) -> None:
    await message.answer(HELP_TEXT)


@router.message(Command("health"))
async def health_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    try:
        zone = local_zone(settings.timezone)
        async with session_factory() as session:
            await session.execute(text("select 1"))
            paused = await queries.get_setting(session, "paused", "false")
            parser_runtime = await get_component_runtime_state(session, "parser")
            reviewer_runtime = await get_component_runtime_state(session, "reviewer")

        parser_line, parser_stale = format_runtime_component(
            "Parser", parser_runtime, timedelta(minutes=max(settings.parser_interval_minutes * 3, 15)), zone
        )
        reviewer_line, reviewer_stale = format_runtime_component(
            "Reviewer", reviewer_runtime, timedelta(minutes=5), zone
        )
        parser_required = settings.parser_enabled
        overall = "⚠️ Нужна проверка" if reviewer_stale or (parser_required and parser_stale) else "✅ Система работает"
        lines = [
            overall,
            "",
            "База данных: подключена",
            f"Пауза: {'да' if paused == 'true' else 'нет'}",
            f"Parser config: {parser_config_state(settings)}",
            f"Claude: {'готов' if settings.claude_ready else 'fallback-режим'}",
            f"Reviewer-чатов: {len(settings.reviewer_chat_ids)}",
            f"Автоматизация: {settings.automation_level}",
            f"Outbound: {'включен' if settings.outbound_ready else 'выключен'}",
            "",
            parser_line,
            reviewer_line,
        ]
        await message.answer("\n".join(lines))
    except Exception as error:
        await message.answer(f"Проверка здоровья не прошла: {error}")


@router.message(Command("stats"))
async def stats_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_dashboard(session_factory), reply_markup=main_menu())


@router.message(Command("queue_stats"))
async def queue_stats_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_queue_stats(session_factory))


@router.callback_query(F.data == "nav:dashboard")
async def dashboard_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await callback.message.answer(await render_dashboard(session_factory), reply_markup=main_menu())
