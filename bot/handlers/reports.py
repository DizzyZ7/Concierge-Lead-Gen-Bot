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
OUTCOME_STATUSES = {"lead", "commented"}
OPEN_STATUSES = {"pending", "approved", "queued_by_limit", "sent_to_reviewer"}


def clamp_days(value: str | None, default: int = 7) -> int:
    if not value:
        return default
    try:
        days = int(value)
    except ValueError:
        return default
    return max(1, min(days, 90))


def quality_recommendation(
    *,
    total: int,
    leads: int,
    commented: int,
    noise: int,
    open_items: int,
) -> str:
    if total < 3:
        return "нужно больше данных"
    noise_rate = noise / total
    outcome_rate = (leads + commented) / total
    open_rate = open_items / total
    if noise_rate >= 0.60:
        return "шумный: поднять min_score или добавить стоп-слова"
    if open_rate >= 0.50:
        return "много незакрытого: проверить лимит и reviewer-очередь"
    if leads > 0 or outcome_rate >= 0.25:
        return "сильный: держать в мониторинге, при необходимости расширить лимит"
    return "наблюдать и уточнять фильтры"


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


async def render_source_quality(session_factory: async_sessionmaker[AsyncSession], days: int) -> str:
    window_start = datetime.now(timezone.utc) - timedelta(days=days)
    async with session_factory() as session:
        rows = await session.execute(
            select(
                TargetChannel.channel_username,
                TargetChannel.channel_title,
                ParsedPost.status,
                func.count(ParsedPost.id),
            )
            .join(ParsedPost, ParsedPost.channel_id == TargetChannel.id)
            .where(ParsedPost.created_at >= window_start)
            .group_by(TargetChannel.channel_username, TargetChannel.channel_title, ParsedPost.status)
        )

    grouped: dict[tuple[str, str | None], dict[str, int]] = defaultdict(dict)
    for username, title, status, count in rows.all():
        grouped[(username, title)][status] = count
    if not grouped:
        return f"За последние {days} дн. по источникам пока нет постов."

    scored: list[tuple[int, float, str, str | None, int, int, int, int, int, str]] = []
    for (username, title), counts in grouped.items():
        total = sum(counts.values())
        leads = counts.get("lead", 0)
        commented = counts.get("commented", 0)
        noise = sum(counts.get(status, 0) for status in BAD_STATUSES)
        open_items = sum(counts.get(status, 0) for status in OPEN_STATUSES)
        outcome_rate = round(((leads + commented) / total) * 100, 1) if total else 0.0
        recommendation = quality_recommendation(
            total=total,
            leads=leads,
            commented=commented,
            noise=noise,
            open_items=open_items,
        )
        scored.append((leads, outcome_rate, username, title, total, commented, noise, open_items, counts.get("processing_failed", 0), recommendation))

    scored.sort(key=lambda item: (item[0], item[1], item[4]), reverse=True)
    lines = [f"Качество источников — последние {days} дн.", ""]
    for leads, outcome_rate, username, title, total, commented, noise, open_items, failed, recommendation in scored[:20]:
        display_name = f"{username} — {title}" if title else username
        lines.append(display_name)
        lines.append(
            f"  постов: {total} | лидов: {leads} | комментариев: {commented} | "
            f"исход: {outcome_rate}% | шум: {noise} | открыто: {open_items} | ошибок: {failed}"
        )
        lines.append(f"  рекомендация: {recommendation}")
    return "\n".join(lines)


@router.message(Command("daily_report"))
async def daily_report_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_daily_report(session_factory))


@router.message(Command("channel_stats"))
async def channel_stats_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_channel_stats(session_factory))


@router.message(Command("source_quality"))
async def source_quality_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=1)
    days = clamp_days(parts[1] if len(parts) == 2 else None)
    await message.answer(await render_source_quality(session_factory, days))


@router.callback_query(F.data == "nav:daily_report")
async def daily_report_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await callback.message.answer(await render_daily_report(session_factory))


@router.callback_query(F.data == "nav:channel_stats")
async def channel_stats_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await callback.message.answer(await render_channel_stats(session_factory))
