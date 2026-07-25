AMOUNT_PROMPT = "Введите сумму пополнения в RUB."
AMOUNT_INVALID = "Введите целое положительное число больше 0."
PAYMENT_METHOD_PROMPT = "Выберите способ оплаты."
USER_NOT_FOUND = "Пользователь не найден. Перезапустите бота и попробуйте снова."
AMOUNT_NOT_FOUND = "Сумма платежа не найдена. Введите сумму заново."
UNKNOWN_METHOD = "Способ оплаты не распознан. Выберите другой вариант."
CREATE_ERROR = "Не удалось создать платеж. Попробуйте еще раз позже."


def created_auto_caption(*, method_name: str, transaction_id: str) -> str:
    return (
        "<b><tg-emoji emoji-id='5967390100357648692'>💵</tg-emoji> Счет создан на оплату создан.</b>\n\n"
        f"<blockquote><b><tg-emoji emoji-id=5769403330761593044>👛</tg-emoji> Способ оплаты:</b> {method_name}\n"
        f"<tg-emoji emoji-id=5956561916573782596>📄</tg-emoji> ID транзакции: {transaction_id}</blockquote>\n\n"
        "<i><tg-emoji emoji-id='5879785854284599288'>ℹ️</tg-emoji> После оплаты баланс пополнится автоматически. Если этого не произошло, обратитесь в поддержку @LunetVpnSupport.</i>"
    )
