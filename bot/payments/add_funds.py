from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto
from aiogram.fsm.context import FSMContext

from backend.images import MAIN_MENU_IMG

from bot.payments.keyboards import back_profile_kb, payment_choice_kb

from backend.states import PaymentStates


router = Router()

@router.callback_query(F.data == "add_funds")
async def topup_balance_clb(callback: CallbackQuery, state: FSMContext):

    text = "Введите сумму пополнения (RUB):"
    content = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )
    await callback.message.edit_media(
        media=content,
        reply_markup=back_profile_kb()
    )
    await state.set_state(PaymentStates.waiting_for_amount)
    await callback.answer()

@router.message(PaymentStates.waiting_for_amount)
async def choose_payment_system_clb(message: Message, state: FSMContext):
    try:
        amount = int(message.text)

        if amount <= 0:
            raise ValueError

    except ValueError:
        text = "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Введите целое положительное число (больше 0)"
        await message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=back_profile_kb()
        )
        return

    await state.update_data(amount=amount)
    text = "Выберите платёжную систему:"
    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        reply_markup=payment_choice_kb()
    )
    await state.set_state(PaymentStates.waiting_for_payment_system)