from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message


async def edit_or_answer(
    message: Message,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool | None = None,
) -> None:
    try:
        await message.edit_text(
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
    except TelegramBadRequest as error:
        description = str(error).lower()
        if "message is not modified" in description:
            return
        await message.answer(text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)


async def edit_callback_message(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool | None = None,
) -> None:
    if isinstance(callback.message, Message):
        await edit_or_answer(
            callback.message,
            text,
            reply_markup=reply_markup,
            disable_web_page_preview=disable_web_page_preview,
        )
