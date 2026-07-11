from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from backend.images import PROFILE_IMG
from backend.states import WithdrawBalance

from bot.navigation.additional_menu.referral.keyboards import (
    back_referral_kb,
    withdraw_confirm_kb,
)

router = Router()


MIN_WITHDRAW_AMOUNT = 500


@router.callback_query(F.data == "withdraw_balance")
async def withdraw_balance_start(callback: CallbackQuery, state: FSMContext, bot_api):
    try:
        info = await bot_api.get_referral_info(tg_id=callback.from_user.id)
        referral = info.get("referral") if isinstance(info, dict) else {}
    except Exception:
        await callback.message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return

    balance = referral.get("balance", 0)

    text = (
        "<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji>"
        f"Доступно для вывода: <b>{balance} RUB</b>\n"
        f"Введите сумму вывода (минимум {MIN_WITHDRAW_AMOUNT} RUB):"
    )
    media = InputMediaPhoto(
        media=PROFILE_IMG,
        caption=text
    )
    await callback.message.edit_media(media=media, reply_markup=back_referral_kb())
    await state.set_state(WithdrawBalance.waiting_for_amount)
    await callback.answer()


@router.message(WithdrawBalance.waiting_for_amount)
async def withdraw_balance_amount(message: Message, state: FSMContext, bot_api):
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
            photo=PROFILE_IMG,
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
            photo=PROFILE_IMG,
            caption=text,
            reply_markup=back_referral_kb()
        )
        return

    info = await bot_api.get_referral_info(tg_id=message.from_user.id)
    referral = info.get("referral") if isinstance(info, dict) else {}
    balance = referral.get("balance", 0)

    if balance < amount:
        text = (
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
            "Недостаточно средств для вывода.\n\n"
            f"Доступно: <b>{balance} RUB</b>\n"
            "Введите сумму меньше или равную доступной:"
        )
        await message.answer_photo(
            photo=PROFILE_IMG,
            caption=text,
            reply_markup=back_referral_kb()
        )
        return

    await state.update_data(amount=amount)

    text = "<tg-emoji emoji-id=\"5769403330761593044\">👝</tg-emoji> Введите метод вывода (например: карта/СБП/USDT(ТОЛЬКО TRC20) + реквизиты):"
    await message.answer_photo(
        photo=PROFILE_IMG,
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
            "<tg-emoji emoji-id=\"5769403330761593044\">👝</tg-emoji> Метод слишком короткий. Введите подробную информацию:"
        )
        await message.answer_photo(
            photo=PROFILE_IMG,
            caption=text,
            reply_markup=back_referral_kb()
        )
        return

    await state.update_data(method=method)
    data = await state.get_data()

    text = (
        "<b>Подтвердите заявку на вывод:</b>\n\n"
        f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Сумма: <b>{data['amount']} RUB</b>\n"
        f"<tg-emoji emoji-id='5769403330761593044'>👝</tg-emoji> Метод: <b>{data['method']}</b>\n"
    )

    await message.answer_photo(
        photo=PROFILE_IMG,
        caption=text,
        reply_markup=withdraw_confirm_kb()
    )
    await state.set_state(WithdrawBalance.waiting_for_confirmation)


@router.callback_query(F.data == "withdraw_cancel")
async def withdraw_balance_cancel(callback: CallbackQuery, state: FSMContext):
    await state.clear()
    text = "Заявка на вывод отменена."
    content = InputMediaPhoto(media=PROFILE_IMG, caption=text)
    await callback.message.edit_media(media=content, reply_markup=back_referral_kb())
    await callback.answer()


@router.callback_query(WithdrawBalance.waiting_for_confirmation, F.data == "withdraw_confirm")
async def withdraw_balance_confirm(
    callback: CallbackQuery,
    state: FSMContext,
    bot_api,
):
    data = await state.get_data()
    amount: int = int(data["amount"])
    method: str = str(data["method"])

    try:
        withdrawal = await bot_api.create_withdrawal(
            tg_id=callback.from_user.id,
            amount=amount,
            method=method,
        )
    except Exception:
        await state.clear()
        text = (
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> "
            "Недостаточно средств для вывода (баланс мог измениться).\n"
            "Попробуйте ещё раз."
        )
        content = InputMediaPhoto(media=PROFILE_IMG, caption=text)
        await callback.message.edit_media(media=content, reply_markup=back_referral_kb())
        await callback.answer()
        return

    await state.clear()

    text_user = (
        "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Заявка на вывод создана и отправлена на рассмотрение.\n\n"
        f"ID заявки: <code>{withdrawal.get('withdrawal', {}).get('id')}</code>"
    )
    content = InputMediaPhoto(media=PROFILE_IMG, caption=text_user)
    await callback.message.edit_media(media=content, reply_markup=back_referral_kb())
    await callback.answer()

