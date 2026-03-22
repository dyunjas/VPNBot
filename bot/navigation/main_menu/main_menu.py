# handlers/start.py
from aiogram import F, Router
from aiogram.filters import Command
from aiogram.filters.command import CommandObject
from aiogram.types import CallbackQuery, Message, InputMediaPhoto

from bot.navigation.main_menu.keyboards import main_menu_kb

from backend.services import UserService
from backend.services.referral_service import ReferralService
from backend.services.exceptions import UserNotFound

from backend.images import MAIN_MENU_IMG

router = Router()


@router.message(Command("start"))
async def start_cmd(
    message: Message,
    command: CommandObject,
    user_service: UserService,
    referral_service: ReferralService,
    is_new_user: bool = False,
):
    tg_id = message.from_user.id
    
    try:
        user = await user_service.get_by_tg_id(tg_id)
    except UserNotFound:
        await message.answer(
            "<tg-emoji emoji-id='5879813604068298387'>❗️</tg-emoji> Пользователь не найден. Попробуйте перезапустить бота."
        )
        return
    
    args = (command.args or "").strip()

    if args.startswith("ref_") and is_new_user and getattr(user, "referrer_id", None) is None:
        ref_str = args.split("_", 1)[1]

        if ref_str.isdigit():
            ref_tg_id = int(ref_str)

            if ref_tg_id != tg_id:
                try:
                    referrer = await user_service.get_by_tg_id(ref_tg_id)

                    linked = await referral_service.attach_referrer(
                        user_id=user.id,
                        referrer_id=referrer.id,
                    )

                    if linked:
                        referral_name = (
                            f"@{message.from_user.username}"
                            if message.from_user.username
                            else (message.from_user.full_name or str(tg_id))
                        )

                        await message.bot.send_message(
                            chat_id=referrer.tg_id,
                            text=(
                                "<tg-emoji emoji-id='5994502837327892086'>🎉</tg-emoji> У вас новый реферал!\n"
                                f"<tg-emoji emoji-id='5879770735999717115'>👤</tg-emoji> {referral_name}\n"
                                "<tg-emoji emoji-id='5875180111744995604'>🎁</tg-emoji> Начислено: 3 дня VPN"
                            )
                        )

                except UserNotFound:
                    pass

    if is_new_user:
        return

    text = (
        "<tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> Добро пожаловать в Lunet!\n\n"
        "<b>В нашем сервисе:</b>\n"
        "<tg-emoji emoji-id='5843553939672274145'>⚡️</tg-emoji> Нет ограничений по скорости, трафику и устройствам\n"
        "<tg-emoji emoji-id='6034962180875490251'>🔓</tg-emoji> Полная безопасность ваших данных\n"
        "<tg-emoji emoji-id='5879585266426973039'>🌐</tg-emoji> Совместимость со всеми платформами"
    )

    await message.answer_photo(
        photo=MAIN_MENU_IMG,
        caption=text,
        reply_markup=main_menu_kb(),
    )


@router.callback_query(F.data == "main_menu")
async def main_menu_clb(callback: CallbackQuery):
    text = (
        "<tg-emoji emoji-id='6005928962163742139'>🌝</tg-emoji> Добро пожаловать в Lunet!\n\n"
        "<b>В нашем сервисе:</b>\n"
        "<tg-emoji emoji-id='5843553939672274145'>⚡️</tg-emoji> Нет ограничений по скорости, трафику и устройствам\n"
        "<tg-emoji emoji-id='6034962180875490251'>🔓</tg-emoji> Полная безопасность ваших данных\n"
        "<tg-emoji emoji-id='5879585266426973039'>🌐</tg-emoji> Совместимость со всеми платформами"
    )

    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=main_menu_kb(),
    )
