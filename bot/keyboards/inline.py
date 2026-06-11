from __future__ import annotations

from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def main_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Dashboard", callback_data="nav:dashboard")],
            [InlineKeyboardButton(text="Pending", callback_data="nav:pending")],
            [InlineKeyboardButton(text="Approved", callback_data="nav:approved_queue")],
            [InlineKeyboardButton(text="Review queue", callback_data="nav:review_queue")],
            [InlineKeyboardButton(text="Saved", callback_data="nav:saved_queue")],
            [InlineKeyboardButton(text="Channels", callback_data="nav:channels")],
            [InlineKeyboardButton(text="Leads", callback_data="nav:leads")],
            [InlineKeyboardButton(text="Templates", callback_data="nav:templates")],
            [InlineKeyboardButton(text="Settings", callback_data="nav:settings")],
        ]
    )


def pending_actions(post_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Approve", callback_data=f"post:approve:{post_id}")],
            [InlineKeyboardButton(text="Approve now", callback_data=f"post:approve_now:{post_id}")],
            [InlineKeyboardButton(text="Save", callback_data=f"post:save:{post_id}")],
            [InlineKeyboardButton(text="Show draft", callback_data=f"post:draft:{post_id}")],
            [InlineKeyboardButton(text="Edit help", callback_data=f"post:edit:{post_id}")],
            [InlineKeyboardButton(text="Skip", callback_data=f"post:skip:{post_id}")],
        ]
    )


def approved_actions(post_id: int, url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Dispatch now", callback_data=f"post:dispatch:{post_id}")],
        [InlineKeyboardButton(text="Save", callback_data=f"post:save:{post_id}")],
        [InlineKeyboardButton(text="Show draft", callback_data=f"post:draft:{post_id}")],
        [InlineKeyboardButton(text="Skip", callback_data=f"post:skip:{post_id}")],
    ]
    if url:
        rows.append([InlineKeyboardButton(text="Open source", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def reviewer_actions(post_id: int, url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Done", callback_data=f"review:done:{post_id}")],
        [InlineKeyboardButton(text="Save", callback_data=f"post:save:{post_id}")],
        [InlineKeyboardButton(text="Show draft", callback_data=f"post:draft:{post_id}")],
        [InlineKeyboardButton(text="Skip", callback_data=f"review:skip:{post_id}")],
    ]
    if url:
        rows.append([InlineKeyboardButton(text="Open source", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def saved_actions(post_id: int, url: str | None) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(text="Show source", callback_data=f"post:source:{post_id}")],
        [InlineKeyboardButton(text="Show draft", callback_data=f"post:draft:{post_id}")],
        [InlineKeyboardButton(text="Skip", callback_data=f"post:skip:{post_id}")],
    ]
    if url:
        rows.append([InlineKeyboardButton(text="Open source", url=url)])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def channel_actions(channel_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Toggle active", callback_data=f"channel:toggle:{channel_id}")],
        ]
    )
