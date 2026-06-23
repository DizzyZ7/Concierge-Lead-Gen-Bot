from __future__ import annotations

from aiogram import Dispatcher


def configure_dispatcher_data(dispatcher: Dispatcher, **data: object) -> None:
    for key, value in data.items():
        dispatcher[key] = value
