from decimal import Decimal, ROUND_UP

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.images import MAIN_MENU_IMG
from backend.services import BillingService, UserService
from backend.services.exceptions import InsufficientBalance, SubscriptionNotFound, UserNotFound
from backend.states import GbAddStates

router = Router()


def _traffic_purchase_cancel_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="vpn_subscription")
    return builder.as_markup()


def _traffic_purchase_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="confirm_buy_extra_traffic")
    builder.button(text="⬅️ Назад", callback_data="cancel_buy_extra_traffic")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "buy_extra_traffic")
async def buy_extra_traffic_start(callback: CallbackQuery, state: FSMContext):
    text = (
        "<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Докупка трафика</b>\n\n"
        "Введите объем докупки трафика в GB.\n"
        "Цена: <b>0.5 RUB за 1 GB</b>.\n"
        "Минимум: <b>5 GB</b>"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_traffic_purchase_cancel_kb())
    await state.set_state(GbAddStates.waiting_for_amount)
    await callback.answer()


@router.message(GbAddStates.waiting_for_amount)
async def buy_extra_traffic_amount(
    message: Message,
    state: FSMContext,
):
    try:
        gb = int((message.text or "").strip())
    except Exception:
        await message.answer("Введите целое число ГБ, например: 5")
        return

    if gb < 5:
        await message.answer("Минимальная докупка — 5 ГБ.")
        return

    charged_rub = int((Decimal(gb) * Decimal("0.5")).to_integral_value(rounding=ROUND_UP))
    await state.update_data(gb=gb)

    text = (
        "<b>Подтверждение оплаты</b>\n\n"
        f"Объем: <b>+{gb} GB</b>\n"
        f"К списанию: <b>{charged_rub} RUB</b>\n\n"
    )
    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=_traffic_purchase_confirm_kb(),
    )
    await state.set_state(GbAddStates.waiting_for_purchase)


@router.callback_query(F.data == "cancel_buy_extra_traffic", GbAddStates.waiting_for_purchase)
async def cancel_buy_extra_traffic(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "<b>Покупка отменена</b>\n\nВы можете вернуться к экрану подписки."
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_traffic_purchase_cancel_kb())
    await callback.answer()


@router.callback_query(F.data == "confirm_buy_extra_traffic", GbAddStates.waiting_for_purchase)
async def confirm_buy_extra_traffic(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
    billing_service: BillingService,
):
    data = await state.get_data()
    gb = int(data.get("gb") or 0)
    if gb < 5:
        await callback.answer("Некорректный объем", show_alert=True)
        return

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.answer("Пользователь не найден", show_alert=True)
        await state.clear()
        return

    try:
        sub, charged_rub = await billing_service.add_gb_to_subscription(user_id=user.id, gb=gb)
    except InsufficientBalance:
        await callback.answer("Недостаточно средств на балансе", show_alert=True)
        return
    except SubscriptionNotFound:
        await callback.answer("Активная подписка не найдена", show_alert=True)
        await state.clear()
        return
    except ValueError as e:
        await callback.answer(str(e), show_alert=True)
        return
    except Exception:
        await callback.answer("Не удалось докупить трафик", show_alert=True)
        return

    text = (
        "<b><tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Покупка завершена</b>\n\n"
        f"Добавлено: <b>+{gb} GB</b>\n"
        f"Списано: <b>{charged_rub} RUB</b>\n"
        f"Текущий остаток: <b>{sub.gb_left} GB</b>"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_traffic_purchase_cancel_kb())
    await state.clear()
    await callback.answer("Трафик докуплен")
