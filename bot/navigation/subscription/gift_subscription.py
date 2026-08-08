from html import escape

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.images import SUBSCRIPTION_IMG
from backend.services.exceptions import InsufficientBalance, PlanNotFound, UserNotFound
from backend.states import GiftSubscriptionStates

router = Router()


def _confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Подарить", callback_data="gift_subscription_confirm", icon_custom_emoji_id="5776375003280838798", style="success")
    builder.button(text="Отмена", callback_data="subscription", icon_custom_emoji_id="5778527486270770928", style="danger")
    builder.adjust(1)
    return builder.as_markup()


def _back_plans_kb(page: int = 0):
    builder = InlineKeyboardBuilder()
    builder.button(text="К тарифам", callback_data=f"plans_page:{page}", icon_custom_emoji_id="5877536313623711363", style="primary")
    builder.adjust(1)
    return builder.as_markup()


@router.callback_query(F.data.startswith("gift_plan:"))
async def gift_subscription_start(callback: CallbackQuery, state: FSMContext, bot_api):
    try:
        _, plan_id_str, page_str = callback.data.split(":")
        plan_id = int(plan_id_str)
        page = int(page_str)
        plans = await bot_api.list_plans(tg_id=callback.from_user.id)
        plan = next((item for item in plans if int(item.get("id")) == plan_id), None)
        if not plan:
            raise PlanNotFound
    except (ValueError, PlanNotFound):
        await callback.answer("Тариф не найден", show_alert=True)
        return

    await state.update_data(gift_plan_id=plan_id, gift_plan_page=page, gift_plan_name=plan.get("name"), gift_plan_price=int(plan.get("price") or 0))
    await state.set_state(GiftSubscriptionStates.waiting_for_recipient)

    text = (
        f"<b><tg-emoji emoji-id='5956148757899776734'>🎁</tg-emoji> Подарить тариф «{escape(str(plan.get('name') or '—'))}»</b>\n\n"
        f"<blockquote><tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Стоимость: <b>{int(plan.get('price') or 0)} RUB</b></blockquote>\n\n"
        "Отправьте Telegram ID или username получателя.\n"
        "<i>Например: <code>123456789</code> или <code>@username</code></i>"
    )
    media = InputMediaPhoto(media=SUBSCRIPTION_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_back_plans_kb(page))
    await callback.answer()


@router.message(GiftSubscriptionStates.waiting_for_recipient)
async def gift_subscription_recipient(message: Message, state: FSMContext):
    recipient = (message.text or "").strip()
    if not recipient:
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Укажите Telegram ID или username получателя.")
        return

    data = await state.get_data()
    await state.update_data(gift_recipient=recipient)
    await state.set_state(GiftSubscriptionStates.waiting_for_confirmation)

    text = (
        "Проверьте данные подарка:\n\n"
        f"<blockquote><tg-emoji emoji-id='5967456680940671207'>🗃</tg-emoji> Тариф: <b>{escape(str(data.get('gift_plan_name') or '—'))}</b>\n"
        f"<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> К списанию: <b>{int(data.get('gift_plan_price') or 0)} RUB</b>\n"
        f"<tg-emoji emoji-id='5956148757899776734'>🎁</tg-emoji> Получатель: <b>{escape(recipient)}</b></blockquote>"
    )
    await message.answer_photo(photo=SUBSCRIPTION_IMG, caption=text, parse_mode="HTML", reply_markup=_confirm_kb())


@router.callback_query(GiftSubscriptionStates.waiting_for_confirmation, F.data == "gift_subscription_confirm")
async def gift_subscription_confirm(callback: CallbackQuery, state: FSMContext, bot_api):
    data = await state.get_data()
    plan_id = int(data.get("gift_plan_id") or 0)
    recipient = str(data.get("gift_recipient") or "").strip()
    page = int(data.get("gift_plan_page") or 0)
    if not plan_id or not recipient:
        await callback.answer("Сначала выберите тариф и получателя.", show_alert=True)
        return

    try:
        result = await bot_api.gift_subscription(tg_id=callback.from_user.id, plan_id=plan_id, recipient=recipient)
    except InsufficientBalance:
        await callback.answer("Недостаточно средств на балансе для подарка.", show_alert=True)
        return
    except UserNotFound:
        await callback.answer("Получатель не найден. Он должен хотя бы раз зайти в бота.", show_alert=True)
        return
    except PlanNotFound:
        await callback.answer("Тариф не найден.", show_alert=True)
        return
    except Exception:
        await callback.answer("Не удалось подарить подписку. Попробуйте позже.", show_alert=True)
        return

    await state.clear()
    recipient_info = result.get("recipient") or {}
    target = f"@{recipient_info.get('username')}" if recipient_info.get("username") else f"ID {recipient_info.get('tg_id') or recipient}"
    text = (
        "<b><tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Подписка подарена</b>\n\n"
        f"<blockquote><tg-emoji emoji-id='5956148757899776734'>🎁</tg-emoji> Получатель: <b>{escape(str(target))}</b>\n"
        f"<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Списано: <b>{result.get('charged', data.get('gift_plan_price') or 0)} RUB</b></blockquote>"
    )
    media = InputMediaPhoto(media=SUBSCRIPTION_IMG, caption=text, parse_mode="HTML")
    await callback.message.edit_media(media=media, reply_markup=_back_plans_kb(page))
    await callback.answer("Подарок отправлен")
