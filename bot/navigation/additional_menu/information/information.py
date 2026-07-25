from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG
from bot.navigation.additional_menu.information.keyboards import information_kb

router = Router()


def _build_information_text() -> str:
    return (
        "<b><tg-emoji emoji-id=\"5879585266426973039\">🌐</tg-emoji> В нашем сервисе более 15-ти серверов с каналом до 20 Гбит/с!</b>\n\n"
        "<i>При проблемах в работе сервиса обращайтесь в поддержку.</i>"
    )


@router.callback_query(F.data == "information")
async def information_clb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=_build_information_text())
    await callback.message.edit_media(media=media, reply_markup=information_kb())
    await callback.answer()
