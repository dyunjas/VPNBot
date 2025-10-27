from aiogram import F, Router
from aiogram.filters import Command
from aiogram.types import CallbackQuery, Message, InputMediaPhoto

from client.navigation.main_menu.keyboards import main_menu_kb

from server.repositories.user_repository import UserRepository

from server.images import MAIN_MENU_IMG

router = Router()

@router.message(Command("start"))
async def start_cmd(message: Message):
    text = (
        "🌙 Добро пожаловать в Lunet!\n\n"
        "<b>В нашем сервисе:</b>\n"
        "⚡️Нет ограничесний по скорости, трафику и количеству устройств\n"
        "🔒Полная безопасность ваших данных\n"
        "🌐Полная совместимость со всеми платформами и устройствами"
    )
    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "main_menu")
async def main_menu_clb(callback: CallbackQuery):
    text = text = (
        "🌙 Добро пожаловать в Lunet!\n\n"
        "<b>В нашем сервисе:</b>\n"
        "⚡️Нет ограничесний по скорости, трафику и количеству устройств\n"
        "🔒Полная безопасность ваших данных\n"
        "🌐Полная совместимость со всеми платформами и устройствами"
    )
    media = InputMediaPhoto(
    caption=text,
    media=MAIN_MENU_IMG
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=main_menu_kb()
    )