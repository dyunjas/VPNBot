from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from client.navigation.additional_menu.profile.keyboards import profile_kb

from server.repositories.user_repository import UserRepository

from server.images import MAIN_MENU_IMG

router = Router()

@router.callback_query(F.data == "profile")
async def profile_clb(callback: CallbackQuery, user_repo: UserRepository):
    tg_id = callback.from_user.id
    user = await user_repo.get_user_by_tg_id(tg_id)
    username = "-" if user.username == None else f"@{user.username}"
    text = (
        f"<b>🌙 Пользователь №{user.id}:</b>\n"
        f"<b>✨ Юзернейм:</b> {username}\n"
        f"<b>⭐️ ID:</b> {user.tg_id}\n"
        f"<b>🌟 Баланс:</b> {user.balance} RUB"
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