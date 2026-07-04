from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.images import MAIN_MENU_IMG
from backend.services.exceptions import InsufficientBalance, SubscriptionNotFound, UserNotFound
from backend.states import TrafficPurchaseStates

router = Router()
TRAFFIC_PRICE_PER_GB_RUB = 2


def _buy_traffic_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="buy_traffic_confirm")
    builder.button(text="⬅️ Назад", callback_data="vpn_subscription")
    builder.adjust(1)
    return builder.as_markup()


def _back_sub_url_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️К подписке", callback_data="vpn_subscription")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "reset_traffic")
async def buy_traffic_start(
    callback: CallbackQuery,
    state: FSMContext,
    bot_api,
):
    try:
        await bot_api.get_subscription_url(tg_id=callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return
    except SubscriptionNotFound:
        await callback.answer("Подписка не активна, купите подписку.", show_alert=True)
        return
    except Exception:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    text = (
        "<b>Докупка трафика</b>\n\n"
        "Введите, сколько ГБ хотите докупить (целое число, минимум 1).\n"
        f"Цена: <b>{TRAFFIC_PRICE_PER_GB_RUB} RUB за 1 GB</b>.\n"
        "Докупленный трафик переносится между месяцами и продлениями."
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_back_sub_url_kb())
    await state.set_state(TrafficPurchaseStates.waiting_for_gb)
    await callback.answer()


@router.message(TrafficPurchaseStates.waiting_for_gb)
async def buy_traffic_enter_gb(message: Message, state: FSMContext):
    try:
        gb = int((message.text or "").strip())
        if gb < 1:
            raise ValueError
    except ValueError:
        await message.answer("Введите целое число ГБ (минимум 1).")
        return

    total = gb * TRAFFIC_PRICE_PER_GB_RUB
    await state.update_data(traffic_gb=gb, traffic_price=total)
    await state.set_state(TrafficPurchaseStates.waiting_for_confirmation)

    text = (
        "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Подтверждение</b>\n\n"
        f"Добавить: <b>+{gb} GB</b>\n"
        f"К списанию: <b>{total} RUB</b>\n\n"
        "Продолжить?"
    )
    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=_buy_traffic_confirm_kb(),
    )


@router.callback_query(F.data == "buy_traffic_confirm")
async def buy_traffic_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot_api,
):
    data = await state.get_data()
    gb = int(data.get("traffic_gb") or 0)
    price = int(data.get("traffic_price") or 0)
    if gb <= 0:
        await callback.answer("Сначала укажите количество ГБ.", show_alert=True)
        return

    try:
        await bot_api.get_subscription_url(tg_id=callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return
    except SubscriptionNotFound:
        await callback.answer("Подписка не активна, купите подписку.", show_alert=True)
        return

    try:
        result = await bot_api.buy_traffic(tg_id=callback.from_user.id, gb=gb)
    except InsufficientBalance:
        await callback.answer("Недостаточно средств на балансе для покупки трафика.", show_alert=True)
        return
    except Exception:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    await state.clear()
    await callback.answer("Трафик докуплен")

    text = (
        "<b><tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Трафик докуплен</b>\n\n"
        f"Добавлено: <b>+{gb} GB</b>\n"
        f"Списано: <b>{result.get('charged', price)} RUB</b>\n"
        "Лимит трафика обновлен. Обновите подписку в приложении."
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_back_sub_url_kb())
