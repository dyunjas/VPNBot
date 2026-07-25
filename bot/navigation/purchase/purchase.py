from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto

from backend.images import SUBSCRIPTION_IMG
from backend.services.exceptions import BannedUser, InsufficientBalance, PlanNotFound, TooEarlyToRenew, UserNotFound
from bot.navigation.purchase.keyboards import fail_purchase_kb, success_purchase_kb
from bot.utils.maintenance import answer_maintenance_callback, is_maintenance_error

router = Router()


@router.callback_query(F.data.startswith("purchase_plan"))
async def purchase_plan_clb(
    callback: CallbackQuery,
    bot_api,
):
    tg_id = callback.from_user.id

    try:
        await bot_api.get_user_by_tg_id(tg_id)
    except UserNotFound:
        await callback.answer(
            "Пользователь не найден. Попробуйте перезапустить бота."
        , show_alert=True)
        return

    _, plan_id_str, *_ = callback.data.split(":")
    plan_id = int(plan_id_str)

    try:
        sub = await bot_api.buy_subscription(tg_id=tg_id, plan_id=plan_id, auto_renew=True)
    except UserNotFound:
        await callback.answer("Пользователь не найден", show_alert=True)
        return
    except InsufficientBalance:
        text = "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Недостаточно средств, пополните баланс"
        media = InputMediaPhoto(media=SUBSCRIPTION_IMG, caption=text)
        await callback.message.edit_media(media=media, reply_markup=fail_purchase_kb())
        await callback.answer()
        return
    except PlanNotFound:
        await callback.answer("План не найден", show_alert=True)
        return
    except TooEarlyToRenew:
        await callback.answer("Подписку нельзя продлить раньше, чем за 3 дня до её окончания", show_alert=True)
        return
    except BannedUser:
        await callback.answer("Ваш аккаунт заблокирован. Покупка недоступна.", show_alert=True)
        return
    except Exception as e:
        await callback.answer(f"Ошибка оформления подписки: {e}; обратитесь в поддержку", show_alert=True)
        return

    plan = next((item for item in await bot_api.list_plans(tg_id=tg_id) if int(item.get("id")) == plan_id), None)
    if not plan:
        return

    try:
        await callback.bot.send_gift(
            gift_id="5170233102089322756",
            user_id=tg_id,
            text=f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji>Спасибо за покупку!",
            text_parse_mode="HTML",
        )
    except Exception:
        pass

    gb_text = f"{plan.get('gb_limit')} GB" if plan.get("gb_limit") else "безлимит"
    device_text = str(plan.get("device_limit") if plan.get("device_limit") is not None else 0)
    
    text = (
        f"<b><tg-emoji emoji-id='5967456680940671207'>🗃</tg-emoji> Тариф</b> «{plan.get('name')}»\n\n"
        f"<blockquote><b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Стоимость:</b> {plan.get('price')} RUB\n"
        f"<b><tg-emoji emoji-id='5843799474362652262'>🔄</tg-emoji> Срок действия:</b> {plan.get('period_days')} дней\n"
        f"<b><tg-emoji emoji-id='5967816500415827773'>💻</tg-emoji> Количество устройств:</b> {device_text}</blockquote>\n\n"
        "<blockquote><b><tg-emoji emoji-id='5931472654660800739'>📊</tg-emoji> Трафик</b>\n"
        f"<b>——LTE-серверы:</b> {gb_text}\n"
        f"<b>——Обычные серверы:</b> безлимит</blockquote>\n\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> Перейдите в меню «Моя подписка», чтобы посмотреть детали.</i>"
        )
    media = InputMediaPhoto(media=SUBSCRIPTION_IMG, caption=text)

    await callback.message.edit_media(media=media, reply_markup=success_purchase_kb())
    await callback.answer("Подписка оформлена", show_alert=True)
