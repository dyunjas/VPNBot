const usersState = { page: 1, pages: 1, selectedUserId: null };

function formatTraffic(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return "0 GB";
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function formatActivityValue(item) {
  const chunks = [];
  if (item.amount !== null && item.amount !== undefined) chunks.push(`${safeText(item.amount)} RUB`);
  if (item.traffic_gb !== null && item.traffic_gb !== undefined) chunks.push(`${safeText(item.traffic_gb)} GB`);
  if (item.note) chunks.push(safeText(item.note));
  return chunks.join(" • ") || "Без деталей";
}

function activityLabel(item) {
  const labels = {
    user_created: "Регистрация",
    ban: "Блокировка",
    unban: "Разблокировка",
    add_balance: "Ручное пополнение",
    sub_balance: "Ручное списание",
    add_traffic: "Ручная выдача трафика",
    balance_added: "Начисление баланса",
    balance_subtracted: "Списание баланса",
    payment_confirmed: "Подтверждение платежа",
    subscription_activated: "Активация подписки",
    subscription_renewed: "Продление подписки",
    subscription_expired: "Истечение подписки",
    subscription_created: "Создание подписки",
    subscription_updated: "Изменение подписки",
    subscription_deleted: "Удаление подписки",
    subscription_bulk_extended: "Массовое продление",
    subscription_purchased: "Покупка подписки",
    traffic_added: "Выдача трафика",
    traffic_purchased: "Покупка трафика",
    auto_renew_changed: "Автопродление",
    promocode_activated: "Промокод",
  };
  return labels[item.action] || item.action || "Событие";
}

function renderEmptyUserState() {
  return `
    <div class="empty-user-state">
      <div class="empty-user-state__icon">
        <svg viewBox="0 0 24 24" aria-hidden="true">
          <circle cx="12" cy="8.5" r="3.2"></circle>
          <path d="M5.5 18c1.4-3.1 4-4.8 6.5-4.8S17.1 14.9 18.5 18"></path>
        </svg>
      </div>
      <div class="empty-user-state__text">Информация о пользователе появится здесь</div>
    </div>
  `;
}

function renderUsersLayout() {
  return `
    <div class="users-layout">
      <div class="card filter-card">
        <div class="toolbar toolbar--filters">
          <input id="search" type="text" placeholder="Поиск: Telegram ID / username / email" />
          <select id="sort_by">
            <option value="created_at">Дата создания</option>
            <option value="id">ID</option>
            <option value="updated_at">Дата обновления</option>
            <option value="tg_id">Telegram ID</option>
            <option value="username">Username</option>
            <option value="email">Email</option>
            <option value="balance">Баланс</option>
            <option value="subscription_end">Дата окончания подписки</option>
          </select>
          <select id="sort_dir">
            <option value="desc">По убыванию</option>
            <option value="asc">По возрастанию</option>
          </select>
          <select id="banned">
            <option value="all">Все</option>
            <option value="exclude">Только не заблокированные</option>
            <option value="only">Только заблокированные</option>
          </select>
          <button id="apply" class="btn-primary">Применить</button>
        </div>
      </div>

      <div class="users-main-grid">
        <div class="card users-table-card">
          <h3>Список пользователей</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Telegram ID</th><th>Username</th><th>Баланс</th><th>Подписка</th><th>Бан</th><th>Действия</th>
                </tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
          <div class="pager pager--minimal">
            <button id="prev" class="btn-pager">Назад</button>
            <span id="meta" class="pager__meta"></span>
            <button id="next" class="btn-pager">Вперёд</button>
          </div>
        </div>

        <div class="content-stack side-panel-stack">
          <div class="card side-card">
            <h3>Данные пользователя</h3>
            <div id="details" class="details-grid details-grid--empty">${renderEmptyUserState()}</div>
          </div>

          <div class="card side-card">
            <h3>Управление</h3>
            <div class="toolbar toolbar--management">
              <input id="balance_amount" type="number" min="1" value="100" placeholder="Сумма" />
              <button id="btn_add_balance" class="btn-info">Пополнить</button>
              <button id="btn_sub_balance" class="btn-warn">Списать</button>
              <button id="btn_toggle_ban" class="btn-outline-danger">Бан / Разбан</button>
            </div>
            <div class="page-sub">Все действия применяются к выбранному пользователю.</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function userAction(userId, action, extra = {}) {
  await api(`/api/admin/users/${userId}/action`, {
    method: "POST",
    body: JSON.stringify({ action, ...extra }),
  });
  await loadUsers();
  await loadUserDetails(userId);
}

async function loadUserDetails(userId) {
  usersState.selectedUserId = userId;
  const data = await api(`/api/admin/users/${userId}`);

  const user = data.user || {};
  const subscription = data.subscription || {};
  const transactions = data.transactions || [];
  const topups = data.topups || [];
  const activities = data.activities || [];

  q("details").innerHTML = `
    <div class="details-section">
      <h4>Основное</h4>
      <div class="details-list">
        <div><span>ID</span><b>${safeText(user.id)}</b></div>
        <div><span>Telegram ID</span><b>${safeText(user.tg_id)}</b></div>
        <div><span>Username</span><b>${safeText(user.username)}</b></div>
        <div><span>Email</span><b>${safeText(user.email)}</b></div>
        <div><span>Баланс</span><b>${safeText(user.balance)} RUB</b></div>
        <div><span>Лимит трафика</span><b>${safeText(formatTraffic(user.traffic_limit_bytes))}</b></div>
        <div><span>Статус</span>${user.banned ? statusBadge("ban") : statusBadge("ok")}</div>
      </div>
    </div>

    <div class="details-section">
      <h4>Подписка</h4>
      <div class="details-list">
        <div><span>План</span><b>${safeText(subscription.plan_name)}</b></div>
        <div><span>Статус</span>${statusBadge(subscription.status || "expired")}</div>
        <div><span>Активна до</span><b>${formatDateTime(subscription.current_period_end)}</b></div>
        <div><span>Автопродление</span>${subscription.auto_renew ? statusBadge("yes") : statusBadge("no")}</div>
        <div><span>Добавлено трафика</span><b>${safeText(subscription.topup_gb || 0)} GB</b></div>
      </div>
    </div>

    <div class="details-section">
      <h4>Последние транзакции</h4>
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Сумма</th><th>Система</th><th>Статус</th></tr></thead>
          <tbody>
            ${transactions
              .slice(0, 8)
              .map(
                (item) =>
                  `<tr><td>${safeText(item.id)}</td><td>${safeText(item.amount)} RUB</td><td>${safeText(item.payment_system)}</td><td>${statusBadge(item.paid ? "paid" : "unpaid")}</td></tr>`
              )
              .join("") || "<tr><td colspan='4'>Нет транзакций</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>

    <div class="details-section">
      <h4>Начисления трафика</h4>
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>GB</th><th>Подписка</th><th>Дата</th></tr></thead>
          <tbody>
            ${topups
              .slice(0, 10)
              .map(
                (item) =>
                  `<tr><td>${safeText(item.id)}</td><td>${safeText(item.gb)} GB</td><td>${safeText(item.subscription_id)}</td><td>${formatDateTime(item.created_at)}</td></tr>`
              )
              .join("") || "<tr><td colspan='4'>Нет начислений трафика</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>

    <div class="details-section">
      <h4>История действий</h4>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Дата</th><th>Тип</th><th>Источник</th><th>Детали</th></tr></thead>
          <tbody>
            ${activities
              .slice(0, 20)
              .map(
                (item) =>
                  `<tr><td>${formatDateTime(item.created_at)}</td><td>${safeText(activityLabel(item))}</td><td>${safeText(item.source || item.category)}</td><td>${formatActivityValue(item)}</td></tr>`
              )
              .join("") || "<tr><td colspan='4'>История пока пуста</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>
  `;
  q("details").classList.remove("details-grid--empty");

  const toggle = q("btn_toggle_ban");
  if (toggle) toggle.textContent = user.banned ? "Разбанить" : "Забанить";
  await loadUsers();
}

function actionBtn(label, className, onClick) {
  const button = document.createElement("button");
  button.textContent = label;
  button.className = className || "";
  button.addEventListener("click", onClick);
  return button;
}

async function loadUsers() {
  const params = new URLSearchParams({
    page: String(usersState.page),
    page_size: "25",
    search: q("search").value || "",
    sort_by: q("sort_by").value,
    sort_dir: q("sort_dir").value,
    banned: q("banned").value,
  });

  const data = await api(`/api/admin/users?${params.toString()}`);
  const items = data.items || [];
  const meta = data.meta || { page: 1, pages: 1, total: 0 };
  usersState.pages = meta.pages;

  q("tbody").innerHTML = "";
  items.forEach((user) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${safeText(user.id)}</td>
      <td>${safeText(user.tg_id)}</td>
      <td>${safeText(user.username)}</td>
      <td>${safeText(user.balance)}</td>
      <td>${user.subscription_active ? statusBadge("active") : statusBadge("expired")}</td>
      <td>${user.banned ? statusBadge("ban") : statusBadge("ok")}</td>
      <td></td>
    `;

    if (usersState.selectedUserId === user.id) {
      tr.classList.add("selected-user");
    }

    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => loadUserDetails(user.id));

    const actions = document.createElement("div");
    actions.className = "row-actions";
    actions.appendChild(actionBtn("Открыть", "btn-outline-primary", () => loadUserDetails(user.id)));
    actions.appendChild(actionBtn("+100", "btn-outline-success", () => userAction(user.id, "add_balance", { amount: 100 })));
    actions.appendChild(actionBtn("-100", "btn-outline-danger", () => userAction(user.id, "sub_balance", { amount: 100 })));
    actions.appendChild(actionBtn(user.banned ? "Разбан" : "Бан", "btn-solid-danger", () => userAction(user.id, user.banned ? "unban" : "ban")));

    tr.querySelector("td:last-child").appendChild(actions);
    q("tbody").appendChild(tr);
  });

  renderPager(meta, q("prev"), q("next"), q("meta"));
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "users",
    title: "Пользователи",
    subtitle: "Поиск, фильтрация, управление статусом",
    contentHtml: renderUsersLayout(),
  });

  q("apply").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      usersState.page = 1;
      await loadUsers();
    }).catch((error) => alert(error.message));
  });

  q("prev").addEventListener("click", async (event) => {
    if (usersState.page <= 1) return;
    await withButtonLoading(event.currentTarget, async () => {
      usersState.page -= 1;
      await loadUsers();
    }).catch((error) => alert(error.message));
  });

  q("next").addEventListener("click", async (event) => {
    if (usersState.page >= usersState.pages) return;
    await withButtonLoading(event.currentTarget, async () => {
      usersState.page += 1;
      await loadUsers();
    }).catch((error) => alert(error.message));
  });

  q("btn_add_balance").addEventListener("click", async (event) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const amount = Number(q("balance_amount").value || "0");
    if (amount <= 0) return alert("Введите корректную сумму");
    await withButtonLoading(event.currentTarget, async () => {
      await userAction(usersState.selectedUserId, "add_balance", { amount });
      showToast("Баланс пополнен", "success");
    }).catch((error) => alert(error.message));
  });

  q("btn_sub_balance").addEventListener("click", async (event) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const amount = Number(q("balance_amount").value || "0");
    if (amount <= 0) return alert("Введите корректную сумму");
    await withButtonLoading(event.currentTarget, async () => {
      await userAction(usersState.selectedUserId, "sub_balance", { amount });
      showToast("Баланс списан", "success");
    }).catch((error) => alert(error.message));
  });

  q("btn_toggle_ban").addEventListener("click", async (event) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const current = (q("btn_toggle_ban").textContent || "").toLowerCase();
    const action = current.includes("разбан") ? "unban" : "ban";
    await withButtonLoading(event.currentTarget, async () => {
      await userAction(usersState.selectedUserId, action);
      showToast(action === "ban" ? "Пользователь забанен" : "Пользователь разбанен", "success");
    }).catch((error) => alert(error.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["search"], "apply");
    await loadUsers();
  } catch (error) {
    alert(error.message);
  }
});
