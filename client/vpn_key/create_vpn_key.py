from aiogram import Router, F
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import CallbackQuery, InputMediaPhoto

from server.repositories.subscription_repository import SubscriptionRepository
from server.repositories.server_repository import ServerRepository
from server.repositories.key_repository import KeyRepository
from server.repositories.user_repository import UserRepository

from server.database.models import KeyStatus
from client.vpn_key.keyboards import servers_kb, key_info_kb

from server.core.loader import settings

from server.images import MAIN_MENU_IMG

router = Router()
XRAY_AUTH_TOKEN = settings.XRAY_AUTH


@router.callback_query(F.data == "create_key")
async def show_servers_clb(
    callback: CallbackQuery,
    subscription_repo: SubscriptionRepository,
    server_repo: ServerRepository,
):
    tg_id = callback.from_user.id

    subscription = await subscription_repo.get_active_subscription_with_plan_by_tg(tg_id)
    if not subscription:
        await callback.answer(
            text="⚠️ У вас нет активной подписки.\nОформите подписку, чтобы создавать ключи.",
            show_alert=True
        )
        await callback.answer()
        return

    servers = await server_repo.get_all_servers()

    text = "🌍 Выберите сервер:"
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )
    await callback.message.edit_media(
        media=media, 
        reply_markup=servers_kb(servers=servers, page=0))
    await callback.answer()


@router.callback_query(F.data.startswith("servers_page:"))
async def switch_servers_page(
    callback: CallbackQuery,
    server_repo: ServerRepository,
):
    page = int(callback.data.split(":")[1])

    servers = await server_repo.get_all_servers()
    keyboard = servers_kb(servers=servers, page=page)

    await callback.message.edit_reply_markup(reply_markup=keyboard)
    await callback.answer()


@router.callback_query(F.data.startswith("server:"))
async def confirm_server(callback: CallbackQuery, server_repo: ServerRepository):
    _, server_id, _page = callback.data.split(":")
    server_id = int(server_id)
    server = await server_repo.get_server_by_id(server_id)

    keyboard = InlineKeyboardBuilder()
    keyboard.button(text="✅ Создать ключ", callback_data=f"confirm_key:{server_id}")
    keyboard.button(text="⬅️ Назад", callback_data="create_key")
    keyboard.adjust(1)

    text = (
        f"<b>🌎 Сервер:</b> {server.country}\n"
        f"<b>🌐 Хост:</b> {server.public_host}\n"
        f"<b>🕓 Создан:</b> {server.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
        f"{server.note}"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )
    await callback.message.edit_media(
        media=media,
        reply_markup=keyboard.as_markup(),
    )
    await callback.answer()


@router.callback_query(F.data.startswith("confirm_key:"))
async def create_key_clb(
    callback: CallbackQuery,
    subscription_repo: SubscriptionRepository,
    server_repo: ServerRepository,
    key_repo: KeyRepository,
    user_repo: UserRepository,
):
    tg_id = callback.from_user.id
    server_id = int(callback.data.split(":")[1])

    subscription = await subscription_repo.get_active_subscription_with_plan_by_tg(tg_id)
    if not subscription:
        await callback.message.answer(
            "⚠️ У вас нет активной подписки.\nОформите подписку, чтобы создавать ключи."
        )
        await callback.answer()
        return

    plan = subscription.plan

    user = await user_repo.get_user_by_tg_id(tg_id)
    if not user:
        await callback.answer("Пользователь не найден.", show_alert=True)
        return

    user_keys = await key_repo.get_keys_by_user_id(user.id)
    active_keys_cnt = sum(1 for k in user_keys if k.status == KeyStatus.active)
    if active_keys_cnt >= plan.key_limit:
        await callback.answer(
            f"⚠️ Лимит ключей исчерпан ({active_keys_cnt}/{plan.key_limit}). "
            "Удалите один из ключей, чтобы создать новый.",
            show_alert=True
        )
        await callback.answer()
        return

    server = await server_repo.get_server_by_id(server_id)
    if not server:
        await callback.answer(
            text="❗️ Сервер не найден",
            show_alert=True
        )
        await callback.answer()
        return

    try:
        key = await key_repo.create_key(
            user_id=user.id,
            server=server,
            auth_token=XRAY_AUTH_TOKEN,
        )
    except Exception as e:
        await callback.answer(
            text=f"❗️ Ошибка при создании ключа: {e}",
            show_alert=True
        )
        await callback.answer()
        return
    
    text = (
        f"<b>📑 ID ключа:</b> <code>{key.uuid}</code>\n"
        f"<b>🌎 Сервер:</b> {server.country if server else '❓'}\n"
        f"<b>🕓 Создан:</b> {key.created_at.strftime('%d.%m.%Y %H:%M')}\n"
        f"<b>📅 Истекает:</b> {key.expires_at.strftime('%d.%m.%Y %H:%M') if key.expires_at else '∞'}\n\n"
        f"<b>🔑 Ключ:</b> <code>{key.uri}</code>"
    )
    media = InputMediaPhoto(
        media=MAIN_MENU_IMG,
        caption=text,
        parse_mode="HTML"
    )

    await callback.message.edit_media(
        media=media,
        reply_markup=key_info_kb(key)
    )
    await callback.answer(
        text="✅ Ключ создан",
        show_alert=True
    )


@router.callback_query(F.data == "cancel_key")
async def cancel_key(callback: CallbackQuery):
    await callback.message.edit_caption("❗️ Создание ключа отменено.")
    await callback.answer()
