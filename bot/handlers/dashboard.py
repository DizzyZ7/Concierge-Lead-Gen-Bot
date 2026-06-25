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
from bot.ui import edit_callback_message
from core.config import Settings
from db import queries
from db.models import ParsedPost
from services.runtime_ops import get_component_runtime_state, parse_iso

router = Router(name=__name__)

ADMIN_HELP_TEXT = """Команды администратора

Основное:
/start
/help
/health
/launch_check
/stats
/queue_stats
/daily_report
/channel_stats
/source_quality [days]
/settings
/pause
/resume

Каналы и мониторинг:
/channels
/add_channel @manual thailand relocation
/validate_channels
/set_channel_limit 1 5
/set_channel_delay 1 0 0
/set_channel_min_score 1 0.70
/set_channel_intents 1 realty,visa,relocation
/set_channel_blocklist 1 crypto,casino
/reset_channel_cursor <channel_id>
/scan_now
/promote_limit_queue

Посты:
/add_item <channel_id> <url_or_dash> <text>
/pending
/approved_queue
/limit_queue
/review_queue
/reviewer_backlog [hours]
/saved_queue
/content_ideas
/failed_queue
/source <post_id>
/draft <post_id>
/dispatch_now <post_id>
/edit_draft <post_id> <new text>

Лиды:
/leads [new|contacted|converted|dead|all]
/lead <lead_id>
/funnel
/followups [hours]
/add_lead <tg_user_id_or_0> <username_or_dash> <geo> <intent> <notes>
/lead_status <lead_id> <new|contacted|converted|dead>
/lead_note <lead_id> <text>
/deal <lead_id> <commission_amount>

Контекст услуг:
/business_context
/set_business_context <описание услуг>

Шаблоны:
/templates
/add_template <geo> <category> <text>
/disable_template <template_id>
"""

REVIEWER_HELP_TEXT = """Команды reviewer-а

Рабочие очереди:
/start
/help
/stats
/daily_report
/pending
/approved_queue
/review_queue
/reviewer_backlog [hours]
/saved_queue
/content_ideas
/source <post_id>
/draft <post_id>
/edit_draft <post_id> <new text>

По карточкам можно отметить: комментарий написан, стал лидом, идея, нерелевантно, сохранить, пропустить или обработано.

Настройки каналов, запуск parser-а, системные операции, CRM-лиды и финансы доступны администратору.
"""


def is_admin_user(user_id: int | None, settings: Settings) -> bool:
    return user_id is not None and user_id in settings.admin_ids


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


async def render_dashboard(session_factory: async_sessionmaker[AsyncSession], *, is_admin: bool) -> str:
    async with session_factory() as session:
        stats = await queries.get_today_stats(session)

    if not is_admin:
        return (
            "Рабочая сводка за сегодня\n\n"
            f"Обработано постов: {stats.posts_parsed}\n"
            f"Карточек отправлено reviewer-ам: {stats.drafts_sent}\n"
            f"Отмечено обработанными: {stats.reviewer_done}\n"
            f"AI-черновиков: {stats.ai_drafts}\n"
            f"Шаблонных черновиков: {stats.template_drafts}"
        )

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
async def start_command(message: Message, settings: Settings) -> None:
    is_admin = is_admin_user(message.from_user.id if message.from_user else None, settings)
    await message.answer("Thailand Lead Radar готов к работе.", reply_markup=main_menu(is_admin=is_admin))


@router.message(Command("help"))
async def help_command(message: Message, settings: Settings) -> None:
    is_admin = is_admin_user(message.from_user.id if message.from_user else None, settings)
    await message.answer(ADMIN_HELP_TEXT if is_admin else REVIEWER_HELP_TEXT)


@router.message(Command("health"))
async def health_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    if not is_admin_user(message.from_user.id if message.from_user else None, settings):
        await message.answer("Проверка здоровья системы доступна только администратору.")
        return
    try:
        zone = local_zone(settings.timezone)
        async with session_factory() as session:
            await session.execute(text("select 1"))
            paused = await queries.get_setting(session, "paused", "false")
            parser_runtime = await get_component_runtime_state(session, "parser")
            reviewer_runtime = await get_component_runtime_state(session, "reviewer")
            limit_queue_runtime = await get_component_runtime_state(session, "limit_queue")
            source_validation_runtime = await get_component_runtime_state(session, "source_validation")

        parser_line, parser_stale = format_runtime_component(
            "Parser", parser_runtime, timedelta(minutes=max(settings.parser_interval_minutes * 3, 15)), zone
        )
        reviewer_line, reviewer_stale = format_runtime_component(
            "Reviewer", reviewer_runtime, timedelta(minutes=5), zone
        )
        limit_queue_line, limit_queue_stale = format_runtime_component(
            "Лимитная очередь", limit_queue_runtime, timedelta(minutes=15), zone
        )
        source_validation_line, source_validation_stale = format_runtime_component(
            "Проверка источников", source_validation_runtime, timedelta(hours=48), zone
        )
        parser_required = settings.parser_enabled
        overall = (
            "⚠️ Нужна проверка"
            if reviewer_stale
            or limit_queue_stale
            or (parser_required and (parser_stale or source_validation_stale))
            else "✅ Система работает"
        )
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
            limit_queue_line,
            source_validation_line,
        ]
        await message.answer("\n".join(lines))
    except Exception as error:
        await message.answer(f"Проверка здоровья не прошла: {error}")


@router.message(Command("stats"))
async def stats_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    is_admin = is_admin_user(message.from_user.id if message.from_user else None, settings)
    await message.answer(await render_dashboard(session_factory, is_admin=is_admin), reply_markup=main_menu(is_admin=is_admin))


@router.message(Command("queue_stats"))
async def queue_stats_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    if not is_admin_user(message.from_user.id if message.from_user else None, settings):
        await message.answer("Статистика статусов очередей доступна только администратору.")
        return
    await message.answer(await render_queue_stats(session_factory))


@router.callback_query(F.data == "nav:dashboard")
async def dashboard_callback(
    callback: CallbackQuery,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    await callback.answer()
    is_admin = is_admin_user(callback.from_user.id if callback.from_user else None, settings)
    await edit_callback_message(
        callback,
        await render_dashboard(session_factory, is_admin=is_admin),
        reply_markup=main_menu(is_admin=is_admin),
    )
