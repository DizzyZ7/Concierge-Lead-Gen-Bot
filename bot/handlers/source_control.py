from __future__ import annotations

from asyncio import Lock

from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message

from services.limit_queue_promoter import LimitQueuePromoter
from services.parser import ParserService

router = Router(name=__name__)


@router.message(Command("scan_now"))
async def scan_now_command(
    message: Message,
    parser_service: ParserService | None,
    source_workflow_lock: Lock,
) -> None:
    if parser_service is None:
        await message.answer("Parser недоступен. Проверь PARSER_ENABLED, TG_API_ID, TG_API_HASH и Telegram session.")
        return
    async with source_workflow_lock:
        await parser_service.run_once()
    await message.answer("Parser выполнил ручной проход. Проверь /pending, /approved_queue, /limit_queue и /failed_queue.")


@router.message(Command("promote_limit_queue"))
async def promote_limit_queue_command(
    message: Message,
    limit_queue_promoter: LimitQueuePromoter,
    source_workflow_lock: Lock,
) -> None:
    async with source_workflow_lock:
        result = await limit_queue_promoter.run_once()
    if result is None:
        await message.answer("Не удалось обработать очередь. Проверь /health и /failed_queue.")
        return
    if result.paused:
        await message.answer("Мониторинг на паузе. Сначала используй /resume.")
        return
    await message.answer(
        "Разгрузка очереди выполнена.\n"
        f"Продвинуто в reviewer pipeline: {result.promoted}\n"
        f"Осталось в лимитной очереди: {result.queued}"
    )
