from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG
from bot.navigation.additional_menu.information.keyboards import information_kb

router = Router()


def _build_information_text() -> str:
    return (
        "<b><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Информация</b>\n"
        "<i>Используя кнопки ниже, вы можете узнать ответы на интересующие вас вопросы.</i>"
    )


@router.callback_query(F.data == "information")
async def information_clb(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=_build_information_text())
    await callback.message.edit_media(media=media, reply_markup=information_kb())
    await callback.answer()
