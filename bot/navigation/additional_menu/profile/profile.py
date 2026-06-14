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
from backend.images import MAIN_MENU_IMG
from backend.services import UserService
from backend.services.exceptions import UserNotFound
from backend.states import EmailBindStates
from bot.navigation.additional_menu.profile.keyboards import profile_kb, email_bind_kb
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


def _smtp_send_code(email: str, code: str) -> None:
    host = (getattr(settings, "SMTP_HOST", None) or "").strip()
    user = (getattr(settings, "SMTP_USER", None) or "").strip()
    password = (getattr(settings, "SMTP_PASSWORD", None) or "").strip()
    from_email = (getattr(settings, "SMTP_FROM_EMAIL", None) or user or "").strip()
    port = int(getattr(settings, "SMTP_PORT", 587) or 587)

    if not host or not from_email:
        raise RuntimeError("SMTP is not configured")

    msg = EmailMessage()
    msg["Subject"] = "Код подтверждения Lunet"
    msg["From"] = from_email
    msg["To"] = email
    msg.set_content(f"Код подтверждения: {code}\nКод действует {OTP_TTL_SEC // 60} минут.")

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


async def _render_profile(callback: CallbackQuery, user_service: UserService) -> None:
    tg_id = callback.from_user.id
    user = await user_service.get_by_tg_id(tg_id)
    username = "-" if user.username is None else f"@{html_escape(user.username)}"
    email = user.email or "не привязана"

    text = (
        f"<b><tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> Пользователь №{user.id}:</b>\n"
        f"<b><tg-emoji emoji-id='5879770735999717115'>👤</tg-emoji> Юзернейм:</b> {username}\n"
        f"<b><tg-emoji emoji-id='5874948844935974490'>⭐️</tg-emoji> ID:</b> <code>{user.tg_id}</code>\n"
        f"<b><tg-emoji emoji-id='5879785854284599288'>✉️</tg-emoji> Почта:</b> {html_escape(email)}\n"
        f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Баланс:</b> {user.balance} RUB"
    )

    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)
    await callback.message.edit_media(media=media, reply_markup=profile_kb())


@router.callback_query(F.data == "profile")
async def profile_clb(callback: CallbackQuery, user_service: UserService):
    try:
        await _render_profile(callback, user_service)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return
    await callback.answer()


@router.callback_query(F.data == "profile_email_bind")
async def profile_email_bind_start(callback: CallbackQuery, state: FSMContext, user_service: UserService):
    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    current_email = html_escape(user.email or "-")
    text = (
        "<b><tg-emoji emoji-id='5967280668885913944'>✉️</tg-emoji> Привязка почты</b>\n"
        f"Текущая почта: <code>{current_email}</code>\n\n"
        "Если вы хотите изменить почту, введите новую почту. На нее будет отправлен код подтверждения."
    )
    await state.clear()
    await state.set_state(EmailBindStates.waiting_for_email)
    media = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)
    await callback.message.edit_media(media=media, reply_markup=email_bind_kb())
    await callback.answer()


@router.message(EmailBindStates.waiting_for_email)
async def profile_email_bind_enter_email(message: Message, state: FSMContext, user_service: UserService):
    email = (message.text or "").strip().lower()
    if not EMAIL_RE.match(email):
        await message.answer("Введите корректный email адрес.")
        return

    try:
        existing = await user_service.get_by_email(email)
        current = await user_service.get_by_tg_id(message.from_user.id)
        if existing.id != current.id:
            await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Эта почта уже привязана к другому аккаунту.")
            return
    except UserNotFound:
        pass

    code = f"{secrets.randbelow(1000000):06d}"
    try:
        _smtp_send_code(email, code)
    except Exception as e:
        logger.exception(
            "[bot][profile_email_bind] smtp_send_failed tg_id=%s email=%s error=%s",
            message.from_user.id,
            email,
            e,
        )
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Непредвиденная ошибка при отправке кода. Попробуйте позже.")
        return

    _put_code(message.from_user.id, email, code)
    await state.update_data(pending_email=email)
    await state.set_state(EmailBindStates.waiting_for_code)
    await message.answer(
        "<tg-emoji emoji-id='5967280668885913944'>✉️</tg-emoji><b>Код отправлен на почту.</b>\n"
        "Введите 6-значный код для подтверждения привязки."
    )


@router.message(EmailBindStates.waiting_for_code)
async def profile_email_bind_verify_code(message: Message, state: FSMContext, user_service: UserService):
    raw_code = (message.text or "").strip()
    if not raw_code.isdigit() or len(raw_code) != 6:
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Введите корректный 6-значный код.")
        return

    ok, email = _verify_code(message.from_user.id, raw_code)
    if not ok or not email:
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Неверный или просроченный код. Запросите код заново через кнопку «Почта» в профиле.")
        return

    try:
        user = await user_service.get_by_tg_id(message.from_user.id)
        await user_service.set_email(user.id, email)
    except ValueError:
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji>Эта почта уже привязана к другому аккаунту.")
        await state.clear()
        return
    except UserNotFound:
        await message.answer("<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота.")
        await state.clear()
        return

    await state.clear()
    text = f"<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji><b>Почта успешно привязана: <code>{html_escape(email)}</code></b>"
    await message.answer(text=text, reply_markup=email_bind_kb())
