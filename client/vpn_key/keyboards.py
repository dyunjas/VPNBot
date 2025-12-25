from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.types import InlineKeyboardButton

SERVERS_PER_PAGE = 10

def _fmt_country(country_enum) -> str:
    try:
        txt = str(country_enum.value if hasattr(country_enum, "value") else country_enum)
    except Exception:
        txt = str(country_enum)
    return txt.replace("_", " ")

def servers_kb(servers, page: int = 0):
    builder = InlineKeyboardBuilder()

    start = page * SERVERS_PER_PAGE
    end = start + SERVERS_PER_PAGE
    chunk = servers[start:end]

    for server in chunk:
        title = f"{_fmt_country(server.country)}"
        builder.button(text=f"{title}", callback_data=f"server:{server.id}:{page}")
    builder.adjust(2)

    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton(text="⬅️ Назад", callback_data=f"servers_page:{page-1}"))
    if end < len(servers):
        nav_buttons.append(InlineKeyboardButton(text="➡️ Вперёд", callback_data=f"servers_page:{page+1}"))

    if nav_buttons:
        builder.row(*nav_buttons)

    builder.row(InlineKeyboardButton(text="⬅️ К ключам", callback_data="my_keys"))
    builder.row(InlineKeyboardButton(text="🪐 В главное меню", callback_data="main_menu"))

    return builder.as_markup()

def user_keys_kb(keys):
    builder = InlineKeyboardBuilder()
    builder.row(InlineKeyboardButton(text="🔄 Единая VPN ссылка", callback_data="subscription_url"))

    if not keys:
        builder.row(InlineKeyboardButton(text="➕ Создать ключ", callback_data="create_key"))
        builder.row(InlineKeyboardButton(text="🪐 В главное меню", callback_data="main_menu"))
        return builder.as_markup()

    keys_builder= InlineKeyboardBuilder()
    for key in keys:
        country = _fmt_country(key.server.country if key.server else "❓")
        keys_builder.button(text=country, callback_data=f"key_info:{key.id}")
    keys_builder.adjust(2)

    builder.attach(keys_builder)
    builder.row(InlineKeyboardButton(text="➕ Новый ключ", callback_data="create_key"))
    builder.row(InlineKeyboardButton(text="🪐 В главное меню", callback_data="main_menu"))
    return builder.as_markup()

def key_info_kb(key, key_uri):
    builder = InlineKeyboardBuilder()

    builder.button(text="🗑 Удалить ключ", callback_data=f"delete_key:{key.id}")
    builder.button(text="⬅️ Назад", callback_data="my_keys")
    builder.adjust(1)
    return builder.as_markup()

def delete_key_kb(key_id):
    builder = InlineKeyboardBuilder()

    builder.button(text="✅ Подтвердить", callback_data=f"confirm_delete:{key_id}")
    builder.button(text="⬅️ Отмена", callback_data="my_keys")
    builder.adjust(1)
    return builder.as_markup()