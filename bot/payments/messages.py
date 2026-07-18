AMOUNT_PROMPT = "Введите сумму пополнения в RUB."
AMOUNT_INVALID = "Введите целое положительное число больше 0."
PAYMENT_METHOD_PROMPT = "Выберите способ оплаты."
USER_NOT_FOUND = "Пользователь не найден. Перезапустите бота и попробуйте снова."
AMOUNT_NOT_FOUND = "Сумма платежа не найдена. Введите сумму заново."
UNKNOWN_METHOD = "Способ оплаты не распознан. Выберите другой вариант."
CREATE_ERROR = "Не удалось создать платеж. Попробуйте еще раз позже."


def created_auto_caption(*, method_name: str, transaction_id: str) -> str:
    return (
        "<tg-emoji emoji-id='5927169041595634481'>💵</tg-emoji> Счет создан, перейдите по ссылке для оплаты.\n\n"
        f"<b>Способ оплаты:</b> {method_name}\n"
        f"<pre>ID транзакции: {transaction_id}</pre>"
    )
