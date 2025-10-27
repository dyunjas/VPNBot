from aiogram import Router, F
from aiogram.types import CallbackQuery, InputMediaPhoto
from aiogram.utils.keyboard import InlineKeyboardBuilder

from server.repositories.key_repository import KeyRepository
from server.repositories.user_repository import UserRepository

from client.vpn_key.keyboards import user_keys_kb, delete_key_kb

from server.images import MAIN_MENU_IMG

from server.core.loader import settings

XRAY_AUTH_TOKEN = settings.XRAY_AUTH

router = Router()


@router.callback_query(F.data.startswith("delete_key:"))
async def confirm_delete_key(callback: CallbackQuery):
    key_id = int(callback.data.split(":")[1])

    text = "❗️ Вы уверены, что хотите удалить этот ключ?"
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=delete_key_kb(key_id)
    )
    await callback.answer()

@router.callback_query(F.data.startswith("confirm_delete:"))
async def perform_delete_key(
    callback: CallbackQuery,
    key_repo: KeyRepository,
    user_repo: UserRepository
):
    key_id = int(callback.data.split(":")[1])
    tg_id = callback.from_user.id
    user = await user_repo.get_user_by_tg_id(tg_id)

    try:
        success = await key_repo.delete_key(key_id, auth_token=XRAY_AUTH_TOKEN)
        if not success:
            await callback.answer("Ключ не найден или уже удалён", show_alert=True)
            return
    except Exception as e:
        await callback.answer(f"Ошибка при удалении на сервере: {e}", show_alert=True)
        return

    keys = await key_repo.get_keys_by_user_id(user.id)

    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption="🌙 Ваши ключи:",
        parse_mode="HTML"
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=user_keys_kb(keys)
    )
    await callback.answer("✅ Ключ удалён", show_alert=True)
