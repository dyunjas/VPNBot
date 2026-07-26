import random

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

from backend.images import MAIN_MENU_IMG
from backend.services.exceptions import UserNotFound, BannedUser
from backend.states import CaptchaStates
from bot.navigation.main_menu.keyboards import main_menu_kb
from bot.utils.html import html_escape

router = Router()

CAPTCHA_ANIMALS = [
    ("cat", "🐱 Кошка"),
    ("dog", "🐶 Собака"),
    ("rabbit", "🐰 Кролик"),
    ("fox", "🦊 Лиса"),
    ("bear", "🐻 Медведь"),
    ("frog", "🐸 Лягушка"),
]


def build_profile_text(user: dict) -> str:
    username = "-" if not user.get("username") else f"@{html_escape(user.get('username'))}"
    email = user.get("email") or "не привязана"

    return (
        f"<b><tg-emoji emoji-id='5920344347152224466'>👤</tg-emoji> Профиль:</b> {username}\n\n"
        f"<blockquote><b>——<tg-emoji emoji-id='5936017305585586269'>🪪</tg-emoji> ID:</b> <code>{user.get('tg_id')}</code>\n"
        f"<b>——<tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Баланс:</b> {user.get('balance')} RUB\n"
        f"<b>——<tg-emoji emoji-id='5967280668885913944'>✉️</tg-emoji> Почта:</b> {html_escape(email)}</blockquote>\n\n"
        "<tg-emoji emoji-id='5771695636411847302'>📢</tg-emoji> Канал: @LunetVpn\n"
        "<tg-emoji emoji-id='5906995262378741881'>🙋</tg-emoji> Поддержка: @LunetVpnSupport\n\n"
        "<blockquote><i><tg-emoji emoji-id='5874960879434338403'>🔎</tg-emoji> Нажмите кнопку 'Купить подписку', чтобы приобрести подписку.</i></blockquote>"
    )


def _build_captcha_markup(options: list[tuple[str, str]]):
    builder = InlineKeyboardBuilder()
    for code, label in options:
        builder.button(text=label, callback_data=f"captcha:{code}", style="primary")
    builder.adjust(2, 2)
    return builder.as_markup()


def _build_captcha_caption(target_label: str, attempts_left: int) -> str:
    return (
        f"<tg-emoji emoji-id='5931415565955503486'>🤖</tg-emoji> Пожалуйста, выбрите <b>{html_escape(target_label)}</b> из списка ниже, чтобы подтвердить, что вы не робот."
    )


async def _send_captcha(
    message: Message,
    state: FSMContext,
    *,
    attempts_left: int = 3,
    extra_data: dict | None = None,
) -> None:
    target_code, target_label = random.choice(CAPTCHA_ANIMALS)
    distractors = random.sample([item for item in CAPTCHA_ANIMALS if item[0] != target_code], k=3)
    options = distractors + [(target_code, target_label)]
    random.shuffle(options)

    await state.set_state(CaptchaStates.waiting_for_answer)
    payload = {
        "captcha_target": target_code,
        "captcha_options": [code for code, _ in options],
        "captcha_attempts": attempts_left,
    }
    if extra_data:
        payload.update(extra_data)
    await state.update_data(**payload)

    await message.answer(
        text=_build_captcha_caption(target_label, attempts_left),
        reply_markup=_build_captcha_markup(options),
    )


async def _edit_captcha(
    callback: CallbackQuery,
    state: FSMContext,
    *,
    target_label: str,
    options: list[tuple[str, str]],
    attempts_left: int,
) -> None:
    await state.update_data(
        captcha_target=next(code for code, label in CAPTCHA_ANIMALS if label == target_label),
        captcha_options=[code for code, _ in options],
        captcha_attempts=attempts_left,
    )
    if callback.message:
        await callback.message.edit_text(
            text=_build_captcha_caption(target_label, attempts_left),
            reply_markup=_build_captcha_markup(options),
        )


async def _render_welcome(
    message_or_callback: Message | CallbackQuery,
    *,
    user: dict | None = None,
    bot_api=None,
) -> None:
    if user is None:
        resp = await bot_api.get_user_by_tg_id(message_or_callback.from_user.id)
        user = resp.get("user") if isinstance(resp, dict) else resp

    text = build_profile_text(user)

    if isinstance(message_or_callback, Message):
        await message_or_callback.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=main_menu_kb(),
        )
        return

    if message_or_callback.message:
        await message_or_callback.message.edit_media(
            media=InputMediaPhoto(media=MAIN_MENU_IMG, caption=text),
            reply_markup=main_menu_kb(),
        )
    else:
        await message_or_callback.bot.send_photo(
            chat_id=message_or_callback.from_user.id,
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=main_menu_kb(),
        )


async def _grant_trial_and_notify(*, message: Message | None, bot, tg_id: int, trial_granted: bool) -> None:
    if not trial_granted:
        return

    text = (
        "<tg-emoji emoji-id='5963213811597970978'>🎁</tg-emoji> <b>Вам выдан тестовый период.</b>\n\n"
        "Перейдите в меню «Моя подписка», чтобы посмотреть детали."
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="Моя подписка", callback_data="vpn_subscription", icon_custom_emoji_id="6005570495603282482", style="primary")
    if message:
        await message.answer(text, reply_markup=builder.as_markup())
        return

    await bot.send_message(chat_id=tg_id, text=text, reply_markup=builder.as_markup())


async def _process_post_registration_links(
    *,
    args: str,
    user_id: int,
    tg_id: int,
    username: str | None,
    bot,
    full_name: str,
    bot_api,
) -> None:
    if args.startswith("partner_"):
        partner_code = args.split("_", 1)[1].strip()
        if partner_code:
            try:
                await bot_api.attach_partner(user_id=user_id, code=partner_code)
            except ValueError:
                pass

    if args.startswith("ref_"):
        ref_str = args.split("_", 1)[1].strip()
        if not ref_str.isdigit():
            return

        ref_tg_id = int(ref_str)
        if ref_tg_id == tg_id:
            return

        try:
            referrer = await bot_api.get_user_by_tg_id(ref_tg_id)
        except UserNotFound:
            return

        try:
            result = await bot_api.attach_referrer(user_id=user_id, referrer_tg_id=ref_tg_id)
        except BannedUser:
            return
        if not result.get("linked"):
            return

        referral_name = (
            f"@{html_escape(username)}"
            if username
            else html_escape(full_name or str(tg_id))
        )

        builder = InlineKeyboardBuilder()
        builder.button(text="Баланс", callback_data="balance_menu", icon_custom_emoji_id="5769403330761593044", style="success")

        await bot.send_message(
            chat_id=referrer.get("user", referrer).get("tg_id"),
            text=(
                "<b><tg-emoji emoji-id='5994502837327892086'>🎉</tg-emoji> Новый реферал!</b>\n\n"
                "По вашей ссылке зарегистрировался пользователь:\n\n"
                f"<blockquote><tg-emoji emoji-id='5920344347152224466'>👤</tg-emoji> {referral_name}</blockquote>\n\n"
                "<tg-emoji emoji-id='5963213811597970978'>🎁</tg-emoji> Вам начислен бонус — 1 день VPN."
            ),
            reply_markup=builder.as_markup()
        )


@router.message(F.text.startswith("/start"))
async def start_cmd(
    message: Message,
    bot_api,
    state: FSMContext,
):
    tg_id = message.from_user.id
    raw_text = (message.text or "").strip()
    parts = raw_text.split(maxsplit=1)
    args = parts[1].strip() if len(parts) > 1 else ""

    try:
        user = await bot_api.get_user_by_tg_id(tg_id)
    except UserNotFound:
        await state.clear()
        await _send_captcha(
            message,
            state,
            extra_data={
                "pending_args": args,
                "pending_username": message.from_user.username,
            },
        )
        return

    await state.clear()
    user_data = user.get("user") if isinstance(user, dict) else user
    await _render_welcome(message, user=user_data)


@router.callback_query(F.data.startswith("captcha:"))
async def captcha_answer(
    callback: CallbackQuery,
    state: FSMContext,
    bot_api,
):
    data = await state.get_data()
    target_code = str(data.get("captcha_target") or "")
    options = [str(item) for item in data.get("captcha_options") or []]
    attempts_left = int(data.get("captcha_attempts") or 3)
    clicked_code = (callback.data or "").split(":", 1)[1].strip()

    if not target_code or clicked_code not in options:
        await callback.answer("Капча устарела. Отправьте /start ещё раз.", show_alert=True)
        await state.clear()
        return

    selected_label = next((label for code, label in CAPTCHA_ANIMALS if code == clicked_code), None)
    target_label = next((label for code, label in CAPTCHA_ANIMALS if code == target_code), None)
    if not selected_label or not target_label:
        await callback.answer("Капча устарела. Отправьте /start ещё раз.", show_alert=True)
        await state.clear()
        return

    if clicked_code != target_code:
        attempts_left -= 1
        if attempts_left <= 0:
            await callback.answer("Попытки закончились. Начните сначала через /start.", show_alert=True)
            if callback.message:
                await callback.message.edit_text(
                    text=(
                        "<b><tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Проверка не пройдена</b>\n\n"
                        "Вы исчерпали 3 попытки. Начните сначала через /start."
                    ),
                    reply_markup=None,
                )
            await state.clear()
            return

        await callback.answer(
            f"Неверно. Осталось попыток: {attempts_left}",
            show_alert=True,
        )

        shuffled_options = [(code, label) for code, label in CAPTCHA_ANIMALS if code in options]
        random.shuffle(shuffled_options)
        await _edit_captcha(
            callback,
            state,
            target_label=target_label,
            options=shuffled_options,
            attempts_left=attempts_left,
        )
        return

    await callback.answer("Проверка пройдена", show_alert=False)

    tg_id = callback.from_user.id
    username = callback.from_user.username
    created = await bot_api.ensure_user(tg_id=tg_id, username=username)
    user = created.get("user") or {}
    await _grant_trial_and_notify(
        message=callback.message,
        bot=callback.bot,
        tg_id=tg_id,
        trial_granted=bool(created.get("trial_granted")),
    )

    await _process_post_registration_links(
        args=str(data.get("pending_args") or ""),
        user_id=int(user.get("id")),
        tg_id=tg_id,
        username=username,
        bot=callback.bot,
        full_name=callback.from_user.full_name or "",
        bot_api=bot_api,
    )

    await state.clear()

    if callback.message:
        await callback.message.delete()
        await callback.message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=build_profile_text(user),
            reply_markup=main_menu_kb(),
        )
    else:
        await callback.bot.send_photo(
            chat_id=tg_id,
            photo=MAIN_MENU_IMG,
            caption=build_profile_text(user),
            reply_markup=main_menu_kb(),
        )

    await state.clear()


@router.callback_query(F.data == "main_menu")
async def main_menu_clb(callback: CallbackQuery, bot_api, state: FSMContext):
    try:
        await _render_welcome(callback, bot_api=bot_api)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return
    await callback.answer()
    await state.clear()


@router.callback_query(F.data == "profile")
async def profile_clb(callback: CallbackQuery, bot_api):
    try:
        await _render_welcome(callback, bot_api=bot_api)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return
    await callback.answer()

