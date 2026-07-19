import asyncio
from datetime import datetime, timedelta, timezone

from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.database.session import async_session
from backend.images import MAIN_MENU_IMG
from backend.services import (
    BillingService,
    SubscriptionService,
    UserService,
    RemnaWaveService
)
from backend.services.exceptions import (
    InsufficientBalance,
    TooEarlyToRenew,
    UserNotFound
)


async def _notify_subscription_expired(bot, tg_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Продлить подписку", callback_data="subscription")
    builder.adjust(1)

    text = (
        "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji>Подписка закончилась</b>\n\n"
        "Доступ к VPN временно остановлен. Продлите подписку, и сервис снова заработает на вашей текущей ссылке.\n\n"
        "Если вы уже продлили подписку, обновите подписку в приложении."
    )

    await bot.send_photo(
        tg_id,
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

async def _notify_subscription_ending_soon(bot, tg_id: int, hours: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Продлить подписку", callback_data="subscription")
    builder.adjust(1)

    if hours >= 24:
        remaining_text = "примерно 1 день"
    else:
        remaining_text = f"примерно {hours} ч."

    text = (
        "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Подписка скоро закончится</b>\n\n"
        f"До окончания осталось {remaining_text}. Продлите заранее, чтобы VPN продолжил работать.\n\n"
        "После продления ссылка останется прежней. Если автопродление включено, проверьте, что на балансе достаточно средств."
    )

    await bot.send_photo(
        tg_id,
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

async def _notify_subscription_renewed(bot, tg_id: int, end_dt: datetime):
    text = (
        "<b><tg-emoji emoji-id='5881702736843511327'>✅</tg-emoji> Подписка продлена автоматически</b>\n\n"
        f"Новая дата окончания: <b>{end_dt:%d.%m.%Y %H:%M}</b>\n"
        "Ссылка для подключения осталась прежней. Средства списаны с вашего баланса."
    )

    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Моя подписка", callback_data="vpn_subscription")
    builder.adjust(1)

    await bot.send_photo(
        tg_id,
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )

async def expire_checker(bot):
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        warning_time = now + timedelta(hours=6)
        webhook_expiration_mode = bool(settings.REMNAWAVE_WEBHOOK_EXPIRATION_ENABLED)

        sub_service = SubscriptionService(session)
        user_service = UserService(session)
        billing_service = BillingService(session)
        remnawave_service = RemnaWaveService(session)

        try:
            if not webhook_expiration_mode:
                try:
                    expired_subs = await sub_service.list_active_expired(now=now)
                except Exception as e:
                    logger.error("Expire checker: failed to load expired subs: %s", e)
                    expired_subs = []

                for sub in expired_subs:
                    try:
                        await sub_service.mark_expired(subscription_id=sub.id)
                    except Exception as e:
                        logger.error("mark_expired failed sub_id=%s: %s", sub.id, e)
                        continue

                    try:
                        user = await user_service.get_by_id(sub.user_id)
                    except UserNotFound:
                        continue

                    try:
                        if remnawave_service.enabled:
                            await remnawave_service.sync_user_state(
                                user=user,
                                subscription=sub,
                                status="EXPIRED",
                            )
                    except Exception as e:
                        logger.error("remnawave expired status sync failed user_id=%s: %s", sub.user_id, e)

                    try:
                        await _notify_subscription_expired(bot, user.tg_id)
                    except Exception as e:
                        logger.error("notify expired failed tg_id=%s: %s", user.tg_id, e)

            try:
                soon_subs = await sub_service.list_active_ending_between(
                    start=now,
                    end=warning_time
                )
            except Exception as e:
                logger.error("failed to load soon subs: %s", e)
                soon_subs = []

            for sub in soon_subs:
                try:
                    user = await user_service.get_by_id(sub.user_id)
                except UserNotFound:
                    continue

                if bool(getattr(user, "banned", False)):
                    logger.info("[scheduler][expire] skip banned user_id=%s sub_id=%s", user.id, sub.id)
                    continue

                # auto renew
                if sub.auto_renew:
                    try:
                        renewed = await billing_service.buy_subscription(
                            user_id=sub.user_id,
                            plan_id=sub.plan_id,
                            auto_renew=True,
                        )

                        end = renewed.current_period_end
                        if end and end.tzinfo is None:
                            end = end.replace(tzinfo=timezone.utc)

                        if end:
                            await _notify_subscription_renewed(bot, user.tg_id, end)

                        continue

                    except (InsufficientBalance, TooEarlyToRenew):
                        pass
                    except Exception as e:
                        logger.error(
                            "auto-renew failed user_id=%s sub_id=%s: %s",
                            sub.user_id,
                            sub.id,
                            e,
                        )

                if webhook_expiration_mode:
                    continue

                try:
                    period_end = sub.current_period_end
                    if not period_end:
                        continue

                    if period_end.tzinfo is None:
                        period_end = period_end.replace(tzinfo=timezone.utc)
                    else:
                        period_end = period_end.astimezone(timezone.utc)

                    remain = period_end - now
                    hours = max(1, int(remain.total_seconds() // 3600))

                    await _notify_subscription_ending_soon(bot, user.tg_id, hours)

                except Exception as e:
                    logger.error("notify soon failed tg_id=%s: %s", user.tg_id, e)
        finally:
            await billing_service.close_clients()


async def expire_checker_loop(bot, interval_sec: int = 300):
    while True:
        try:
            await expire_checker(bot)
        except Exception:
            logger.exception("Expire checker execution error")

        await asyncio.sleep(interval_sec)
