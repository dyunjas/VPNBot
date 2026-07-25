from aiogram import Router, F
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import PROFILE_IMG
from bot.navigation.additional_menu.referral.keyboards import referral_kb
from bot.utils.html import html_escape

router = Router()


@router.callback_query(F.data == "referral")
async def referral_clb(callback: CallbackQuery, bot_api, state: FSMContext):
    try:
        info = await bot_api.get_referral_info(tg_id=callback.from_user.id)
    except Exception:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    referral = info.get("referral") if isinstance(info, dict) else {}
    referral_url = f"https://t.me/LunetVpnBot?start=ref_{callback.from_user.id}"
    share_referral_url = f"https://t.me/share/url?url={referral_url}"

    text = (
        "<b>Приглашайте друзей и зарабатывайте\n\n</b>"
        "<blockquote><tg-emoji emoji-id='5963213811597970978'>🎁</tg-emoji> +1 день VPN \n"
        f"<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> +{referral.get('percent')}% с каждого пополнения друга</blockquote>\n\n"
        "<blockquote><tg-emoji emoji-id='5931472654660800739'>📉</tg-emoji> Ваша статистика:\n"
        f"<tg-emoji emoji-id='5920344347152224466'>👤</tg-emoji> Приглашено: {referral.get('invited_count')} чел\n"
        f"<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Баланс: {referral.get('balance')} RUB</blockquote>\n\n"
        "<tg-emoji emoji-id='5877465816030515018'>🔗</tg-emoji> Ваша ссылка:\n"
        f"<code>{html_escape(referral_url)}</code>\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Совет: делитесь ссылкой с друзьями, публикуйте в чатах и соцсетях</i>"
    )

    media = InputMediaPhoto(
        caption=text,
        media=PROFILE_IMG,
        parse_mode="HTML"
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=referral_kb(share_referral_url)
    )
    await state.clear()

