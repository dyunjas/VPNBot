from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from backend.images import MAIN_MENU_IMG
from backend.states import WithdrawBalance

from bot.navigation.additional_menu.referral.keyboards import (
    back_referral_kb,
    withdraw_confirm_kb,
    admin_withdraw_kb
)

from backend.services.referral_service import ReferralService
from backend.services.user_service import UserService
from backend.services.withdrawal_service import WithdrawalService
from backend.services.exceptions import NotEnoughReferralBalance, UserNotFound


router = Router()


MIN_WITHDRAW_AMOUNT = 500


@router.callback_query(F.data == "withdraw_balance")
async def withdraw_balance_start(callback: CallbackQuery, state: FSMContext, user_service: UserService, referral_service: ReferralService):

    try:
        user = await user_service.get_by_tg_id(callback.from_user.id)
    except UserNotFound:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    balance = await referral_service.get_balance(user.id)

    text = (
        "<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji>"
        f"Доступно для вывода: <b>{balance} RUB</b>\n"
        f"Введите сумму вывода (минимум {MIN_WITHDRAW_AMOUNT} RUB):"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )
    await callback.message.edit_media(media=media, reply_markup=back_referral_kb())
    await state.set_state(WithdrawBalance.waiting_for_amount)
    await callback.answer()


@router.message(WithdrawBalance.waiting_for_amount)
async def withdraw_balance_amount(
    message: Message,
    state: FSMContext,
    user_service: UserService,
    referral_service: ReferralService,
):
    try:
        amount = int((message.text or "").strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        text = (
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
            "Введите целое положительное число:"
        )
        await message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=back_referral_kb()
        )
        return

    if amount < MIN_WITHDRAW_AMOUNT:
        text = (
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
            f"Минимальная сумма вывода — <b>{MIN_WITHDRAW_AMOUNT} RUB</b>.\n"
            f"Введите сумму не меньше {MIN_WITHDRAW_AMOUNT}:"
        )
        await message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=back_referral_kb()
        )
        return

    user = await user_service.get_by_tg_id(message.from_user.id)
    balance = await referral_service.get_balance(user.id)

    if balance < amount:
        text = (
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
            "Недостаточно средств для вывода.\n\n"
            f"Доступно: <b>{balance} RUB</b>\n"
            "Введите сумму меньше или равную доступной:"
        )
        await message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=back_referral_kb()
        )
        return

    await state.update_data(amount=amount)

    text = "<tg-emoji emoji-id=\"5769403330761593044\">👛</tg-emoji> Введите метод вывода (например: карта/СБП/USDT(ТОЛЬКО TRC20) + реквизиты):"
    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        reply_markup=back_referral_kb()
    )
    await state.set_state(WithdrawBalance.waiting_for_method)


@router.message(WithdrawBalance.waiting_for_method)
async def withdraw_balance_method(message: Message, state: FSMContext):
    method = (message.text or "").strip()
    if len(method) < 8:
        text = (
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
            "<tg-emoji emoji-id=\"5769403330761593044\">👛</tg-emoji> Метод слишком короткий. Введите подробную информацию:"
        )
        await message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=back_referral_kb()
        )
        return

    await state.update_data(method=method)
    data = await state.get_data()

    text = (
        "<b>Подтвердите заявку на вывод:</b>\n\n"
        f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Сумма: <b>{data['amount']} RUB</b>\n"
        f"<tg-emoji emoji-id='5769403330761593044'>👛</tg-emoji> Метод: <b>{data['method']}</b>\n"
    )

    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        reply_markup=withdraw_confirm_kb()
    )
    await state.set_state(WithdrawBalance.waiting_for_confirmation)


@router.callback_query(F.data == "withdraw_cancel")
async def withdraw_balance_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "Заявка на вывод отменена."
    content = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)
    await callback.message.edit_media(media=content, reply_markup=back_referral_kb())
    await callback.answer()


@router.callback_query(WithdrawBalance.waiting_for_confirmation, F.data == "withdraw_confirm")
async def withdraw_balance_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    user_service: UserService,
    withdrawal_service: WithdrawalService,
):
    data = await state.get_data()
    amount: int = int(data["amount"])
    method: str = str(data["method"])

    user = await user_service.get_by_tg_id(callback.from_user.id)

    try:
        withdrawal = await withdrawal_service.create_withdrawal(
            user_id=user.id,
            amount=amount,
            method=method
        )
    except NotEnoughReferralBalance:
        await state.clear()
        text = (
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
            "Недостаточно средств для вывода (баланс мог измениться).\n"
            "Попробуйте ещё раз."
        )
        content = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text)
        await callback.message.edit_media(media=content, reply_markup=back_referral_kb())
        await callback.answer()
        return

    await state.clear()

    text_user = (
        "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Заявка на вывод создана и отправлена на рассмотрение.\n\n"
        f"ID заявки: <code>{withdrawal.id}</code>"
    )
    content = InputMediaPhoto(media=MAIN_MENU_IMG, caption=text_user)
    await callback.message.edit_media(media=content, reply_markup=back_referral_kb())
    await callback.answer()
