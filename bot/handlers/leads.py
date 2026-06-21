from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from bot.presentation import intent_label, status_label
from db import queries
from db.models import Lead

router = Router(name=__name__)


async def send_leads(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        result = await session.scalars(
            select(Lead)
            .options(selectinload(Lead.source_post))
            .where(Lead.status == "new")
            .order_by(Lead.created_at.desc())
            .limit(20)
        )
        leads = result.all()
    if not leads:
        await message.answer("Новых лидов пока нет.")
        return
    for lead in leads:
        username = f"@{lead.tg_username}" if lead.tg_username else "-"
        source_post = lead.source_post
        source_text = f"#{source_post.id}" if source_post else "-"
        source_url = source_post.post_url if source_post else None
        text = (
            f"Лид #{lead.id}\n"
            f"Статус: {escape(status_label(lead.status))}\n"
            f"Telegram ID: {lead.tg_user_id or '-'}\n"
            f"Username: {escape(username)}\n"
            f"Имя: {escape(lead.first_name or '-')}\n"
            f"Гео: {escape(lead.geo or '-')}\n"
            f"Категория: {escape(intent_label(lead.intent))}\n"
            f"Источник: {escape(source_text)}\n"
            f"Ссылка на источник: {escape(source_url or '-')}\n"
            f"Заметка: {escape(lead.notes or '-')}"
        )
        await message.answer(text, disable_web_page_preview=True)


@router.message(Command("leads"))
async def leads_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_leads(message, session_factory)


@router.callback_query(F.data == "nav:leads")
async def leads_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_leads(callback.message, session_factory)


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
    allowed_statuses = {"new", "contacted", "converted", "dead"}
    if len(parts) != 3 or not parts[1].isdigit() or parts[2] not in allowed_statuses:
        await message.answer("Формат: /lead_status <lead_id> <new|contacted|converted|dead>")
        return
    async with session_factory() as session:
        ok = await queries.update_lead_status(session, int(parts[1]), parts[2])
    await message.answer("Статус обновлен." if ok else "Лид не найден.")


@router.message(Command("deal"))
async def deal_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Формат: /deal <lead_id> <amount>")
        return
    try:
        amount = Decimal(parts[2].replace(",", "."))
    except InvalidOperation:
        await message.answer("Сумма должна быть числом.")
        return
    if amount <= 0:
        await message.answer("Сумма должна быть больше нуля.")
        return
    async with session_factory() as session:
        ok = await queries.close_deal(session, int(parts[1]), amount)
    await message.answer("Сделка сохранена." if ok else "Лид не найден.")
