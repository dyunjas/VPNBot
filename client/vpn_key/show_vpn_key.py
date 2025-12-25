from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery, InputMediaPhoto

from server.repositories.key_repository import KeyRepository
from server.repositories.user_repository import UserRepository

from client.vpn_key.keyboards import user_keys_kb, key_info_kb

from server.images import MAIN_MENU_IMG


router = Router()

@router.callback_query(F.data == "my_keys")
async def show_user_keys(
    callback: CallbackQuery, 
    key_repo: KeyRepository,
    user_repo: UserRepository
    ):
    tg_id = callback.from_user.id
    user = await user_repo.get_user_by_tg_id(tg_id)
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
    await callback.answer()


@router.callback_query(F.data.startswith("key_info:"))
async def show_key_info(callback: CallbackQuery, key_repo: KeyRepository):
    key_id = int(callback.data.split(":")[1])

    key = await key_repo.get_key_by_id(key_id)

    if not key:
        await callback.answer("Ключ не найден", show_alert=True)
        return

    server = key.server
    text = (
        f"<b>📑 ID ключа:</b> <code>{key.uuid}</code>\n"
        f"<b>🌎 Сервер:</b> {server.country if server else '❓'}\n"
        f"<b>🕓 Создан:</b> {key.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"<b>📅 Истекает:</b> {key.expires_at.strftime('%d.%m.%Y %H:%M') if key.expires_at else '∞'}\n"
        f"<b>🔑 Ключ:</b> <code>{key.uri}</code>\n\n"
        f'<a href="https://telegra.ph/Lunet-VPN---instrukciya-12-18"><b>📝 Инструкция по подключению(нажмите, чтобы перейти)</b></a>'
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=key_info_kb(key, key.uri)
    )
    await callback.answer()
