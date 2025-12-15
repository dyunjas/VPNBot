from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from server.repositories.subscription_repository import SubscriptionRepository, NotEnoughBalanceError
from server.repositories.user_repository import UserRepository

from server.images import MAIN_MENU_IMG

from client.navigation.purchase.keyboards import fail_purchase_kb, success_purchase_kb

from server.core.logger_config import logger

router = Router()


@router.callback_query(F.data.startswith("purchase_plan"))
async def purchase_plan_clb(
    callback: CallbackQuery,
    subscription_repo: SubscriptionRepository,
    user_repo: UserRepository,
):
    tg_id = callback.from_user.id

    _, plan_id_str, *_ = callback.data.split(":")
    plan_id = int(plan_id_str)

    try:
        subscription = await subscription_repo.create_or_renew_subscription(
            tg_id=tg_id,
            plan_id=plan_id,
        )
    except NotEnoughBalanceError:
        text = "⚠️ Недостаточно средств, пополните баланс"
        media = InputMediaPhoto(
            media=MAIN_MENU_IMG,
            caption=text
        )
        await callback.message.edit_media(
            media=media,
            reply_markup=fail_purchase_kb()
        )
        await callback.answer()
        return

    except ValueError as e:
        logger.warning(f"Value error while creating subscription: {e}")
        await callback.answer("⚠️ Ошибка оформления подписки", show_alert=True)
        return

    except Exception as e:
        logger.exception(f"Unexpected error while creating subscription: {e}")
        await callback.answer("⚠️ Ошибка оформления подписки", show_alert=True)
        return

    user = await user_repo.get_user_by_tg_id(tg_id)
    plan = await subscription_repo.get_subscription_plan_by_id(plan_id)

    text = (
        f"<b>🌙 План:</b> {plan.name}\n"
        f"<b>🌟 Стоимость:</b> {plan.price} RUB\n"
        f"<b>✨ Активен до:</b> {subscription.current_period_end:%d.%m.%Y %H:%M}\n"
        f"<b>⭐️ Баланс:</b> {user.balance} RUB\n\n"
        "<i>ℹ️ Создайте ключ для доступа и начните пользоваться сервисом</i>"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=success_purchase_kb()
    )
    await callback.answer(
        text="✅ Подписка оформлена",
        show_alert=True
    )