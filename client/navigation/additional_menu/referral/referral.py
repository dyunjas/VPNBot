from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from server.images import MAIN_MENU_IMG
from client.navigation.additional_menu.referral.keyboards import referral_kb

router = Router()


@router.callback_query(F.data == "referral")
async def referral_clb(callback: CallbackQuery):

    tg_id = callback.from_user.id

    referral_url = f"https://t.me/LunetVpnBot?start=ref_{tg_id}"
    share_referral_url = f"https://t.me/share/url?url={referral_url}"

    text = (
        "<b>Приглашайте друзей и зарабатывайте\n</b>"
        "🎁 +10 RUB вам и другу за регистрацию\n"
        "🌟 +20% с каждого пополнения друга\n\n"

        "🔗 Ваша ссылка:\n"
        f"<code>{referral_url}</code>\n"
        "<i>ℹ️ Совет: делитесь ссылкой с друзьями, публикуйте в чатах и соцсетях</i>"
    )

    media = InputMediaPhoto(
        caption=text,
        media=MAIN_MENU_IMG,
        parse_mode="HTML"
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=referral_kb(share_referral_url)
    )