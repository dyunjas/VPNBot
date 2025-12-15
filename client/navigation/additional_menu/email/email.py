from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.fsm.context import FSMContext

from server.repositories.user_repository import UserRepository
from server.images import MAIN_MENU_IMG
from server.states import EmailStates
from server.core.logger_config import logger

import re
from datetime import datetime
import asyncio

from client.navigation.additional_menu.email.keyboards import back_profile_kb
from client.navigation.additional_menu.email.utils import send_email_code, generate_code
from client.navigation.additional_menu.email.otp_hash import otp_verify

router = Router()
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.callback_query(F.data == "email")
async def email_clb(callback: CallbackQuery, state: FSMContext, user_repo: UserRepository):
    email = await user_repo.get_user_email(callback.from_user.id)

    if email:
        text = (
            f"📨 Ваша почта: {email}\n\n"
            "🎁 Раз в неделю на привязанную почту будут приходить <b>бесплатные</b> промокоды для пополнения баланса!"
        )
    else:
        await state.set_state(EmailStates.waiting_email)
        text = (
            "ℹ️ Благодаря привязанной почте, вы не потеряете доступ к вашему профилю Lunet VPN в случае блокировки Telegram/Вашего Telegram профиля.\n\n"
            "🎁 Раз в неделю на привязанную почту будут приходить <b>бесплатные</b> промокоды для пополнения баланса!\n\n"
            "📨 Введите почту для привязки:"
        )

    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)
    await callback.message.edit_media(media=media, reply_markup=back_profile_kb())
    await callback.answer()


@router.message(EmailStates.waiting_email)
async def got_email(message: Message, state: FSMContext, user_repo: UserRepository):
    email = (message.text or "").strip().lower()

    if not EMAIL_RE.match(email):
        return await message.answer("❌ Неверный email. Введите ещё раз:")

    if await user_repo.check_email_taken(email):
        return await message.answer("❌ Эта почта уже используется другим аккаунтом.")

    ver = await user_repo.get_email_verification(message.from_user.id)
    if ver and (datetime.now() - ver.last_sent_at).total_seconds() < 60:
        await state.set_state(EmailStates.waiting_code)
        return await message.answer("❗️ Код уже отправлен. Введите код из письма:")

    code = generate_code()
    await user_repo.upsert_email_verification(message.from_user.id, email, code)

    try:
        await asyncio.to_thread(send_email_code, email, code)
    except Exception as e:
        logger.exception("SMTP send failed: %r", e)
        await message.answer(f"❌ Не удалось отправить письмо: {type(e).__name__}: {e}")
        return

    await state.set_state(EmailStates.waiting_code)
    await message.answer("✅ Код отправлен на почту. Введите код из 6 цифр:")


@router.message(EmailStates.waiting_code)
async def got_code(message: Message, state: FSMContext, user_repo: UserRepository):
    code = (message.text or "").strip()

    if not re.fullmatch(r"\d{6}", code):
        return await message.answer("❌ Введите код из 6 цифр:")

    ver = await user_repo.get_email_verification(message.from_user.id)
    if not ver:
        await state.clear()
        return await message.answer("❌ Нет активного кода. Начните заново.")

    if datetime.now() > ver.expires_at:
        await user_repo.delete_email_verification(message.from_user.id)
        await state.clear()
        return await message.answer("⏳ Код истёк. Нажмите Email и запросите новый.")

    if ver.attempts >= 5:
        await user_repo.delete_email_verification(message.from_user.id)
        await state.clear()
        return await message.answer("🚫 Слишком много попыток. Начните заново.")

    if not otp_verify(code, ver.code_hash):
        await user_repo.increase_email_verification_attempts(message.from_user.id)
        return await message.answer("❌ Код неверный. Попробуйте ещё раз:")

    ok = await user_repo.set_email_unique(message.from_user.id, ver.email)
    await user_repo.delete_email_verification(message.from_user.id)
    await state.clear()

    if not ok:
        return await message.answer("❌ Эта почта уже привязана к другому аккаунту.")

    await message.answer(
        text=f"✅ Почта успешно привязана: {ver.email}"
    )
