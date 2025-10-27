from datetime import datetime, timedelta
import asyncio

from sqlalchemy import select

from server.database.session import async_session
from server.database.models import Subscription, SubStatus, User
from server.repositories.key_repository import KeyRepository
from server.images import MAIN_MENU_IMG

from server.core.loader import bot, settings

from server.core.logger_config import logger

from aiogram.utils.keyboard import InlineKeyboardBuilder

from aiogram.types import InputMediaPhoto

AGENT_TOKEN = settings.XRAY_AUTH

async def expire_checker():
    async with async_session() as session:
        now = datetime.now()
        warning_time = now + timedelta(hours=6)

        expired_q = select(Subscription).where(
            Subscription.status == SubStatus.active,
            Subscription.current_period_end < now
        )
        expired_subs = (await session.execute(expired_q)).scalars().all()

        key_repo = KeyRepository(session)

        for sub in expired_subs:
            sub.status = SubStatus.expired
            await session.commit()

            await key_repo.delete_all_keys_for_user(
                sub.user_id,
                auth_token=AGENT_TOKEN
            )

            user = await session.get(User, sub.user_id)
            if user:
                builder = InlineKeyboardBuilder()
                builder.button(text="🌙 Продлить", callback_data="my_subscription")
                try:
                    text = (
                        f"<b>🚨 Внимание! 🚨</b>\n\n"
                        f"❗️ Ваша подписка истекла. Доступ к ключам отключен.\n"
                        f"Продлите подписку, чтобы восстановить доступ к сервису."
                    )
                    await bot.send_photo(
                        user.tg_id,
                        photo=MAIN_MENU_IMG,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
                except Exception as e:
                    logger.error(f"Notification error: {user.tg_id}: {e}")

        soon_q = select(Subscription).where(
            Subscription.status == SubStatus.active,
            Subscription.current_period_end.between(now, warning_time)
        )
        soon_subs = (await session.execute(soon_q)).scalars().all()

        for sub in soon_subs:
            user = await session.get(User, sub.user_id)
            if user:
                try:
                    remain = sub.current_period_end - now
                    hours = max(1, int(remain.total_seconds() // 3600))
                    builder = InlineKeyboardBuilder()
                    builder.button(text="🌙 Продлить", callback_data="my_subscription")
                    text = (
                        f"<b>🚨 Внимание! 🚨</b>\n\n"
                        f"⚠️ Ваша подписка скоро истечёт! Осталось ≈ {hours} ч ⏳. Продлите подписку, чтобы не потерять доступ к сервису!"
                    )
                    await bot.send_photo(
                        user.tg_id,
                        photo=MAIN_MENU_IMG,
                        caption=text,
                        parse_mode="HTML",
                        reply_markup=builder.as_markup()
                    )
                except Exception as e:
                    logger.error(f"Notification error: {user.tg_id}: {e}")

        await session.commit()


async def expire_checker_loop(interval_sec: int = 300):
    while True:
        try:
            await expire_checker()
        except Exception:
            logger.error("[expire_checker_loop] execution error")
        await asyncio.sleep(interval_sec)
