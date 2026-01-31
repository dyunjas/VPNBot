from datetime import datetime, timedelta
import asyncio

from backend.database.session import async_session
from backend.images import MAIN_MENU_IMG

from backend.core.loader import bot
from backend.core.config import settings
from backend.core.logger_config import logger

from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.services import SubscriptionService, UserService, VPNService
from backend.services.exceptions import UserNotFound, SubscriptionNotFound


AGENT_TOKEN = settings.XRAY_AUTH


async def expire_checker():
    async with async_session() as session:
        now = datetime.now()
        warning_time = now + timedelta(hours=6)

        sub_service = SubscriptionService(session)
        user_service = UserService(session)
        vpn_service = VPNService(session, xray_auth_token=AGENT_TOKEN)

        try:
            expired_subs = await sub_service.list_active_expired(now=now)
        except Exception as e:
            logger.error(f"Expire checker: failed to load expired subs: {e}")
            expired_subs = []

        for sub in expired_subs:
            try:
                await sub_service.mark_expired(subscription_id=sub.id)
            except Exception as e:
                logger.error(f"Expire checker: mark_expired failed sub_id={getattr(sub,'id',None)}: {e}")
                continue

            try:
                await vpn_service.delete_all_user_keys(sub.user_id)
            except Exception as e:
                logger.error(f"Expire checker: delete keys failed user_id={sub.user_id}: {e}")

            try:
                user = await user_service.get_by_id(sub.user_id)
            except UserNotFound:
                continue
            except Exception as e:
                logger.error(f"Expire checker: get user failed user_id={sub.user_id}: {e}")
                continue

            builder = InlineKeyboardBuilder()
            builder.button(
                text="🌙 Продлить",
                callback_data="my_subscription"
            )

            text = (
                "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Внимание! "
                "<tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji></b>\n\n"
                "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ваша подписка истекла. "
                "Доступ к ключам остановлен.\n"
                "Продлите подписку, чтобы восстановить доступ к сервису."
            )

            try:
                await bot.send_photo(
                    user.tg_id,
                    photo=MAIN_MENU_IMG,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Expire checker: notify expired failed tg_id={user.tg_id}: {e}")

        try:
            soon_subs = await sub_service.list_active_ending_between(start=now, end=warning_time)
        except Exception as e:
            logger.error(f"Expire checker: failed to load soon subs: {e}")
            soon_subs = []

        for sub in soon_subs:
            try:
                user = await user_service.get_by_id(sub.user_id)
            except UserNotFound:
                continue
            except Exception as e:
                logger.error(f"Expire checker: get user failed user_id={sub.user_id}: {e}")
                continue

            try:
                remain = sub.current_period_end - now
                hours = max(1, int(remain.total_seconds() // 3600))

                builder = InlineKeyboardBuilder()
                builder.button(text="🌙 Продлить", callback_data="my_subscription")

                text = (
                    "<b><tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji> Внимание! "
                    "<tg-emoji emoji-id='5881702736843511327'>⚠️</tg-emoji></b>\n\n"
                    f"<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Ваша подписка скоро истечёт! Осталось ≈ {hours} ч <tg-emoji emoji-id='5900104897885376843'>🕓</tg-emoji>. "
                    "Продлите подписку, чтобы не потерять доступ к сервису!"
                )

                await bot.send_photo(
                    user.tg_id,
                    photo=MAIN_MENU_IMG,
                    caption=text,
                    parse_mode="HTML",
                    reply_markup=builder.as_markup()
                )
            except Exception as e:
                logger.error(f"Expire checker: notify soon failed tg_id={user.tg_id}: {e}")


async def expire_checker_loop(interval_sec: int = 300):
    while True:
        try:
            await expire_checker()
        except Exception:
            logger.exception("Expire checker execution error")
        await asyncio.sleep(interval_sec)
