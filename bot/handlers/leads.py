from __future__ import annotations

from decimal import Decimal, InvalidOperation
from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import queries

router = Router(name=__name__)


async def send_leads(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        leads = await queries.list_new_leads(session, 20)
    if not leads:
        await message.answer("No new leads.")
        return
    for lead in leads:
        username = f"@{lead.tg_username}" if lead.tg_username else "-"
        text = (
            f"Lead #{lead.id}\n"
            f"User ID: {lead.tg_user_id or '-'}\n"
            f"Username: {escape(username)}\n"
            f"First name: {escape(lead.first_name or '-')}\n"
            f"Geo: {escape(lead.geo or '-')}\n"
            f"Intent: {escape(lead.intent or '-')}\n"
            f"Notes: {escape(lead.notes or '-')}"
        )
        await message.answer(text)


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
        await message.answer("Usage: /add_lead <tg_user_id_or_0> <username_or_dash> <geo> <intent> <notes>")
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
    await message.answer(f"Added lead #{lead.id}.")


@router.message(Command("lead_status"))
async def lead_status_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Usage: /lead_status <lead_id> <new|contacted|converted|dead>")
        return
    async with session_factory() as session:
        ok = await queries.update_lead_status(session, int(parts[1]), parts[2])
    await message.answer("Updated." if ok else "Lead not found.")


@router.message(Command("deal"))
async def deal_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    if not message.text:
        return
    parts = message.text.split(maxsplit=2)
    if len(parts) != 3 or not parts[1].isdigit():
        await message.answer("Usage: /deal <lead_id> <amount>")
        return
    try:
        amount = Decimal(parts[2])
    except InvalidOperation:
        await message.answer("Amount must be numeric.")
        return
    async with session_factory() as session:
        ok = await queries.close_deal(session, int(parts[1]), amount)
    await message.answer("Deal saved." if ok else "Lead not found.")
