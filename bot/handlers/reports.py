from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta, timezone

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from bot.presentation import intent_label, status_label
from db.models import ParsedPost, TargetChannel

router = Router(name=__name__)

IMPORTANT_STATUSES = [
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

GOOD_STATUSES = {"lead", "commented", "content_idea", "saved", "reviewer_done"}
BAD_STATUSES = {"not_relevant", "skipped"}


async def render_daily_report(session_factory: async_sessionmaker[AsyncSession]) -> str:
    window_start = datetime.now(timezone.utc) - timedelta(hours=24)
    async with session_factory() as session:
        status_rows = await session.execute(
            select(ParsedPost.status, func.count(ParsedPost.id))
            .where(ParsedPost.created_at >= window_start)
            .group_by(ParsedPost.status)
        )
        intent_rows = await session.execute(
            select(ParsedPost.intent, func.count(ParsedPost.id))
            .where(ParsedPost.created_at >= window_start)
            .group_by(ParsedPost.intent)
            .order_by(func.count(ParsedPost.id).desc())
            .limit(10)
        )
        top_channel_rows = await session.execute(
            select(TargetChannel.channel_username, func.count(ParsedPost.id))
            .join(ParsedPost, ParsedPost.channel_id == TargetChannel.id)
            .where(ParsedPost.created_at >= window_start, ParsedPost.status.in_(GOOD_STATUSES))
            .group_by(TargetChannel.channel_username)
            .order_by(func.count(ParsedPost.id).desc())
            .limit(5)
        )
    status_counts = {status: count for status, count in status_rows.all()}
    total = sum(status_counts.values())
    useful = sum(status_counts.get(status, 0) for status in GOOD_STATUSES)
    bad = sum(status_counts.get(status, 0) for status in BAD_STATUSES)
    queued_by_limit = status_counts.get("queued_by_limit", 0)
    failed = status_counts.get("processing_failed", 0)
    usefulness = round((useful / total) * 100, 1) if total else 0.0
    noise = round((bad / total) * 100, 1) if total else 0.0

    lines = [
        "Thailand Lead Radar — последние 24 часа",
        "",
        f"Новых постов: {total}",
        f"Полезных исходов: {useful} ({usefulness}%)",
        f"Шум: {bad} ({noise}%)",
        f"Отложено по дневным лимитам: {queued_by_limit}",
        f"Ошибок обработки: {failed}",
        "",
        "Статусы:",
    ]
    for status in IMPORTANT_STATUSES:
        lines.append(f"- {status_label(status)}: {status_counts.get(status, 0)}")

    intents = intent_rows.all()
    if intents:
        lines.extend(["", "Топ категорий:"])
        for intent, count in intents:
            lines.append(f"- {intent_label(intent)}: {count}")

    channels = top_channel_rows.all()
    if channels:
        lines.extend(["", "Лучшие каналы:"])
        for channel, count in channels:
            lines.append(f"- {channel}: {count}")

    return "\n".join(lines)


async def render_channel_stats(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        rows = await session.execute(
            select(TargetChannel.channel_username, ParsedPost.status, func.count(ParsedPost.id))
            .join(ParsedPost, ParsedPost.channel_id == TargetChannel.id)
            .group_by(TargetChannel.channel_username, ParsedPost.status)
            .order_by(TargetChannel.channel_username)
        )
    grouped: dict[str, dict[str, int]] = defaultdict(dict)
    for channel, status, count in rows.all():
        grouped[channel][status] = count

    if not grouped:
        return "Статистики по каналам пока нет."

    scored = []
    for channel, counts in grouped.items():
        total = sum(counts.values())
        useful = sum(counts.get(status, 0) for status in GOOD_STATUSES)
        bad = sum(counts.get(status, 0) for status in BAD_STATUSES)
        score = round((useful / total) * 100, 1) if total else 0.0
        scored.append((score, channel, total, useful, bad, counts))

    scored.sort(reverse=True)
    lines = ["Качество каналов — за все время", ""]
    for score, channel, total, useful, bad, counts in scored[:20]:
        lines.append(f"{channel}")
        lines.append(f"  качество: {score}% | всего: {total} | полезно: {useful} | шум: {bad}")
        compact = ", ".join(
            f"{status_label(status)}:{counts.get(status, 0)}"
            for status in IMPORTANT_STATUSES
            if counts.get(status, 0)
        )
        lines.append(f"  статусы: {compact or '-'}")
    return "\n".join(lines)


@router.message(Command("daily_report"))
async def daily_report_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_daily_report(session_factory))


@router.message(Command("channel_stats"))
async def channel_stats_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_channel_stats(session_factory))


@router.callback_query(F.data == "nav:daily_report")
async def daily_report_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await callback.message.answer(await render_daily_report(session_factory))


@router.callback_query(F.data == "nav:channel_stats")
async def channel_stats_callback(callback: CallbackQuery, session_factory: async_sessionmaker[Async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await callback.message.answer(await render_channel_stats(session_factory))
