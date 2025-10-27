from aiogram.utils.keyboard import InlineKeyboardBuilder
from urllib.parse import quote

def back_profile_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="profile")
    builder.adjust(1)
    return builder.as_markup()


def payment_choice_kb(amount: int):
    text = f"Пришлите ссылку на оплату {amount} RUB"
    encoded_text = quote(text)
    builder = InlineKeyboardBuilder()
    builder.button(text="СБП 1", callback_data="pay_pally")
    builder.button(text=f"Зарубежные карты", url=f"https://t.me/LunetVPNSupportBot?text={encoded_text}")
    builder.adjust(1)
    return builder.as_markup()


def payment_menu_kb(invoice_url, invoice_id, check_prefix: str = "check_payment"):
    builder = InlineKeyboardBuilder()
    builder.button(text="Оплатить", url=invoice_url)
    builder.button(
        text="🔄 Проверить оплату",
        callback_data=f"{check_prefix}:{invoice_id}"
    )
    builder.adjust(1, 1)
    return builder.as_markup()