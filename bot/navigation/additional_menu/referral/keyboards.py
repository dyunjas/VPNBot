from aiogram.utils.keyboard import InlineKeyboardBuilder


def referral_kb(share_link_url):
    builder = InlineKeyboardBuilder()
    builder.button(text="Перевести на основной баланс", callback_data="transfer_referral_balance", icon_custom_emoji_id="5967390100357648692", style="success")
    builder.button(text="Вывести", callback_data="withdraw_balance", icon_custom_emoji_id="5811989245761426317", style="success")
    builder.button(text="Поделиться", url=share_link_url, icon_custom_emoji_id="5899757765743615694", style="primary")
    builder.button(text="Назад", callback_data="profile", icon_custom_emoji_id="5877536313623711363", style="primary")

    builder.adjust(1)
    return builder.as_markup()


def back_referral_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Назад", callback_data="referral", icon_custom_emoji_id="5877536313623711363", style="primary")

    builder.adjust(1)
    return builder.as_markup()


def withdraw_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить", callback_data="withdraw_confirm", icon_custom_emoji_id="5776375003280838798", style="success")
    builder.button(text="Отмена", callback_data="withdraw_cancel", icon_custom_emoji_id="5778527486270770928", style="danger")

    builder.adjust(1)
    return builder.as_markup()


def transfer_confirm_kb():
    builder = InlineKeyboardBuilder()
    builder.button(text="Подтвердить перевод", callback_data="transfer_confirm", icon_custom_emoji_id="5776375003280838798", style="success")
    builder.button(text="Отмена", callback_data="transfer_cancel", icon_custom_emoji_id="5778527486270770928", style="danger")

    builder.adjust(1)
    return builder.as_markup()
