import asyncio
from datetime import datetime, timedelta, timezone

from aiogram.utils.keyboard import InlineKeyboardBuilder

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


async def _notify_subscription_ending_soon(bot, tg_id: int, hours: int):
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


async def _notify_subscription_renewed(bot, tg_id: int, end_dt: datetime):
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


async def expire_checker(bot):
    async with async_session() as session:
        now = datetime.now(timezone.utc)
        warning_time = now + timedelta(hours=6)

        sub_service = SubscriptionService(session)
        user_service = UserService(session)
        billing_service = BillingService(session)
        remnawave_service = RemnaWaveService(session)

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

            # notify soon
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


async def expire_checker_loop(bot, interval_sec: int = 300):
    while True:
        try:
            await expire_checker(bot)
        except Exception:
            logger.exception("Expire checker execution error")

        await asyncio.sleep(interval_sec)
