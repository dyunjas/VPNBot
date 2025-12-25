from aiogram import Router, F
from aiogram.types import CallbackQuery, Message, InputMediaPhoto

from server.repositories.subscription_repository import SubscriptionRepository

from client.navigation.subscription.keyboards import (
    subscription_plans_kb, 
    purchase_subscription_plan,
    my_subscription_plan_kb
)

from server.images import MAIN_MENU_IMG

router = Router()

@router.callback_query(F.data == "my_subscription")
async def my_subscription_plan_clb(callback: CallbackQuery, subscription_repo: SubscriptionRepository):
    tg_id = callback.from_user.id
    subscription = await subscription_repo.get_user_subscription_by_tg_id(tg_id)

    if subscription:
        until = subscription.current_period_end.strftime("%d.%m.%Y %H:%M")
        status_map = {
            "active": "✅ Активна",
            "past_due": "⚠️ Просрочена",
            "expired": "⏳ Истекла",
            "canceled": "🚫 Отменена"
        }

        status = status_map.get(subscription.status.value, subscription.status.value)
        text = (
            f"<b>🌙 Ваша подписка</b>\n"
            f"<b>🌟 План:</b> {subscription.plan.name}\n"
            f"<b>✨ Активна до:</b> {until}\n"
            f"<b>⭐️ Статус:</b> {status}"
        )
    else:
        text = "У вас нет активной подписки 🌙"

    await callback.message.edit_caption(caption=text, reply_markup=my_subscription_plan_kb())
    await callback.answer()


@router.callback_query(F.data == "subscription")
async def subscription_plans_clb(callback: CallbackQuery, subscription_repo: SubscriptionRepository):
    plans = await subscription_repo.get_all_subscription_plans()

    if not plans:
        await callback.answer("Нет доступных подписок", show_alert=True)
        return
    
    text = "Выберите тарифный план:"
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=subscription_plans_kb(plans)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("plans_page:"))
async def paginate_page_clb(callback: CallbackQuery, subscription_repo: SubscriptionRepository):
    page = int(callback.data.split(":")[1])
    plans = await subscription_repo.get_all_subscription_plans()

    text = "Выберите тарифный план:"
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=subscription_plans_kb(plans, page)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("plan:"))
async def select_plan_clb(callback: CallbackQuery, subscription_repo: SubscriptionRepository):
    _, plan_id_str, page_str = callback.data.split(":")
    plan_id = int(plan_id_str)
    page = int(page_str)
    plan = await subscription_repo.get_subscription_plan_by_id(plan_id)

    if not plan:
        await callback.answer("План не найден", show_alert=True)
        return
    
    text = (
        f"<b>🌙 План:</b> {plan.name}\n"
        f"<b>🌟 Стоимость:</b> {plan.price} RUB\n"
        f"<b>✨ Период:</b> {plan.period_days} дней\n"
        f"<b>📊 Лимит гигабайт:</b> безлимит GB.\n\n"
        f"<i>ℹ️ Подключиться к VPN можно сразу после оплаты.</i>"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=purchase_subscription_plan(plan_id, page)
    )
    await callback.answer()