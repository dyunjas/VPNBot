from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from backend.images import MAIN_MENU_IMG
from backend.services.subscription_service import SubscriptionService
from backend.services.exceptions import PlanNotFound
from bot.navigation.subscription.keyboards import (
    subscription_plans_kb, 
    purchase_subscription_plan
)

router = Router()


@router.callback_query(F.data == "subscription")
async def subscription_plans_clb(
    callback: CallbackQuery, 
    subscription_service: SubscriptionService
):
    plans = await subscription_service.list_plans()

    if not plans:
        await callback.answer("Нет доступных подписок", show_alert=True)
        return
    
    text = "Выберите тарифный план:"
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)

    await callback.message.edit_media(
        media=media,
        reply_markup=subscription_plans_kb(plans)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plans_page:"))
async def paginate_page_clb(
    callback: CallbackQuery, 
    subscription_service: SubscriptionService
):
    page = int(callback.data.split(":")[1])
    plans = await subscription_service.list_plans()

    text = "Выберите тарифный план:"
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)

    await callback.message.edit_media(
        media=media,
        reply_markup=subscription_plans_kb(plans, page)
    )
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def select_plan_clb(
    callback: CallbackQuery, 
    subscription_service: SubscriptionService
):
    try:
        _, plan_id_str, page_str = callback.data.split(":")
        plan_id = int(plan_id_str)
        page = int(page_str)

        plan = await subscription_service.get_plan(plan_id)
    except (ValueError, PlanNotFound):
        await callback.answer("План не найден", show_alert=True)
        return

    text = (
        f"<b><tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> План:</b> {plan.name}\n"
        f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Стоимость:</b> {plan.price} RUB\n"
        f"<b><tg-emoji emoji-id='5843799474362652262'>🔄</tg-emoji> Период:</b> {plan.period_days} дней\n"
        f"<b><tg-emoji emoji-id='5931472654660800739'>📊</tg-emoji> Лимит гигабайт:</b> {plan.gb_limit if plan.gb_limit else 'безлимит'} GB\n\n"
        f"<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Подключиться к VPN можно сразу после оплаты.</i>"
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
