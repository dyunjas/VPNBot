from aiogram import F, Router
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import MAIN_MENU_IMG
from backend.services.exceptions import PlanNotFound
from bot.navigation.subscription.keyboards import purchase_subscription_plan, subscription_plans_kb

router = Router()


@router.callback_query(F.data == "subscription")
async def subscription_plans_clb(callback: CallbackQuery, bot_api):
    plans = await bot_api.list_plans(tg_id=callback.from_user.id)

    if not plans:
        await callback.answer("Нет доступных тарифов", show_alert=True)
        return

    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption="Выберите тарифный план:")
    await callback.message.edit_media(media=media, reply_markup=subscription_plans_kb(plans))
    await callback.answer()


@router.callback_query(F.data.startswith("plans_page:"))
async def paginate_page_clb(callback: CallbackQuery, bot_api):
    page = int(callback.data.split(":")[1])
    plans = await bot_api.list_plans(tg_id=callback.from_user.id)

    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption="Выберите тарифный план:")
    await callback.message.edit_media(media=media, reply_markup=subscription_plans_kb(plans, page))
    await callback.answer()


@router.callback_query(F.data.startswith("plan:"))
async def select_plan_clb(callback: CallbackQuery, bot_api):
    try:
        _, plan_id_str, page_str = callback.data.split(":")
        plan_id = int(plan_id_str)
        page = int(page_str)
        plans = await bot_api.list_plans(tg_id=callback.from_user.id)
        plan = next((item for item in plans if int(item.get("id")) == plan_id), None)
        if not plan:
            raise PlanNotFound
    except (ValueError, PlanNotFound):
        await callback.answer("План не найден", show_alert=True)
        return

    gb_text = f"{plan.get('gb_limit')} GB" if plan.get("gb_limit") else "безлимит"

    text = (
        f"<b><tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> Тариф:</b> {plan.get('name')}\n"
        f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Стоимость:</b> {plan.get('price')} RUB\n"
        f"<b><tg-emoji emoji-id='5843799474362652262'>🔄</tg-emoji> Период:</b> {plan.get('period_days')} дней\n"
        f"<b><tg-emoji emoji-id='5931472654660800739'>📊</tg-emoji> Трафик Белых списков:</b> {gb_text}\n"
        f"<b><tg-emoji emoji-id='5931472654660800739'>📊</tg-emoji> Трафик обычных серверов:</b> безлимит\n"
        "<b><tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Устройств:</b> 3\n\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Подключиться к VPN можно сразу после оплаты.</i>"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text, parse_mode="HTML")

    await callback.message.edit_media(media=media, reply_markup=purchase_subscription_plan(plan_id, page))
    await callback.answer()

