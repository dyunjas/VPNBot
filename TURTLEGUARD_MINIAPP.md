# Telegram Mini App and TurtleGuard

На https://miniapp.lunet.pro/miniapp/ проверена текущая страница защиты и её публичный JS. В HTML задаётся `window.__tgChal.next = "/miniapp/"`. Скрипт после проверки выполняет `location.replace(next)`. Фрагмент `#tgWebAppData=…` не входит в next и теряется **до загрузки приложения**. При первом запуске кэш приложения и SDK ещё пусты. Увеличение ожидания или повтор API-запроса не восстановит удалённые данные.

## Необходимое исправление на стороне TurtleGuard

Добавить содержимое `deploy/turtleguard-preserve-telegram.js` в шаблон challenge после установки `window.__tgChal` и до загрузки `/.turtleguard/c/*.js`. Скрипт добавляет исходный fragment к `next` только для перехода на тот же origin. Query string и path сохраняются. Альтернативное исправление непосредственно в коде защиты: сохранить `location.hash` при старте и добавить его к next перед обоими вызовами `location.replace`.

Проверка: открыть свежую WebView без cookies защиты через бота, пройти challenge и убедиться, что `tgWebAppData` остаётся в URL после редиректа и POST /api/profile содержит непустой initData. Не записывать initData в логи. Повторить после перезагрузки страницы и на iOS/Android.

У этой сессии нет доступа к панели TurtleGuard или серверу. Файл исправления готов для администратора защиты или её поддержки. Если настройка challenge-шаблона недоступна, передать описание и файл поддержке TurtleGuard. Отключать всю DDoS-защиту не требуется.

## Изменения проекта

- Раннее сохранение launch data, включая URL с hash-маршрутом и query-параметрами.
- Восстановление из sessionStorage приложения и штатного `__telegram__initParams` SDK, с ограничением срока. Текущие данные запуска имеют приоритет.
- Официальный SDK размещён локально в `frontend/static/assets/telegram-web-app.js` (источник https://telegram.org/js/telegram-web-app.js, получен 2026-10-13), чтобы его загрузка не зависела от доступности внешнего домена.
- Пустой initData никогда не отправляется. HTML challenge вместо JSON распознаётся. Запросы покупки/платежа не повторяются автоматически.
- Серверная проверка подписи и срока Telegram не изменена; initDataUnsafe не используется для входа.

Нужно развернуть `frontend/build/miniapp` и `frontend/static/assets`. Исправления проекта помогают при сохранённых параметрах, **но не заменяют исправление редиректа TurtleGuard при первом открытии**.

Проверки: `node --test tests/telegram-launch.test.mjs`, `npm run build --workspace lunet-miniapp --prefix frontend`.
