from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.presentation import intent_label, status_label
from db import queries
from db.models import Lead
from services.deals import record_deal_revenue

router = Router(name=__name__)

LEAD_STATUSES = {"new", "contacted", "converted", "dead"}
OPEN_LEAD_STATUSES = {"new", "contacted"}
DEFAULT_FOLLOWUP_HOURS = 48
MAX_FOLLOWUP_HOURS = 24 * 30


def as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)


def format_activity(value: datetime | None) -> str:
    normalized = as_utc(value)
    if normalized is None:
        return "-"
    age = max(0, int((datetime.now(timezone.utc) - normalized).total_seconds() // 3600))
    return f"{normalized.strftime('%d.%m %H:%M UTC')} ({age} ч. назад)"


def render_lead(lead: Lead) -> str:
    username = f"@{lead.tg_username}" if lead.tg_username else "-"
    source_post = lead.source_post
    source_text = f"#{source_post.id}" if source_post else "-"
    source_url = source_post.post_url if source_post else None
    return (
        f"Лид #{lead.id}\n"
        f"Статус: {escape(status_label(lead.status))}\n"
        f"Telegram ID: {lead.tg_user_id or '-'}\n"
        f"Username: {escape(username)}\n"
        f"Имя: {escape(lead.first_name or '-')}\n"
        f"Гео: {escape(lead.geo or '-')}\n"
        f"Категория: {escape(intent_label(lead.intent))}\n"
        f"Источник: {escape(source_text)}\n"
        f"Ссылка на источник: {escape(source_url or '-')}\n"
        f"Доход / комиссия: {lead.deal_amount or '-'}\n"
        f"Последняя активность: {escape(format_activity(lead.updated_at or lead.created_at))}\n"
        f"Заметка: {escape(lead.notes or '-')}"
    )


async def get_lead(session: AsyncSession, lead_id: int) -> Lead | None:
    return await session.scalar(
        select(Lead)
        .options(selectinload(Lead.source_post))
        .where(Lead.id == lead_id)
    )


async def send_leads(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    status: str | None = "new",
) -> None:
    async with session_factory() as session:
        statement = select(Lead).options(selectinload(Lead.source_post)).order_by(Lead.updated_at.desc()).limit(30)
        if status:
            statement = statement.where(Lead.status == status)
        result = await session.scalars(statement)
        leads = result.all()
    if not leads:
        label = status_label(status) if status else "всех статусов"
        await message.answer(f"Лидов со статусом «{label}» пока нет.")
        return
    for lead in leads:
        await message.answer(render_lead(lead), disable_web_page_preview=True)


async def render_funnel(session_factory: async_sessionmaker[AsyncSession]) -> str:
    async with session_factory() as session:
        rows = await session.execute(select(Lead.status, func.count(Lead.id)).group_by(Lead.status))
    counts = {status: count for status, count in rows.all()}
    total = sum(counts.values())
    new = counts.get("new", 0)
    contacted = counts.get("contacted", 0)
    converted = counts.get("converted", 0)
    dead = counts.get("dead", 0)
    active = new + contacted
    conversion = round((converted / total) * 100, 1) if total else 0.0
    contact_rate = round(((contacted + converted) / total) * 100, 1) if total else 0.0
    return (
        "Воронка лидов\n\n"
        f"Всего: {total}\n"
        f"Новые: {new}\n"
        f"В работе: {contacted}\n"
        f"Активные: {active}\n"
        f"Сделки: {converted}\n"
        f"Неактуальные: {dead}\n\n"
        f"Контакт достигнут: {contact_rate}%\n"
        f"Конверсия в сделку: {conversion}%"
    )


async def send_followups(
    message: Message,
    session_factory: async_sessionmaker[AsyncSession],
    followup_hours: int,
) -> None:
    cutoff = datetime.now(timezone.utc) - timedelta(hours=followup_hours)
    async with session_factory() as session:
        result = await session.scalars(
            select(Lead)
            .options(selectinload(Lead.source_post))
            .where(Lead.status.in_(OPEN_LEAD_STATUSES), Lead.updated_at <= cutoff)
            .order_by(Lead.updated_at.asc())
            .limit(30)
        )
        leads = result.all()
    if not leads:
        await message.answer(f"Лидов без активности более {followup_hours} ч. нет.")
        return

    lines = [f"Follow-up: нет активности более {followup_hours} ч.", ""]
    for lead in leads:
        source = f"#{lead.source_post.id}" if lead.source_post else "-"
        username = f"@{lead.tg_username}" if lead.tg_username else "-"
        lines.append(
            f"Лид #{lead.id} | {status_label(lead.status)} | {intent_label(lead.intent)}\n"
            f"Контакт: {username}\n"
            f"Источник: {source}\n"
            f"Последняя активность: {format_activity(lead.updated_at or lead.created_at)}"
        )
    await message.answer("\n\n".join(lines), disable_web_page_preview=True)


@router.message(Command("leads"))
async def leads_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=1)
    requested_status = parts[1].lower().strip() if len(parts) == 2 else "new"
    if requested_status == "all":
        await send_leads(message, session_factory, None)
        return
    if requested_status not in LEAD_STATUSES:
        await message.answer("Формат: /leads [new|contacted|converted|dead|all]")
        return
    await send_leads(message, session_factory, requested_status)


@router.message(Command("lead"))
async def lead_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2 or not parts[1].isdigit():
        await message.answer("Формат: /lead <lead_id>")
        return
    async with session_factory() as session:
        lead = await get_lead(session, int(parts[1]))
    await message.answer(render_lead(lead) if lead else "Лид не найден.", disable_web_page_preview=True)


@router.message(Command("funnel"))
async def funnel_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await message.answer(await render_funnel(session_factory))


@router.message(Command("followups"))
async def followups_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=1)
    followup_hours = DEFAULT_FOLLOWUP_HOURS
    if len(parts) == 2:
        if not parts[1].isdigit():
            await message.answer("Формат: /followups [hours]")
            return
        followup_hours = int(parts[1])
    if followup_hours < 1 or followup_hours > MAX_FOLLOWUP_HOURS:
        await message.answer(f"Укажи значение от 1 до {MAX_FOLLOWUP_HOURS} часов.")
        return
    await send_followups(message, session_factory, followup_hours)


@router.callback_query(F.data == "nav:leads")
async def leads_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_leads(callback.message, session_factory, "new")


@router.message(Command("add_lead"))
async def add_lead_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=5)
    if len(parts) < 6:
        await message.answer("Формат: /add_lead <tg_user_id_or_0> <username_or_dash> <geo> <intent> <notes>")
        return
    user_id = None if parts[1] == "0" else int(parts[1]) if parts[1].isdigit() else None
    username = None if parts[2] == "-" else parts[2].lstrip("@")
    async with session_factory() as session:
        lead = await queries.create_lead(
            session,
            tg_user_id=user_id,
            tg_username=username,
            first_name=None,
            source_post_id=None,
            geo=parts[3],
            intent=parts[4],
            notes=parts[5],
        )
    await message.answer(f"Добавлен лид #{lead.id}.")


@router.message(Command("lead_status"))
async def lead_status_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    status = parts[2].lower() if len(parts) == 3 else ""
    if len(parts) != 3 or not parts[1].isdigit() or status not in LEAD_STATUSES:
        await message.answer("Формат: /lead_status <lead_id> <new|contacted|converted|dead>")
        return
    async with session_factory() as session:
        ok = await queries.update_lead_status(session, int(parts[1]), status)
    await message.answer("Статус обновлен, активность зафиксирована." if ok else "Лид не найден.")


@router.message(Command("lead_note"))
async def lead_note_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Формат: /lead_note <lead_id> <text>")
        return
    lead_id = int(parts[1])
    note = parts[2].strip()
    if not note:
        await message.answer("Заметка не должна быть пустой.")
        return
    timestamp = datetime.now(timezone.utc).strftime("%d.%m %H:%M UTC")
    async with session_factory() as session:
        lead = await session.get(Lead, lead_id)
        if not lead:
            await message.answer("Лид не найден.")
            return
        entry = f"[{timestamp}] {note}"
        lead.notes = f"{lead.notes}\n\n{entry}" if lead.notes else entry
        await session.commit()
    await message.answer("Заметка добавлена, активность обновлена.")


@router.message(Command("deal"))
async def deal_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Формат: /deal <lead_id> <commission_amount>")
        return
    try:
        revenue = Decimal(parts[2].replace(",", "."))
    except InvalidOperation:
        await message.answer("Доход / комиссия должны быть числом.")
        return
    if revenue <= 0:
        await message.answer("Доход / комиссия должны быть больше нуля.")
        return
    async with session_factory() as session:
        result = await record_deal_revenue(session, lead_id=int(parts[1]), revenue=revenue)
    messages = {
        "created": "Сделка и фактический доход сохранены.",
        "updated": "Сумма дохода исправлена, статистика скорректирована.",
        "unchanged": "Сделка уже была сохранена с такой суммой.",
        "missing": "Лид не найден.",
    }
    await message.answer(messages[result])
