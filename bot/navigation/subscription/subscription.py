from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG
from backend.services.exceptions import PlanNotFound
from backend.services.subscription_service import SubscriptionService
from bot.navigation.subscription.keyboards import purchase_subscription_plan, subscription_plans_kb

router = Router()


@router.callback_query(F.data == "subscription")
async def subscription_plans_clb(callback: CallbackQuery, subscription_service: SubscriptionService):
    plans = await subscription_service.list_plans()

    if not plans:
        await callback.answer("Нет доступных тарифов", show_alert=True)
        return

    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption="Выберите тарифный план:")
    await callback.message.edit_media(media=media, reply_markup=subscription_plans_kb(plans))
    await callback.answer()


@router.callback_query(F.data.startswith("plans_page:"))
async def paginate_page_clb(callback: CallbackQuery, subscription_service: SubscriptionService):
    page = int(callback.data.split(":")[1])
    plans = await subscription_service.list_plans()

    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption="Выберите тарифный план:")
    await callback.message.edit_media(media=media, reply_markup=subscription_plans_kb(plans, page))
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def select_plan_clb(callback: CallbackQuery, subscription_service: SubscriptionService):
    try:
        _, plan_id_str, page_str = callback.data.split(":")
        plan_id = int(plan_id_str)
        page = int(page_str)
        plan = await subscription_service.get_plan(plan_id)
    except (ValueError, PlanNotFound):
        await callback.answer("План не найден", show_alert=True)
        return

    gb_text = f"{plan.gb_limit} GB" if plan.gb_limit else "безлимит"
    devices = int(getattr(plan, "device_limit", 0) or 0)

    text = (
        f"<b><tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> Тариф:</b> {plan.name}\n"
        f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Стоимость:</b> {plan.price} RUB\n"
        f"<b><tg-emoji emoji-id='5843799474362652262'>🔄</tg-emoji> Период:</b> {plan.period_days} дней\n"
        f"<b><tg-emoji emoji-id='5931472654660800739'>📊</tg-emoji> Трафик:</b> {gb_text}\n"
        f"<b><tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Устройств:</b> {devices}\n\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Подключиться к VPN можно сразу после оплаты.</i>"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")

    await callback.message.edit_media(media=media, reply_markup=purchase_subscription_plan(plan_id, page))
    await callback.answer()
