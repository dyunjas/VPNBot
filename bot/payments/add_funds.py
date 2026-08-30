from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from backend.images import PROFILE_IMG
from backend.states import PaymentStates
from bot.payments import messages as payment_messages
from bot.payments.keyboards import back_profile_kb, payment_choice_kb

router = Router()


@router.callback_query(F.data == "add_funds")
async def topup_balance_clb(callback: CallbackQuery, state: FSMContext):
    content = InputMediaPhoto(
        media=PROFILE_IMG,
        caption=payment_messages.AMOUNT_PROMPT,
    )
    await callback.message.edit_media(
        media=content,
        reply_markup=back_profile_kb(),
    )
    await state.set_state(PaymentStates.waiting_for_amount)
    await callback.answer()


@router.message(PaymentStates.waiting_for_amount)
async def choose_payment_system_clb(message: Message, state: FSMContext):
    try:
        amount = int((message.text or "").strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer_photo(
            photo=PROFILE_IMG,
            caption=payment_messages.AMOUNT_INVALID,
            reply_markup=back_profile_kb(),
        )
        return

    await state.update_data(amount=amount)
    await message.answer_photo(
        photo=PROFILE_IMG,
        caption=payment_messages.PAYMENT_METHOD_PROMPT,
        reply_markup=await payment_choice_kb(),
    )
    await state.set_state(PaymentStates.waiting_for_payment_system)
