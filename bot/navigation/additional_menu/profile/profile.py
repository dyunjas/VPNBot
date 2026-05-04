from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from bot.navigation.additional_menu.profile.keyboards import profile_kb

from backend.services import UserService
from backend.services.exceptions import UserNotFound

from backend.images import MAIN_MENU_IMG


router = Router()


@router.callback_query(F.data == "profile")
async def profile_clb(callback: CallbackQuery, user_service: UserService):
    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return
    
    username = "-" if user.username == None else f"@{user.username}"
    text = (
        f"<b><tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> Пользователь №{user.id}:</b>\n"
        f"<b><tg-emoji emoji-id='5879770735999717115'>👤</tg-emoji> Юзернейм:</b> {username}\n"
        f"<b><tg-emoji emoji-id='5874948844935974490'>⭐️</tg-emoji> ID:</b> <code>{user.tg_id}</code>\n"
        f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Баланс:</b> {user.balance} RUB"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=profile_kb()
    )
    await callback.answer()