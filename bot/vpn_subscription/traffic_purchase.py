from decimal import Decimal, ROUND_HALF_UP

from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.images import MAIN_MENU_IMG
from backend.services import RemnaWaveService, SubscriptionService, UserService
from backend.services.exceptions import SubscriptionNotFound, UserNotFound

router = Router()


def _reset_traffic_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="reset_traffic_confirm")
    builder.button(text="⬅️ Назад", callback_data="vpn_subscription")
    builder.adjust(1)
    return builder.as_markup()

def _back_sub_url_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️К подписке", callback_data="vpn_subscription")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "reset_traffic")
async def reset_traffic(
    callback: CallbackQuery,
    user_service: UserService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnaWaveService,
):
    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    try:
        sub = await subscription_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        await callback.answer("Подписка не активна, купите подписку.", show_alert=True)
        return

    if not remnawave_service.enabled:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    plan_price = int(getattr(getattr(sub, "plan", None), "price", 0) or 0)
    charge = int((Decimal(plan_price) * Decimal("0.5")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if charge < 1:
        charge = 1

    text = (
        "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Подтверждение</b>\n\n"
        "Вы хотите обнулить трафик текущей подписки.\n"
        f"К списанию: <b>{charge} RUB (50% от стоимости тарифа)</b>\n\n"
        "Продолжить?"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_reset_traffic_confirm_kb())
    await callback.answer()


@router.callback_query(F.data == "reset_traffic_confirm")
async def reset_traffic_confirm(
    callback: CallbackQuery,
    user_service: UserService,
    subscription_service: SubscriptionService,
    remnawave_service: RemnaWaveService,
):
    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    try:
        sub = await subscription_service.get_active_subscription(user_id=user.id)
    except SubscriptionNotFound:
        await callback.answer("Подписка не активна, купите подписку.", show_alert=True)
        return

    if not remnawave_service.enabled:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    plan_price = int(getattr(getattr(sub, "plan", None), "price", 0) or 0)
    charge = int((Decimal(plan_price) * Decimal("0.5")).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
    if charge < 1:
        charge = 1

    balance = int(getattr(user, "balance", 0) or 0)
    if balance < charge:
        await callback.answer(f"Недостаточно средств. Нужно {charge} RUB", show_alert=True)
        return

    ok = await remnawave_service.reset_user_traffic(user=user, subscription=sub)
    if not ok:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    await user_service.sub_balance(user_id=user.id, amount=charge)
    await callback.answer("Трафик обнулен")

    text = (
        "<b><tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Трафик обнулен</b>\n\n"
        f"Списано: <b>{charge} RUB</b>\n"
        "Лимиты трафика сброшены. Обновите подписку в приложении."
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_back_sub_url_kb())
