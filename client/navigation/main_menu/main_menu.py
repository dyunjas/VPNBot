from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import CallbackQuery, Message, InputMediaPhoto

from client.navigation.main_menu.keyboards import main_menu_kb

from server.repositories.user_repository import UserRepository
from server.images import MAIN_MENU_IMG
from server.core.loader import bot

router = Router()

@router.message(Command("start"))
async def start_cmd(message: Message, command: CommandObject, user_repo: UserRepository):
    args = (command.args or "").strip()
    tg_id = message.from_user.id

    user = await user_repo.get_user_by_tg_id(tg_id)

    is_new_user = False
    if not user:
        user = await user_repo.create_user(
            tg_id=tg_id,
            username=message.from_user.username,
            full_name=message.from_user.full_name,
        )
        is_new_user = True

    if is_new_user and args.startswith("ref_"):
        ref_tg_id_str = args.split("_", 1)[1]
        if ref_tg_id_str.isdigit():
            ref_tg_id = int(ref_tg_id_str)

            if ref_tg_id != tg_id:
                referrer = await user_repo.get_user_by_tg_id(ref_tg_id)
                if referrer:
                    linked = await user_repo.set_referrer_if_empty(
                        user_id=user.id,
                        referrer_id=referrer.id
                    )
                    if linked:
                        await user_repo.increase_balance(referrer.tg_id, 10)
                        await user_repo.increase_balance(message.from_user.id, 10)

                        referral_name = (
                            f"@{message.from_user.username}"
                            if message.from_user.username
                            else (message.from_user.full_name or str(tg_id))
                        )
                        await message.bot.send_message(
                            chat_id=referrer.tg_id,
                            text=f"🎉 У вас новый реферал: {referral_name}\n🌟 Начислено: 10 RUB"
                        )

    text = (
        "🌙 Добро пожаловать в Lunet!\n\n"
        "<b>В нашем сервисе:</b>\n"
        "⚡️Нет ограничесний по скорости, трафику и количеству устройств\n"
        "🔒Полная безопасность ваших данных\n"
        "🌐Полная совместимость со всеми платформами и устройствами"
    )
    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        reply_markup=main_menu_kb()
    )

@router.callback_query(F.data == "main_menu")
async def main_menu_clb(callback: CallbackQuery):
    text = text = (
        "🌙 Добро пожаловать в Lunet!\n\n"
        "<b>В нашем сервисе:</b>\n"
        "⚡️Нет ограничесний по скорости, трафику и количеству устройств\n"
        "🔒Полная безопасность ваших данных\n"
        "🌐Полная совместимость со всеми платформами и устройствами"
    )
    media = InputMediaPhoto(
    caption=text,
    media=MAIN_MENU_IMG
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=main_menu_kb()
    )