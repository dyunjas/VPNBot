from __future__ import annotations

from aiogram.types import CallbackQuery, Message

from backend.services.exceptions import MaintenanceModeError

MAINTENANCE_TEXT = "Сервер не доступен. Идут технические работы."
MAINTENANCE_HTML = (
    "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
    "Сервер не доступен. Идут технические работы."
)


def is_maintenance_error(error: Exception) -> bool:
    return isinstance(error, MaintenanceModeError)


async def answer_maintenance_callback(callback: CallbackQuery) -> None:
    try:
        await callback.answer(MAINTENANCE_TEXT, show_alert=True)
    except Exception:
        return


async def send_maintenance_message(message: Message) -> None:
    try:
        await message.answer(MAINTENANCE_HTML)
    except Exception:
        return
