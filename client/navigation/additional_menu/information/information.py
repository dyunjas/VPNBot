from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from client.navigation.additional_menu.information.keyboards import information_kb


from server.images import MAIN_MENU_IMG

router = Router()

@router.callback_query(F.data == "information")
async def information_clb(callback: CallbackQuery):
    text = (
        "<b>ℹ️Информация</b>\n"
        "<i>Используя кнопки ниже, вы можете узнать ответы на интересующие вас вопросы</i>"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=information_kb()
    )
    await callback.answer()