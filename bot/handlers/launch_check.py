from __future__ import annotations

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from core.config import Settings
from core.reviewer_access import reviewer_user_ids
from db import queries
from db.models import ParsedPost, TargetChannel
from services.channel_validation import is_channel_validation_fresh
from services.runtime_ops import get_component_runtime_state, parse_iso

router = Router(name=__name__)


def mark(ok: bool) -> str:
    return "✅" if ok else "⚠️"


async def render_launch_check(session_factory: async_sessionmaker[AsyncSession], settings: Settings) -> str:
    db_ok = False
    paused = "unknown"
    active_channels = 0
    unvalidated_channels = 0
    failed_items = 0
    queued_by_limit = 0
    parser_runtime: dict[str, str | None] = {}
    reviewer_runtime: dict[str, str | None] = {}
    limit_queue_runtime: dict[str, str | None] = {}

    try:
        async with session_factory() as session:
            await session.execute(text("select 1"))
            db_ok = True
            paused = await queries.get_setting(session, "paused", "false") or "false"
            active_channel_rows = list(
                (
                    await session.scalars(
                        select(TargetChannel)
                        .where(TargetChannel.is_active.is_(True))
                        .order_by(TargetChannel.id)
                    )
                ).all()
            )
            active_channels = len(active_channel_rows)
            unvalidated_channels = sum(
                1
                for channel in active_channel_rows
                if not is_channel_validation_fresh(
                    channel.last_validation_at,
                    channel.last_validation_error,
                )
            )
            failed_items = int(
                await session.scalar(
                    select(func.count(ParsedPost.id)).where(ParsedPost.status == "processing_failed")
                )
                or 0
            )
            queued_by_limit = int(
                await session.scalar(
                    select(func.count(ParsedPost.id)).where(ParsedPost.status == "queued_by_limit")
                )
                or 0
            )
            parser_runtime = await get_component_runtime_state(session, "parser")
            reviewer_runtime = await get_component_runtime_state(session, "reviewer")
            limit_queue_runtime = await get_component_runtime_state(session, "limit_queue")
    except Exception as error:
        return f"❌ Launch check не прошел: база данных недоступна ({error.__class__.__name__})."

    parser_config_ok = settings.parser_enabled and settings.parser_ready
    reviewers_ok = bool(settings.reviewer_chat_ids)
    reviewer_users = reviewer_user_ids(settings)
    group_delivery_enabled = any(chat_id < 0 for chat_id in settings.reviewer_chat_ids)
    reviewer_access_ok = not group_delivery_enabled or bool(reviewer_users)
    channels_ok = active_channels > 0
    validation_ok = channels_ok and unvalidated_channels == 0
    unpaused_ok = paused != "true"
    failures_ok = failed_items == 0
    required_ok = all(
        [
            db_ok,
            parser_config_ok,
            reviewers_ok,
            reviewer_access_ok,
            channels_ok,
            validation_ok,
            unpaused_ok,
            failures_ok,
        ]
    )

    parser_heartbeat = parse_iso(parser_runtime.get("last_success_at"))
    reviewer_heartbeat = parse_iso(reviewer_runtime.get("last_success_at"))
    limit_queue_heartbeat = parse_iso(limit_queue_runtime.get("last_success_at"))
    parser_heartbeat_text = parser_heartbeat.strftime("%d.%m %H:%M UTC") if parser_heartbeat else "еще нет"
    reviewer_heartbeat_text = reviewer_heartbeat.strftime("%d.%m %H:%M UTC") if reviewer_heartbeat else "еще нет"
    limit_queue_heartbeat_text = limit_queue_heartbeat.strftime("%d.%m %H:%M UTC") if limit_queue_heartbeat else "еще нет"
    reviewer_access_text = (
        f"пользователей: {len(reviewer_users)}"
        if reviewer_access_ok
        else "для group-chat добавь REVIEWER_USER_IDS"
    )

    lines = [
        "✅ Можно запускать" if required_ok else "⚠️ Перед запуском нужно исправить пункты ниже",
        "",
        f"{mark(db_ok)} База данных: {'доступна' if db_ok else 'недоступна'}",
        f"{mark(parser_config_ok)} Parser: {'готов' if parser_config_ok else 'не настроен или выключен'}",
        f"{mark(reviewers_ok)} Reviewer-чаты: {len(settings.reviewer_chat_ids)}",
        f"{mark(reviewer_access_ok)} Reviewer-доступ: {reviewer_access_text}",
        f"{mark(channels_ok)} Активные каналы: {active_channels}",
        f"{mark(validation_ok)} Валидация каналов: {'все свежие' if validation_ok else f'требуют проверки: {unvalidated_channels}'}",
        f"{mark(unpaused_ok)} Пауза: {'нет' if unpaused_ok else 'включена'}",
        f"{mark(failures_ok)} Ошибки обработки: {failed_items}",
        f"ℹ️ Очередь сверх дневного лимита: {queued_by_limit}",
        f"{'✅' if settings.claude_ready else 'ℹ️'} Claude: {'готов' if settings.claude_ready else 'fallback-режим'}",
        "",
        f"Parser heartbeat: {parser_heartbeat_text}",
        f"Reviewer heartbeat: {reviewer_heartbeat_text}",
        f"Лимитная очередь heartbeat: {limit_queue_heartbeat_text}",
    ]
    return "\n".join(lines)


@router.message(Command("launch_check"))
async def launch_check_command(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    settings: Settings,
) -> None:
    await message.answer(await render_launch_check(session_factory, settings))
