from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from backend.images import MAIN_MENU_IMG
from bot.navigation.additional_menu.referral.keyboards import referral_kb

from backend.services import ReferralService, UserService
from backend.services.exceptions import UserNotFound

router = Router()


@router.callback_query(F.data == "referral")
async def referral_clb(callback: CallbackQuery, referral_service: ReferralService, user_service: UserService, state: FSMContext):

    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return
    
    referral_account = await referral_service.create_account(user.id)

    referral_url = f"https://t.me/LunetVpnBot?start=ref_{tg_id}"
    share_referral_url = f"https://t.me/share/url?url={referral_url}"

    text = (
        "<b>Приглашайте друзей и зарабатывайте\n</b>"
        "<tg-emoji emoji-id='5875180111744995604'>🎁</tg-emoji> +10 RUB вам и другу за регистрацию\n"
        f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> +{referral_account.referral_percent}% с каждого пополнения друга\n\n"

        "<tg-emoji emoji-id='5931472654660800739'>📊</tg-emoji> Ваша статистика:\n"
        f"<tg-emoji emoji-id='5879770735999717115'>👤</tg-emoji> Приглашено: {referral_account.invited_count} чел\n"
        f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Баланс: {referral_account.referral_balance} RUB\n\n"

        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> Ваша ссылка:\n"
        f"<code>{referral_url}</code>\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Совет: делитесь ссылкой с друзьями, публикуйте в чатах и соцсетях</i>"
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
    await state.clear()