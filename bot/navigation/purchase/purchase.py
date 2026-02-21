from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from backend.images import MAIN_MENU_IMG

from bot.navigation.purchase.keyboards import fail_purchase_kb, success_purchase_kb

from backend.services import UserService, BillingService, SubscriptionService
from backend.services.exceptions import (
    UserNotFound, InsufficientBalance, 
    PlanNotFound, TooEarlyToRenew
)
from backend.core.logger_config import logger

router = Router()

@router.callback_query(F.data.startswith("purchase_plan"))
async def purchase_plan_clb(
    callback: CallbackQuery,
    billing_service: BillingService,
    subscription_service: SubscriptionService,
    user_service: UserService
):
    tg_id = callback.from_user.id

    try:
        user = await user_service.get_by_tg_id(tg_id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    _, plan_id_str, *_ = callback.data.split(":")
    plan_id = int(plan_id_str)

    try:
        sub = await billing_service.buy_subscription(
            user_id=user.id,
            plan_id=plan_id,
        )

    except UserNotFound:
        await callback.message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден", show_alert=True)
        return

    except InsufficientBalance:
        text = "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Недостаточно средств, пополните баланс"
        media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)
        await callback.message.edit_media(media=media, reply_markup=fail_purchase_kb())
        await callback.answer()
        return

    except PlanNotFound:
        await callback.answer("План не найден", show_alert=True)
        return
    
    except TooEarlyToRenew:
        await callback.answer("Подписку нельзя продлить раньше, чем за 3 дня до её окончания", show_alert=True)
        return

    except Exception as e:
        logger.exception(f"Ошибка при покупке подписки: {e}")
        await callback.message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ошибка оформления подписки", show_alert=True)
        return
    
    try:
        await callback.bot.send_gift(
            gift_id="5170233102089322756", 
            user_id=tg_id,
            text=f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji>Спасибо за покупку!",
            text_parse_mode="HTML"
        )
    except Exception as e:
        print(f"{e}")
        pass
    
    plan = await subscription_service.get_plan(plan_id)

    text = (
        f"<b><tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> План:</b> {plan.name}\n"
        f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Стоимость:</b> {plan.price} RUB\n"
        f"<b><tg-emoji emoji-id='5843799474362652262'>🔄</tg-emoji> Период:</b> {plan.period_days} дней\n"
        f"<b><tg-emoji emoji-id='5931472654660800739'>📊</tg-emoji> Лимит гигабайт:</b> {plan.gb_limit if plan.gb_limit else 'безлимит'} GB\n\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Создайте VPN ссылку и начните пользоваться сервисом.</i>"
    )
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)

    await callback.message.edit_media(media=media, reply_markup=success_purchase_kb())
    await callback.answer("Подписка оформлена", show_alert=True)
