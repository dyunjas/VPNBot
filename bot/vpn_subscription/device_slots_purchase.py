from decimal import Decimal, ROUND_UP

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.core.business_config import get_business_decimal
from backend.images import SUBSCRIPTION_IMG
from backend.services.exceptions import InsufficientBalance, SubscriptionNotFound, UserNotFound
from backend.states import DeviceSlotsPurchaseStates

router = Router()


def _format_rub(value: Decimal | int | float) -> str:
    text = format(Decimal(str(value)), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data="buy_device_slots_confirm", icon_custom_emoji_id="5776375003280838798", style="success")
    builder.button(text="Отмена", callback_data="subscription_devices", icon_custom_emoji_id="5778527486270770928", style="danger")
    builder.adjust(1)
    return builder.as_markup()


def _back_devices_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="К устройствам", callback_data="subscription_devices", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data == "buy_device_slots")
async def buy_device_slots_start(callback: CallbackQuery, state: FSMContext, bot_api):
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

    price = _format_rub(get_business_decimal("DEVICE_SLOT_PRICE_RUB"))
    text = (
        "Введите количество дополнительных устройств, которое хотите купить.\n\n"
        f"<blockquote><tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Стоимость: <b>{price} RUB за 1 устройство</b>\n"
        "<tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Можно купить от <b>1</b> до <b>20</b> устройств за раз.</blockquote>\n\n"
        "<i><tg-emoji emoji-id='6005843436479975944'>🔁</tg-emoji> При следующем продлении лимит вернется к лимиту выбранного тарифа.</i>"
    )
    media = InputMediaPhoto(media=SUBSCRIPTION_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_back_devices_kb())
    await state.set_state(DeviceSlotsPurchaseStates.waiting_for_slots)
    await callback.answer()


@router.message(DeviceSlotsPurchaseStates.waiting_for_slots)
async def buy_device_slots_enter(message: Message, state: FSMContext):
    try:
        slots = int((message.text or "").strip())
        if slots < 1 or slots > 20:
            raise ValueError
    except ValueError:
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Введите целое число устройств от 1 до 20.")
        return

    total = int((Decimal(slots) * get_business_decimal("DEVICE_SLOT_PRICE_RUB")).to_integral_value(rounding=ROUND_UP))
    await state.update_data(device_slots=slots, device_slots_price=total)
    await state.set_state(DeviceSlotsPurchaseStates.waiting_for_confirmation)

    text = (
        "Проверьте данные перед оплатой:\n\n"
        f"<blockquote><tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Будет добавлено: <b>{slots}</b>\n"
        f"<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> К списанию: <b>{total} RUB</b></blockquote>"
    )
    await message.answer_photo(photo=SUBSCRIPTION_IMG, caption=text, parse_mode="HTML", reply_markup=_confirm_kb())


@router.callback_query(DeviceSlotsPurchaseStates.waiting_for_confirmation, F.data == "buy_device_slots_confirm")
async def buy_device_slots_confirm(callback: CallbackQuery, state: FSMContext, bot_api):
    data = await state.get_data()
    slots = int(data.get("device_slots") or 0)
    price = int(data.get("device_slots_price") or 0)
    if slots <= 0:
        await callback.answer("Сначала укажите количество устройств.", show_alert=True)
        return

    try:
        result = await bot_api.buy_device_slots(tg_id=callback.from_user.id, slots=slots)
    except InsufficientBalance:
        await callback.answer("Недостаточно средств на балансе для покупки устройств.", show_alert=True)
        return
    except SubscriptionNotFound:
        await callback.answer("Подписка не активна, купите подписку.", show_alert=True)
        return
    except Exception:
        await callback.answer("Непредвиденная ошибка. Попробуйте позже.", show_alert=True)
        return

    await state.clear()
    await callback.answer("Устройства докуплены")
    text = (
        "<b><tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Устройства докуплены</b>\n\n"
        f"<blockquote><tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Добавлено: <b>{result.get('slots_added', slots)}</b>\n"
        f"<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Списано: <b>{result.get('charged', price)} RUB</b>\n"
        f"<tg-emoji emoji-id='5877318502947229960'>💻</tg-emoji> Новый лимит: <b>{result.get('device_limit', '—')}</b></blockquote>\n\n"
        "<i><tg-emoji emoji-id='6005843436479975944'>🔁</tg-emoji> Обновите подписку в приложении, чтобы изменение отобразилось.</i>"
    )
    media = InputMediaPhoto(media=SUBSCRIPTION_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_back_devices_kb())
