from __future__ import annotations

from aiogram.exceptions import TelegramBadRequest
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message

CALLBACK_MESSAGE_UNAVAILABLE = "Сообщение недоступно. Открой раздел командой из меню."


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


async def edit_callback_message_or_alert(
    callback: CallbackQuery,
    text: str,
    *,
    reply_markup: InlineKeyboardMarkup | None = None,
    disable_web_page_preview: bool | None = None,
) -> bool:
    if not isinstance(callback.message, Message):
        await callback.answer(text, show_alert=True)
        return False
    await edit_or_answer(
        callback.message,
        text,
        reply_markup=reply_markup,
        disable_web_page_preview=disable_web_page_preview,
    )
    return True


async def callback_message_or_alert(
    callback: CallbackQuery,
    text: str = CALLBACK_MESSAGE_UNAVAILABLE,
) -> Message | None:
    if isinstance(callback.message, Message):
        return callback.message
    await callback.answer(text, show_alert=True)
    return None
