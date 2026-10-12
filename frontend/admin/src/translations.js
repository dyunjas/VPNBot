// Technical identifiers and user-provided text remain unchanged; interface labels are Russian.
export const fieldLabels = {
  subscription_token: "Токен подписки", role: "Роль", is_active: "Доступ включён",
  login: "Логин", text: "Текст сообщения", parse_mode: "Формат сообщения",
  include_banned: "Включая заблокированных", has_image: "Есть изображение", image_name: "Изображение",
  job_id: "Номер рассылки", total: "Всего", processed: "Обработано", success: "Успешно",
  failed: "Ошибки", error: "Ошибка", started_at: "Начало", finished_at: "Завершение",
  account_id: "Реферальный счёт", referral_balance: "Реферальный баланс", invited_count: "Приглашено",
  referral_percent: "Реферальный процент", transaction_id_ref: "Связанная операция",
  price: "Цена", plan_name: "Тариф", plan_price: "Стоимость тарифа", period_days: "Срок, дней",
  gb_limit: "Трафик, ГБ", purchase_limit: "Лимит покупок", display_order: "Порядок",
  is_hidden: "Скрыт", is_trial: "Пробный", is_exhausted: "Лимит исчерпан",
  usages: "Количество активаций", promocode_id: "Промокод", user_created_at: "Регистрация пользователя",
  paid_total: "Всего оплачено", subscriptions_count: "Число подписок", subscriptions_total: "Всего подписок",
  transactions_total: "Всего операций", activities_total: "Всего событий", topup_gb: "Добавлено, ГБ",
  last_paid_at: "Последняя оплата", last_payment_at: "Последняя оплата", attributed_at: "Приглашён",
  url: "Ссылка", link: "Ссылка", download_url: "Скачать", content: "Содержимое",
  path: "Адрес запроса", method: "Метод запроса", action: "Действие", details: "Подробности",
  ip_address: "IP-адрес", user_agent: "Браузер", reason: "Причина", status_code: "Код ответа",
  target_id: "Номер записи", level: "Уровень", logger: "Источник", line: "Строка журнала",
  time: "Время", message: "Сообщение", source: "Источник", result: "Результат",
  title: "Название", category: "Категория", note: "Примечание", currency: "Валюта",
  days: "Дни", gb: "Трафик, ГБ", subscription_id: "Подписка", admin_id: "Администратор",
  user_traffic_limit_bytes: "Лимит трафика пользователя", notified: "Уведомление отправлено",
  platform: "Платформа", hostname: "Имя сервера", server_id: "Сервер", country: "Страна",
  port: "Порт", public_host: "Адрес сервера", grpc_endpoint: "Адрес подключения",
  uptime: "Время работы", uptime_seconds: "Время работы, секунд", checked_at: "Проверено",
  total_gb: "Всего, ГБ", used_gb: "Использовано, ГБ", available_gb: "Доступно, ГБ",
  traffic_gb: "Трафик, ГБ", duration_hours: "Длительность, часов", traffic: "Трафик",
  percent: "Процент", used: "Использовано", available: "Доступно", count: "Количество",
  total_keys_count: "Всего ключей", active_keys_count: "Активные ключи", latency_ms: "Задержка, мс",
  service: "Сервис", size_bytes: "Размер файла", filename: "Имя файла", key: "Ключ",
  free_gb: "Свободно, ГБ", cpu_count: "Процессоры", frequency_mhz: "Частота, МГц",
  physical_cores: "Физические ядра", logical_cores: "Логические ядра", threads: "Потоки",
  load_average: "Средняя нагрузка", rss: "Оперативная память", rss_gb: "Оперативная память, ГБ",
  vms: "Виртуальная память", vms_gb: "Виртуальная память, ГБ", pid: "Номер процесса",
  boot_time: "Запуск системы", metrics_available: "Метрики доступны", metrics_source: "Источник метрик",
  elapsed_seconds: "Прошло, секунд", last_time: "Последнее событие", summary: "Сводка",
  ready: "Готово", scheduled: "Запланировано", problem: "Проблемы", overall: "Общий результат",
  label: "Подпись", value: "Значение", rate: "Доля", premium_emoji_note: "Примечание об эмодзи",
  invoice_url: "Ссылка на оплату", status_url: "Статус оплаты", already_paid: "Уже оплачено",
  subscription_active: "Подписка активна", active_now: "Активна сейчас", gb_left: "Остаток трафика",
  remnawave_user_id: "Номер пользователя на сервере", remnawave_user_uuid: "Идентификатор пользователя на сервере",
  tg_id: "ID в Telegram", total_users: "Всего пользователей", active_subscriptions: "Активные подписки",
  paid_transactions: "Оплаченные операции", total_revenue: "Выручка", month_revenue: "Выручка за месяц",
  banned_users: "Заблокированные пользователи", total_servers: "Всего серверов", total_devices: "Всего устройств",
  active_keys: "Активные ключи", subscription: "Подписка", user: "Пользователь", plan: "Тариф",
  maintenance: "Обслуживание", warn: "Предупреждение", danger: "Ошибка", info: "Информация",
};

const states = {
  active: "Активна", expired: "Истекла", canceled: "Отменена", cancelled: "Отменена",
  past_due: "Просрочена", pending: "Ожидает подтверждения", approved: "Одобрено", rejected: "Отклонено",
  queued: "В очереди", running: "Выполняется", completed: "Завершено", finished: "Завершено",
  failed: "Ошибка", stopped: "Остановлено", success: "Успешно", paid: "Оплачено", unpaid: "Не оплачено",
};
export function translateValue(key, value) {
  if (key === "status") return states[String(value).toLowerCase()] || "Неизвестный статус";
  if (key === "role") return ({ support: "Поддержка", superadmin: "Суперадминистратор" })[value] || "Неизвестная роль";
  if (key === "action") {
    const [method, resource] = String(value).split(" ");
    const verbs = { POST: "Создание / действие", PATCH: "Изменение", PUT: "Изменение", DELETE: "Удаление", GET: "Выгрузка" };
    const resources = { users: "пользователи", subscriptions: "подписки", plans: "тарифы", transactions: "платежи", admins: "администраторы", broadcast: "рассылки", legal: "документы", withdrawals: "выводы", partners: "партнёры", maintenance: "обслуживание", promocodes: "промокоды", auth: "авторизация", referrals: "рефералы" };
    if (verbs[method]) return `${verbs[method]}: ${resources[resource] || "панель управления"}`;
  }
  if (key === "reason") return ({ invalid_credentials: "Неверные данные для входа", invalid_totp: "Неверный код подтверждения", invalid_code: "Неверный код", logout: "Выход из системы", success: "Успешно", password_login: "Вход по паролю" })[value] || null;
  return null;
}

export function translateError(detail, status) {
  if (typeof detail === "string" && /[а-яё]/i.test(detail)) return detail;
  const messages = {
    "Invalid credentials": "Неверная почта или пароль.", "Invalid code": "Неверный код подтверждения.",
    "Invalid or expired verification code": "Код неверный или срок его действия истёк. Проверьте код или начните вход заново.",
    "Invalid verification code": "Неверный код подтверждения. Введите актуальный код из приложения-аутентификатора.",
    "Unable to send verification code": "Не удалось отправить письмо с кодом. Повторите позже.",
    "Security configuration is incomplete": "Вход временно недоступен. Обратитесь к администратору сервера.",
    "Request origin is not allowed": "Не удалось подтвердить безопасность запроса. Откройте страницу заново.",
    "HTTPS is required": "Откройте сайт по защищённому адресу HTTPS.",
    "Invalid CSRF token": "Сеанс устарел. Обновите страницу и повторите действие.",
    "admin email already exists": "Администратор с такой почтой уже существует.",
    "admin username already exists": "Это имя администратора уже используется.",
    "admin email already exists or is invalid": "Проверьте почту: адрес неверен или уже используется.",
    "admin access not found": "Администратор не найден.",
  };
  return messages[detail] || ({ 400: "Проверьте введённые данные.", 401: "Необходим повторный вход.",
    403: "Недостаточно прав для этого действия.", 404: "Запись не найдена.",
    409: "Изменение невозможно: проверьте данные и текущий статус записи.",
    422: "Заполните обязательные поля и проверьте формат значений.",
    429: "Слишком много попыток. Повторите позже." })[status] || `Не удалось выполнить действие (код ${status}). Повторите позже.`;
}
