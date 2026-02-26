import asyncio
from datetime import datetime, timedelta, timezone

from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.core.config import settings
from backend.core.loader import bot
from backend.core.logger_config import logger
from backend.database.session import async_session
from backend.images import MAIN_MENU_IMG
from backend.services import BillingService, SubscriptionService, UserService, VPNService
from backend.services.exceptions import InsufficientBalance, SubscriptionNotFound, TooEarlyToRenew, UserNotFound


AGENT_TOKEN = settings.XRAY_AUTH


async def _notify_subscription_expired(tg_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Продлить", callback_data="subscription")

    text = (
        "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Внимание!</b>\n\n"
        "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ваша подписка истекла. "
        "Доступ к ключам остановлен.\n"
        "Продлите подписку, чтобы восстановить доступ к сервису."
    )
    await bot.send_photo(
        tg_id,
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


async def _notify_subscription_ending_soon(tg_id: int, hours: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Продлить", callback_data="subscription")

    text = (
        "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Внимание!</b>\n\n"
        f"<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ваша подписка скоро истечёт! Осталось примерно {hours} ч.\n"
        "Продлите подписку, чтобы не потерять доступ к сервису."
    )
    await bot.send_photo(
        tg_id,
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


async def _notify_subscription_renewed(tg_id: int, end_dt: datetime):
    text = (
        "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> <b>Подписка продлена автоматически</b>\n\n"
        f"Новый срок действия: <b>{end_dt:%d.%m.%Y %H:%M}</b>\n"
        "Средства списаны с вашего баланса."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="🌙 Подписка", callback_data="vpn_subscription")
    await bot.send_photo(
        tg_id,
        photo=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML",
        reply_markup=builder.as_markup(),
    )


async def expire_checker():
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        warning_time = now + timedelta(hours=6)

        sub_service = SubscriptionService(session)
        user_service = UserService(session)
        billing_service = BillingService(session)
        vpn_service = VPNService(session, xray_auth_token=AGENT_TOKEN)

        try:
            expired_subs = await sub_service.list_active_expired(now=now)
        except Exception as e:
            logger.error("Expire checker: failed to load expired subs: %s", e)
            expired_subs = []

        for sub in expired_subs:
            try:
                await sub_service.mark_expired(subscription_id=sub.id)
            except Exception as e:
                logger.error(
                    "Expire checker: mark_expired failed sub_id=%s: %s",
                    getattr(sub, "id", None),
                    e,
                )
                continue

            try:
                await vpn_service.delete_all_user_keys(sub.user_id)
            except Exception as e:
                logger.error("Expire checker: delete keys failed user_id=%s: %s", sub.user_id, e)

            try:
                user = await user_service.get_by_id(sub.user_id)
            except UserNotFound:
                continue
            except Exception as e:
                logger.error("Expire checker: get user failed user_id=%s: %s", sub.user_id, e)
                continue

            try:
                await _notify_subscription_expired(user.tg_id)
            except Exception as e:
                logger.error("Expire checker: notify expired failed tg_id=%s: %s", user.tg_id, e)

        try:
            soon_subs = await sub_service.list_active_ending_between(start=now, end=warning_time)
        except Exception as e:
            logger.error("Expire checker: failed to load soon subs: %s", e)
            soon_subs = []

        for sub in soon_subs:
            try:
                user = await user_service.get_by_id(sub.user_id)
            except UserNotFound:
                continue
            except Exception as e:
                logger.error("Expire checker: get user failed user_id=%s: %s", sub.user_id, e)
                continue

            if sub.auto_renew:
                try:
                    renewed = await billing_service.buy_subscription(
                        user_id=sub.user_id,
                        plan_id=sub.plan_id,
                        auto_renew=True,
                    )
                    renewed_end = renewed.current_period_end
                    if renewed_end and renewed_end.tzinfo is None:
                        renewed_end = renewed_end.replace(tzinfo=timezone.utc)
                    if renewed_end:
                        await _notify_subscription_renewed(user.tg_id, renewed_end)
                    continue
                except (InsufficientBalance, TooEarlyToRenew):
                    pass
                except Exception as e:
                    logger.error(
                        "Expire checker: auto-renew failed user_id=%s sub_id=%s: %s",
                        sub.user_id,
                        sub.id,
                        e,
                    )

            try:
                period_end = sub.current_period_end
                if period_end and period_end.tzinfo is None:
                    period_end = period_end.replace(tzinfo=timezone.utc)
                elif period_end:
                    period_end = period_end.astimezone(timezone.utc)
                else:
                    continue

                remain = period_end - now
                hours = max(1, int(remain.total_seconds() // 3600))
                await _notify_subscription_ending_soon(user.tg_id, hours)
            except Exception as e:
                logger.error("Expire checker: notify soon failed tg_id=%s: %s", user.tg_id, e)


async def expire_checker_loop(interval_sec: int = 300):
    while True:
        try:
            await expire_checker()
        except Exception:
            logger.exception("Expire checker execution error")
        await asyncio.sleep(interval_sec)
