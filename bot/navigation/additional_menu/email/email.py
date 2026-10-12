import re
import secrets
import smtplib
import time
from email.message import EmailMessage

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from backend.core.config import settings
from backend.core.logger_config import logger
from backend.email_templates import render_code_email
from backend.images import PROFILE_IMG
from backend.services.exceptions import UserNotFound
from backend.states import EmailBindStates
from bot.navigation.additional_menu.email.keyboards import email_bind_kb, email_bind_cancel_kb
from bot.utils.html import html_escape


router = Router()

OTP_TTL_SEC = 600
_EMAIL_CODE_STORE: dict[str, dict] = {}
EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


def _cleanup_codes() -> None:
    now = int(time.time())
    stale = [k for k, v in _EMAIL_CODE_STORE.items() if int(v.get("expires_at", 0)) < now]
    for key in stale:
        _EMAIL_CODE_STORE.pop(key, None)


def _put_code(tg_id: int, email: str, code: str) -> None:
    _cleanup_codes()
    _EMAIL_CODE_STORE[str(tg_id)] = {
        "email": email,
        "code": code,
        "expires_at": int(time.time()) + OTP_TTL_SEC,
    }


def _verify_code(tg_id: int, code: str) -> tuple[bool, str | None]:
    _cleanup_codes()
    key = str(tg_id)
    rec = _EMAIL_CODE_STORE.get(key)
    if not rec:
        return False, None
    if str(rec.get("code")) != str(code).strip():
        return False, None
    _EMAIL_CODE_STORE.pop(key, None)
    return True, str(rec.get("email") or "")


def _smtp_send_code(email: str, code: str, purpose: str = "bind") -> None:
    host = (getattr(settings, "SMTP_HOST", None) or "").strip()
    user = (getattr(settings, "SMTP_USER", None) or "").strip()
    password = (getattr(settings, "SMTP_PASSWORD", None) or "").strip()
    from_email = (getattr(settings, "SMTP_FROM_EMAIL", None) or user or "").strip()
    port = int(getattr(settings, "SMTP_PORT", 587) or 587)

    if not host or not from_email:
        raise RuntimeError("SMTP is not configured")

    html_body, plain_body = render_code_email(code, purpose=purpose)
    from_header = f"Lunet <{from_email}>"

    msg = EmailMessage()
    msg["Subject"] = "Код подтверждения Lunet" if purpose == "bind" else "Код входа Lunet"
    msg["From"] = from_header
    msg["To"] = email
    msg.set_content(plain_body)
    msg.add_alternative(html_body, subtype="html")

    if port == 465:
        with smtplib.SMTP_SSL(host, port, timeout=15) as server:
            if user:
                server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port, timeout=15) as server:
            server.starttls()
            if user:
                server.login(user, password)
            server.send_message(msg)


@router.callback_query(F.data == "email_bind")
async def email_bind_start(callback: CallbackQuery, state: FSMContext, bot_api):
    try:
        await bot_api.get_user_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    text = (
        "<b><tg-emoji emoji-id='5967280668885913944'>✉️</tg-emoji> Привязка почты</b>\n\n"
        "Укадите email — он понадобится, если возникнут проблемы с Telegram или вашим аккаунтом.\n\n"
        "Отправьте адрес электронной почты, который хотите привязать/обновить к аккаунту."
    )
    await state.clear()
    await state.set_state(EmailBindStates.waiting_for_email)
    media = InputMediaPhoto(media=PROFILE_IMG, caption=text)
    await callback.message.edit_media(media=media, reply_markup=email_bind_kb())
    await callback.answer()


@router.message(EmailBindStates.waiting_for_email)
async def email_bind_enter_email(message: Message, state: FSMContext, bot_api):
    email = (message.text or "").strip().lower()
    if not EMAIL_RE.match(email):
        await message.answer("Введите корректный email адрес.")
        return

    code = f"{secrets.randbelow(1000000):06d}"
    try:
        _smtp_send_code(email, code)
    except Exception as e:
        logger.exception(
            "[bot][email_bind] smtp_send_failed tg_id=%s email=%s error=%s",
            message.from_user.id,
            email,
            e,
        )
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Непредвиденная ошибка при отправке кода. Попробуйте позже.")
        return

    _put_code(message.from_user.id, email, code)
    await state.update_data(pending_email=email)
    await state.set_state(EmailBindStates.waiting_for_code)
    await message.answer(
        "<tg-emoji emoji-id='5967280668885913944'>✉️</tg-emoji><b> Код подтверждения отправлен на почту.</b>\n"
        "Введите 6-значный код для подтверждения привязки.",
        reply_markup=email_bind_cancel_kb()
    )


@router.message(EmailBindStates.waiting_for_code)
async def email_bind_verify_code(message: Message, state: FSMContext, bot_api):
    raw_code = (message.text or "").strip()
    if not raw_code.isdigit() or len(raw_code) != 6:
        await message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Введите корректный 6-значный код.", 
            reply_markup=email_bind_cancel_kb()
            )
        return

    ok, email = _verify_code(message.from_user.id, raw_code)
    if not ok or not email:
        await message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Неверный или просроченный код. Запросите код заново через кнопку «Почта».",
            reply_markup=email_bind_cancel_kb()
            )
        return

    try:
        user = await bot_api.get_user_by_tg_id(message.from_user.id)
        user_data = user.get("user") if isinstance(user, dict) else user
        await bot_api.update_email(user_id=int(user_data["id"]), email=email)
    except ValueError:
        await message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Эта почта уже привязана к другому аккаунту.",
            reply_markup=email_bind_cancel_kb()
            )
        await state.clear()
        return
    except UserNotFound:
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота.")
        await state.clear()
        return

    await state.clear()
    text = f"<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji><b>Почта успешно привязана: <code>{html_escape(email)}</code></b>"
    await message.answer(text=text, reply_markup=email_bind_kb())
