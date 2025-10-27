from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InputMediaPhoto

from aiogram.fsm.context import FSMContext

from server.states import PromocodeStates

from server.images import MAIN_MENU_IMG, MAIN_MENU_IMG

from client.navigation.additional_menu.profile.keyboards import promocode_kb

from server.repositories.promocode_repository import PromocodeRepository
from server.repositories.user_repository import UserRepository

router = Router()

@router.callback_query(F.data == "activate_promocode")
async def enter_promocode_clb(callback: CallbackQuery, state: FSMContext):
    text = "Введите промокод:"
    
    content = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text
    )

    await callback.message.edit_media(
        media=content,
        reply_markup=promocode_kb()
    )
    await state.set_state(PromocodeStates.waiting_for_code)
    await callback.answer()

@router.message(PromocodeStates.waiting_for_code)
async def process_promocode_clb(message: Message, state: FSMContext, user_repo: UserRepository, promocode_repo: PromocodeRepository):
    
    tg_id = message.from_user.id

    code = message.text.strip()

    promocode = await promocode_repo.activate_promocode(code=code, user_id=tg_id)

    if promocode is None:
        text = "❗️ Промокод недействителен или уже использован"
        await message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=promocode_kb()
        )
    else:
        try:
            await user_repo.increase_balance(tg_id, promocode.amount)
        except:
            await message.answer(text="Ошибка обновления баланса, обратитесь в поддержку")
            return
        text = (
            f"✅ Промокод активирован!\n"
            f"<b>🌟 Баланс пополнен на:</b> {promocode.amount} RUB."
        )
        await message.answer_photo(
            photo=MAIN_MENU_IMG,
            caption=text,
            reply_markup=promocode_kb()
        )
    await state.clear()