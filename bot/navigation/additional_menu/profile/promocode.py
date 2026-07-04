from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InputMediaPhoto, Message

from backend.core.logger_config import logger
from backend.images import MAIN_MENU_IMG
from backend.services.exceptions import PromocodeAlreadyUsed, PromocodeExhausted, PromocodeNotFound, UserNotFound
from backend.states import PromocodeStates
from bot.navigation.additional_menu.profile.keyboards import promocode_kb


router = Router()


@router.callback_query(F.data == "activate_promocode")
async def enter_promocode_clb(callback: CallbackQuery, state: FSMContext):
    content = InputMediaPhoto(media=MAIN_MENU_IMG, caption="Введите промокод:")
    await callback.message.edit_media(media=content, reply_markup=promocode_kb())
    await state.set_state(PromocodeStates.waiting_for_code)
    await callback.answer()


@router.message(PromocodeStates.waiting_for_code)
async def process_promocode_clb(
    message: Message,
    state: FSMContext,
    bot_api,
):
    code = (message.text or "").strip()

    try:
        result = await bot_api.activate_promocode(tg_id=message.from_user.id, code=code)
        amount = int(result.get("amount_added") or 0)
    except UserNotFound:
        await message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        await state.clear()
        return
    except PromocodeNotFound:
        text = "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Промокод не найден."
    except PromocodeAlreadyUsed:
        text = "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Вы уже использовали этот промокод."
    except PromocodeExhausted:
        text = "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Лимит активаций этого промокода исчерпан."
    except Exception:
        logger.exception("Promocode activation failed")
        await message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Произошла ошибка при активации промокода. Попробуйте позже."
        )
        await state.clear()
        return
    else:
        text = (
            "<tg-emoji emoji-id='5825794181183836432'>✅</tg-emoji> <b>Промокод активирован!</b>\n\n"
            f"<tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Баланс пополнен на <b>{amount} RUB</b>."
        )

    await message.answer_photo(photo=MAIN_MENU_IMG, caption=text, reply_markup=promocode_kb())
    await state.clear()

