from aiogram.utils.keyboard import InlineKeyboardBuilder


def referral_kb(share_link_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="💳 Перевести на основной баланс", callback_data="transfer_referral_balance")
    builder.button(text="💸 Вывести", callback_data="withdraw_balance")
    builder.button(text="📥 Поделиться", url=share_link_url)
    builder.button(text="⬅️ Назад", callback_data="profile")

    builder.adjust(1)
    return builder.as_markup()


def back_referral_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="⬅️ Назад", callback_data="referral")

    builder.adjust(1)
    return builder.as_markup()


def withdraw_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить", callback_data="withdraw_confirm")
    builder.button(text="❌ Отмена", callback_data="withdraw_cancel")

    builder.adjust(1)
    return builder.as_markup()


def transfer_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Подтвердить перевод", callback_data="transfer_confirm")
    builder.button(text="❌ Отмена", callback_data="transfer_cancel")

    builder.adjust(1)
    return builder.as_markup()


def admin_withdraw_kb(withdrawal_id: int):
    builder = InlineKeyboardBuilder()
    builder.button(text="Approve", callback_data=f"admin_withdraw:approve:{withdrawal_id}")
    builder.button(text="Reject", callback_data=f"admin_withdraw:reject:{withdrawal_id}")

    builder.adjust(1)
    return builder.as_markup()
