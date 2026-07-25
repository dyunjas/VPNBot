from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG
from backend.services.exceptions import UserNotFound
from bot.navigation.additional_menu.balance.keyboards import balance_menu_kb


router = Router()


def build_balance_text(user: dict) -> str:
    return (
        "<b><tg-emoji emoji-id='5769403330761593044'>💳</tg-emoji> Управление балансом</b>\n\n"
        f"<blockquote><b><tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Доступно:</b> {user.get('balance')} RUB</blockquote>\n\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Пополните баланс любым удобным вам способом.</i>"
    )


@router.callback_query(F.data == "balance_menu")
async def balance_menu_clb(callback: CallbackQuery, bot_api):
    try:
        resp = await bot_api.get_user_by_tg_id(callback.from_user.id)
        user = resp.get("user") if isinstance(resp, dict) else resp
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    await callback.message.edit_media(
        media=InputMediaPhoto(media=MAIN_MENU_IMG, caption=build_balance_text(user)),
        reply_markup=balance_menu_kb(),
    )
    await callback.answer()
