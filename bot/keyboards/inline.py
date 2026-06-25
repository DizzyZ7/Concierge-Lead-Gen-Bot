from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu(*, is_admin: bool = True) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Главная", callback_data="nav:dashboard")],
        [InlineKeyboardButton(text="Отчет за 24 часа", callback_data="nav:daily_report")],
        [InlineKeyboardButton(text="На проверке", callback_data="nav:pending")],
        [InlineKeyboardButton(text="Одобренные", callback_data="nav:approved_queue")],
        [InlineKeyboardButton(text="Очередь reviewer-а", callback_data="nav:review_queue")],
        [InlineKeyboardButton(text="Просроченные reviewer", callback_data="nav:reviewer_backlog")],
        [InlineKeyboardButton(text="Сохраненные", callback_data="nav:saved_queue")],
        [InlineKeyboardButton(text="Идеи", callback_data="nav:content_ideas")],
    ]
    if is_admin:
        rows.extend(
            [
                [InlineKeyboardButton(text="Статистика каналов", callback_data="nav:channel_stats")],
                [InlineKeyboardButton(text="Сверх дневного лимита", callback_data="nav:limit_queue")],
                [InlineKeyboardButton(text="Ошибки обработки", callback_data="nav:failed_queue")],
                [InlineKeyboardButton(text="Каналы", callback_data="nav:channels")],
                [InlineKeyboardButton(text="Лиды", callback_data="nav:leads")],
                [InlineKeyboardButton(text="Шаблоны", callback_data="nav:templates")],
                [InlineKeyboardButton(text="Настройки", callback_data="nav:settings")],
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows)


def result_actions(post_id: int) -> list[list[InlineKeyboardButton]]:
    return [
        [
            InlineKeyboardButton(text="Комментарий написан", callback_data=f"result:commented:{post_id}"),
            InlineKeyboardButton(text="Стал лидом", callback_data=f"result:lead:{post_id}"),
        ],
        [
            InlineKeyboardButton(text="Идея", callback_data=f"result:content_idea:{post_id}"),
            InlineKeyboardButton(text="Нерелевантно", callback_data=f"result:not_relevant:{post_id}"),
        ],
    ]


def pending_actions(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Одобрить", callback_data=f"post:approve:{post_id}")],
            [InlineKeyboardButton(text="Одобрить сейчас", callback_data=f"post:approve_now:{post_id}")],
            [InlineKeyboardButton(text="Сохранить", callback_data=f"post:save:{post_id}")],
            [InlineKeyboardButton(text="Показать черновик", callback_data=f"post:draft:{post_id}")],
            [InlineKeyboardButton(text="Как отредактировать", callback_data=f"post:edit:{post_id}")],
            [InlineKeyboardButton(text="Пропустить", callback_data=f"post:skip:{post_id}")],
        ]
    )


def failed_actions(post_id: int, url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Повторить обработку", callback_data=f"failed:retry:{post_id}")],
        [InlineKeyboardButton(text="Показать источник", callback_data=f"post:source:{post_id}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"post:skip:{post_id}")],
    ]
    if url:
        rows.append([InlineKeyboardButton(text="Открыть источник", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def approved_actions(post_id: int, url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Отправить в очередь сейчас", callback_data=f"post:dispatch:{post_id}")],
        [InlineKeyboardButton(text="Сохранить", callback_data=f"post:save:{post_id}")],
        [InlineKeyboardButton(text="Показать черновик", callback_data=f"post:draft:{post_id}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"post:skip:{post_id}")],
    ]
    rows.extend(result_actions(post_id))
    if url:
        rows.append([InlineKeyboardButton(text="Открыть источник", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reviewer_actions(post_id: int, url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Взять в работу", callback_data=f"review:claim:{post_id}"),
            InlineKeyboardButton(text="Освободить", callback_data=f"review:release:{post_id}"),
        ],
        [InlineKeyboardButton(text="Обработано", callback_data=f"review:done:{post_id}")],
        [InlineKeyboardButton(text="Сохранить", callback_data=f"post:save:{post_id}")],
        [InlineKeyboardButton(text="Показать черновик", callback_data=f"post:draft:{post_id}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"review:skip:{post_id}")],
    ]
    rows.extend(result_actions(post_id))
    if url:
        rows.append([InlineKeyboardButton(text="Открыть источник", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def saved_actions(post_id: int, url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Показать источник", callback_data=f"post:source:{post_id}")],
        [InlineKeyboardButton(text="Показать черновик", callback_data=f"post:draft:{post_id}")],
        [InlineKeyboardButton(text="Пропустить", callback_data=f"post:skip:{post_id}")],
    ]
    rows.extend(result_actions(post_id))
    if url:
        rows.append([InlineKeyboardButton(text="Открыть источник", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_actions(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Вкл./выкл. мониторинг", callback_data=f"channel:toggle:{channel_id}")],
            [InlineKeyboardButton(text="К списку каналов", callback_data="nav:channels")],
            [InlineKeyboardButton(text="Главная", callback_data="nav:dashboard")],
        ]
    )


def channels_menu(channel_ids: list[int]) -> InlineKeyboardMarkup:
    rows: list[list[InlineKeyboardButton]] = []
    for channel_id in channel_ids:
        rows.append([InlineKeyboardButton(text=f"Канал #{channel_id}", callback_data=f"channel:view:{channel_id}")])
    rows.append([InlineKeyboardButton(text="Главная", callback_data="nav:dashboard")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
