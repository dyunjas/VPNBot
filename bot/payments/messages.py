AMOUNT_PROMPT = "Введите сумму пополнения в RUB."
AMOUNT_INVALID = "Введите целое положительное число больше 0."
PAYMENT_METHOD_PROMPT = "Выберите способ оплаты."
USER_NOT_FOUND = "Пользователь не найден. Перезапустите бота и попробуйте снова."
AMOUNT_NOT_FOUND = "Сумма платежа не найдена. Введите сумму заново."
UNKNOWN_METHOD = "Способ оплаты не распознан. Выберите другой вариант."
CREATE_ERROR = "Не удалось создать платеж. Попробуйте еще раз позже."
NOT_CONFIRMED = "Платеж еще не подтвержден. Проверьте его через пару минут."
TRANSACTION_NOT_FOUND = "Платеж не найден. Если вы уже оплатили, напишите в поддержку."
CONFIRM_ERROR = "Не удалось проверить платеж. Попробуйте еще раз позже."


def created_caption(*, method_name: str, transaction_id: str) -> str:
    return (
        "<tg-emoji emoji-id='5927169041595634481'>💵</tg-emoji> Счет создан, перейдите по ссылке для оплаты.\n"
        f"<b>Способ оплаты:</b> {method_name}\n"
        f"<pre>ID транзакции: {transaction_id}</pre>"
    )


def success_caption(*, amount_rub: int) -> str:
    return (
        "<tg-emoji emoji-id='5776375003280838798'>✅</tg-emoji> Оплата подтверждена.\n"
        f"<b>Баланс пополнен на:</b> {amount_rub} RUB"
    )


def referral_bonus_caption(*, bonus_rub: int, payment_amount_rub: int) -> str:
    return (
        "<tg-emoji emoji-id='5994502837327892086'>🎉</tg-emoji> Бонус за реферала!\n"
        f"<b><tg-emoji emoji-id='5956148757899776734'>⭐️</tg-emoji> Начислено:</b> {bonus_rub} RUB\n"
        f"<b><tg-emoji emoji-id='5769403330761593044'>💄</tg-emoji> Платеж реферала:</b> {payment_amount_rub} RUB"
    )
