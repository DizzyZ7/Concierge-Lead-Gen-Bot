from __future__ import annotations

from html import escape

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from db import queries

router = Router(name=__name__)

BUSINESS_CONTEXT_KEY = "business_context"
BUSINESS_CONTEXT_LIMIT = 2500


def normalize_context(value: str) -> str:
    return " ".join(value.split())


async def send_settings(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        paused = await queries.get_setting(session, "paused", "false")
        business_context = await queries.get_setting(session, BUSINESS_CONTEXT_KEY, "")
    await message.answer(
        "Настройки\n\n"
        f"Пауза: {'да' if paused == 'true' else 'нет'}\n"
        "Режим: reviewer-first\n"
        "Внешние действия: только вручную\n"
        f"Business context: {'настроен' if business_context else 'не задан'}"
    )


@router.message(Command("settings"))
async def settings_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await send_settings(message, session_factory)


@router.callback_query(F.data == "nav:settings")
async def settings_callback(callback: CallbackQuery, session_factory: async_sessionmaker[AsyncSession]) -> None:
    await callback.answer()
    await send_settings(callback.message, session_factory)


@router.message(Command("pause"))
async def pause_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await queries.set_setting(session, "paused", "true")
    await message.answer("Мониторинг поставлен на паузу.")


@router.message(Command("resume"))
async def resume_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        await queries.set_setting(session, "paused", "false")
    await message.answer("Мониторинг возобновлен.")


@router.message(Command("autoapprove"))
async def autoapprove_command(message: Message) -> None:
    await message.answer(
        "Автоодобрение не используется в reviewer-first режиме. "
        "Бот может подготовить карточку и черновик, но решение о внешнем действии остается за человеком."
    )


@router.message(Command("business_context"))
async def business_context_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    async with session_factory() as session:
        value = await queries.get_setting(session, BUSINESS_CONTEXT_KEY, "")
    if not value:
        await message.answer(
            "Business context пока не задан.\n\n"
            "Добавь его так:\n"
            "/set_business_context Помогаем с ..."
        )
        return
    await message.answer(f"Business context:\n\n{escape(value)}")


@router.message(Command("set_business_context"))
async def set_business_context_command(message: Message, session_factory: async_sessionmaker[AsyncSession]) -> None:
    parts = (message.text or "").split(maxsplit=1)
    if len(parts) != 2:
        await message.answer("Формат: /set_business_context <описание услуг>\nДля очистки: /set_business_context -")
        return
    value = "" if parts[1].strip() == "-" else normalize_context(parts[1])
    if len(value) > BUSINESS_CONTEXT_LIMIT:
        await message.answer(f"Контекст слишком длинный. Максимум: {BUSINESS_CONTEXT_LIMIT} символов.")
        return
    async with session_factory() as session:
        await queries.set_setting(session, BUSINESS_CONTEXT_KEY, value)
    if not value:
        await message.answer("Business context очищен. AI снова будет работать в нейтральном режиме.")
        return
    await message.answer("Business context сохранен. Он будет учтен в следующих AI-оценках и черновиках.")
