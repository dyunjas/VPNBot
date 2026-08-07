const usersState = { page: 1, pages: 1, selectedUserId: null, sortBy: "created_at", sortDir: "desc" };

function formatTraffic(bytes) {
  const value = Number(bytes || 0);
  if (value <= 0) return "0 GB";
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function shortText(value, max = 18) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function shortId(value) {
  return shortText(value, 22);
}

function formatActivityValue(item) {
  const chunks = [];

  if (item.amount !== null && item.amount !== undefined && Number(item.amount) !== 0) {
    chunks.push(`${safeText(item.amount)} RUB`);
  }

  if (item.traffic_gb !== null && item.traffic_gb !== undefined && Number(item.traffic_gb) !== 0) {
    chunks.push(`${safeText(item.traffic_gb)} GB`);
  }

  if (item.subscription_id) {
    chunks.push(`Подписка #${safeText(item.subscription_id)}`);
  }

  if (item.transaction_id) {
    chunks.push(`Платеж #${safeText(item.transaction_id)}`);
  }

  if (item.provider_payment_id) {
    chunks.push(`Provider ${safeText(shortId(item.provider_payment_id))}`);
  }

  if (item.note) {
    const compactNote = String(item.note)
      .replace(/Ручное подтверждение платежа/gi, "Подтвержден")
      .replace(/Manual payment confirmation/gi, "Подтвержден")
      .replace(/Ручное пополнение/gi, "Пополнение")
      .replace(/Ручное списание/gi, "Списание");
    chunks.push(safeText(shortText(compactNote, 42)));
  }

  return chunks.join(" • ") || "Без деталей";
}

function userBanBadge(isBanned) {
  return isBanned
    ? `<span class="badge danger">Заблокирован</span>`
    : `<span class="badge ok">Доступ открыт</span>`;
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

function renderUsersLayout() {
  return `
    <div class="users-layout">
      <div class="card filter-card">
        <div class="toolbar toolbar--filters">
          <input id="search" type="text" placeholder="Поиск: Telegram ID / username / email" />
          <select id="banned">
            <option value="all">Все</option>
            <option value="exclude">Только не заблокированные</option>
            <option value="only">Только заблокированные</option>
          </select>
          <button id="apply" class="btn-primary">Применить</button>
          <button id="export_users" type="button">CSV</button>
        </div>
      </div>

      <div class="card users-table-card">
        <h3>Список пользователей</h3>
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                ${sortableTh("ID", "id", usersState.sortBy, usersState.sortDir)}
                ${sortableTh("Telegram ID", "tg_id", usersState.sortBy, usersState.sortDir)}
                ${sortableTh("Username", "username", usersState.sortBy, usersState.sortDir)}
                ${sortableTh("Баланс", "balance", usersState.sortBy, usersState.sortDir)}
                ${sortableTh("Подписка", "subscription_end", usersState.sortBy, usersState.sortDir)}
                <th>Бан</th>
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

      <div id="user_modal" class="user-modal" hidden>
        <button id="user_modal_overlay" class="user-modal__overlay" type="button" aria-label="Закрыть окно"></button>
        <div class="user-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="user_modal_title">
          <div class="user-modal__topbar">
            <div>
              <div class="user-modal__eyebrow">Пользователь</div>
              <h3 id="user_modal_title" class="user-modal__title">Карточка пользователя</h3>
            </div>
            <button id="user_modal_close" class="user-modal__close" type="button" aria-label="Закрыть окно">×</button>
          </div>

          <div class="user-modal__actions">
            <input id="balance_amount" type="number" min="1" value="100" placeholder="Сумма" />
            <button id="btn_add_balance" class="btn-info">Пополнить</button>
            <button id="btn_sub_balance" class="btn-outline-danger">Списать</button>
            <button id="btn_toggle_ban" class="btn-danger">Бан / Разбан</button>
          </div>

          <div id="details" class="user-modal__content"></div>
        </div>
      </div>
    </div>
  `;
}

function closeUserModal() {
  const modal = q("user_modal");
  if (!modal) return;
  modal.hidden = true;
  document.body.classList.remove("user-modal-open");
}

function openUserModal() {
  const modal = q("user_modal");
  if (!modal) return;
  if (modal.parentElement !== document.body) {
    document.body.appendChild(modal);
  }
  modal.hidden = false;
  modal.scrollTop = 0;
  modal.querySelector(".user-modal__dialog")?.scrollTo({ top: 0, left: 0 });
  document.body.classList.add("user-modal-open");
}

function renderUsersTableHead() {
  const thead = document.querySelector(".users-table-card thead");
  if (!thead) return;
  thead.innerHTML = `
    <tr>
      ${sortableTh("ID", "id", usersState.sortBy, usersState.sortDir)}
      ${sortableTh("Telegram ID", "tg_id", usersState.sortBy, usersState.sortDir)}
      ${sortableTh("Username", "username", usersState.sortBy, usersState.sortDir)}
      ${sortableTh("Баланс", "balance", usersState.sortBy, usersState.sortDir)}
      ${sortableTh("Подписка", "subscription_end", usersState.sortBy, usersState.sortDir)}
      <th>Бан</th>
    </tr>
  `;
  bindSortableTable(thead, usersState, async (button) => {
    await withButtonLoading(button, loadUsers).catch((error) => alert(error.message));
  });
}

async function userAction(userId, action, extra = {}) {
  await api(`/api/admin/users/${userId}/action`, {
    method: "POST",
    body: JSON.stringify({ action, ...extra }),
  });
  await loadUsers();
  await loadUserDetails(userId);
}

function renderInfoRow(label, value) {
  return `<div><span>${label}</span><b>${value}</b></div>`;
}

async function loadUserDetails(userId) {
  usersState.selectedUserId = userId;
  const data = await api(`/api/admin/users/${userId}`);

  const user = data.user || {};
  const summary = data.summary || {};
  const referral = data.referral || {};
  const subscription = data.subscription || {};
  const subscriptions = data.subscriptions || [];
  const transactions = data.transactions || [];
  const topups = data.topups || [];
  const activities = data.activities || [];

  q("user_modal_title").textContent = user.username ? `@${user.username}` : `Пользователь #${user.id}`;
  q("details").innerHTML = `
    <div class="user-modal__summary">
      <div class="user-summary-card">
        <span class="user-summary-card__label">Баланс</span>
        <strong>${safeText(user.balance)} RUB</strong>
      </div>
      <div class="user-summary-card">
        <span class="user-summary-card__label">Статус</span>
        <strong>${user.banned ? "Забанен" : "Активен"}</strong>
      </div>
      <div class="user-summary-card">
        <span class="user-summary-card__label">Подписка</span>
        <strong>${safeText(subscription.plan_name || "Нет")}</strong>
      </div>
      <div class="user-summary-card">
        <span class="user-summary-card__label">Трафик</span>
        <strong>${safeText(subscription.topup_gb || 0)} GB</strong>
      </div>
      <div class="user-summary-card">
        <span class="user-summary-card__label">Оплачено</span>
        <strong>${safeText(summary.paid_total || 0)} RUB</strong>
      </div>
      <div class="user-summary-card">
        <span class="user-summary-card__label">Рефералы</span>
        <strong>${safeText(summary.invited_count || 0)}</strong>
      </div>
    </div>

    <div class="user-modal__grid user-modal__grid--overview">
      <div class="details-section">
        <h4>Основное</h4>
        <div class="details-list">
          ${renderInfoRow("ID", safeText(user.id))}
          ${renderInfoRow("Telegram ID", safeText(user.tg_id))}
          ${renderInfoRow("Username", safeText(user.username || "—"))}
          ${renderInfoRow("Email", safeText(user.email || "—"))}
          ${renderInfoRow("Баланс", `${safeText(user.balance)} RUB`)}
          ${renderInfoRow("Лимит трафика", safeText(formatTraffic(user.traffic_limit_bytes)))}
          ${renderInfoRow("Создан", formatDateTime(user.created_at))}
          ${renderInfoRow("Обновлен", formatDateTime(user.updated_at))}
          <div><span>Статус</span>${userBanBadge(user.banned)}</div>
        </div>
      </div>

      <div class="details-section">
        <h4>Подписка</h4>
        <div class="details-list">
          ${renderInfoRow("План", safeText(subscription.plan_name || "—"))}
          <div><span>Статус</span>${statusBadge(subscription.status || "expired")}</div>
          ${renderInfoRow("Активна до", formatDateTime(subscription.current_period_end))}
          <div><span>Автопродление</span>${subscription.auto_renew ? statusBadge("yes") : statusBadge("no")}</div>
          ${renderInfoRow("Добавлено трафика", `${safeText(subscription.topup_gb || 0)} GB`)}
          ${renderInfoRow("Токен", safeText(shortId(subscription.subscription_token || user.subscription_token || "—")))}
        </div>
      </div>

      <div class="details-section">
        <h4>Remnawave</h4>
        <div class="details-list">
          ${renderInfoRow("User ID", safeText(user.remnawave_user_id || "—"))}
          ${renderInfoRow("UUID", safeText(user.remnawave_user_uuid || "—"))}
          ${renderInfoRow("Subscription URL", safeText(shortText(user.subscription_url || "—", 44)))}
        </div>
      </div>

      <div class="details-section">
        <h4>Реферальная система</h4>
        <div class="details-list">
          ${renderInfoRow("Аккаунт", safeText(referral.account_id || "—"))}
          ${renderInfoRow("Приглашено", safeText(referral.invited_count || summary.invited_count || 0))}
          ${renderInfoRow("Баланс", `${safeText(referral.referral_balance || 0)} RUB`)}
          ${renderInfoRow("Процент", `${safeText(referral.referral_percent || 0)}%`)}
        </div>
      </div>
    </div>

    <div class="user-modal__grid user-modal__grid--details">
      <div class="details-section details-section--compact">
        <div class="details-section__head">
          <h4>Все подписки</h4>
          <span class="details-section__meta">${subscriptions.length}</span>
        </div>
        <div class="table-wrap table-wrap--modal">
          <table>
            <thead><tr><th>ID</th><th>Тариф</th><th>Статус</th><th>Авто</th><th>Окончание</th></tr></thead>
            <tbody>
              ${subscriptions
                .slice(0, 10)
                .map(
                  (item) =>
                    `<tr><td>${safeText(item.id)}</td><td>${safeText(item.plan_name || `#${item.plan_id}`)}</td><td>${statusBadge(item.status || "expired")}</td><td>${item.auto_renew ? statusBadge("yes") : statusBadge("no")}</td><td>${formatDateTime(item.current_period_end)}</td></tr>`,
                )
                .join("") || "<tr><td colspan='5'>Нет подписок</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>

      <div class="details-section details-section--compact">
        <div class="details-section__head">
          <h4>Последние транзакции</h4>
          <span class="details-section__meta">${summary.transactions_total || transactions.length}</span>
        </div>
        <div class="table-wrap table-wrap--modal">
          <table>
            <thead><tr><th>ID</th><th>Сумма</th><th>Система</th><th>Статус</th></tr></thead>
            <tbody>
              ${transactions
                .slice(0, 8)
                .map(
                  (item) =>
                    `<tr><td>${safeText(item.id)}</td><td>${safeText(item.amount)} RUB</td><td>${safeText(item.payment_system)}</td><td>${statusBadge(item.paid ? "paid" : "unpaid")}</td></tr>`,
                )
                .join("") || "<tr><td colspan='4'>Нет транзакций</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>

      <div class="details-section details-section--compact">
        <div class="details-section__head">
          <h4>Начисления трафика</h4>
          <span class="details-section__meta">${topups.length}</span>
        </div>
        <div class="table-wrap table-wrap--modal">
          <table>
            <thead><tr><th>ID</th><th>GB</th><th>Подписка</th><th>Дата</th></tr></thead>
            <tbody>
              ${topups
                .slice(0, 10)
                .map(
                  (item) =>
                    `<tr><td>${safeText(item.id)}</td><td>${safeText(item.gb)} GB</td><td>${safeText(item.subscription_id)}</td><td>${formatDateTime(item.created_at)}</td></tr>`,
                )
                .join("") || "<tr><td colspan='4'>Нет начислений трафика</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <div class="details-section details-section--history">
      <div class="details-section__head">
        <h4>История действий</h4>
        <span class="details-section__meta">${activities.length}</span>
      </div>
      <div class="table-wrap table-wrap--modal table-wrap--history">
        <table>
          <thead><tr><th>Дата</th><th>Тип</th><th>Источник</th><th>Детали</th></tr></thead>
          <tbody>
            ${activities
              .slice(0, 20)
              .map(
                (item) =>
                  `<tr><td>${formatDateTime(item.created_at)}</td><td>${safeText(activityLabel(item))}</td><td>${safeText(item.source || item.category || "system")}</td><td>${formatActivityValue(item)}</td></tr>`,
              )
              .join("") || "<tr><td colspan='4'>История пока пуста</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>
  `;

  const toggle = q("btn_toggle_ban");
  if (toggle) {
    toggle.textContent = user.banned ? "Разбанить" : "Забанить";
    toggle.className = user.banned ? "btn-success" : "btn-danger";
  }
  openUserModal();
  await loadUsers();
}

async function loadUsers() {
  const tbody = q("tbody");
  setTableRefreshing(tbody, true);
  const params = new URLSearchParams({
    page: String(usersState.page),
    page_size: "25",
    search: q("search").value || "",
    sort_by: usersState.sortBy,
    sort_dir: usersState.sortDir,
    banned: q("banned").value,
  });

  try {
    const data = await api(`/api/admin/users?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    usersState.pages = meta.pages;

    renderUsersTableHead();
    tbody.innerHTML = "";
    items.forEach((user) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${safeText(user.id)}</td>
        <td>${safeText(user.tg_id)}</td>
        <td>${safeText(user.username || "—")}</td>
        <td><span class="money-cell">${safeText(user.balance)} RUB</span></td>
        <td>${user.subscription_active ? statusBadge("active") : statusBadge("expired")}</td>
        <td>${userBanBadge(user.banned)}</td>
      `;

      if (usersState.selectedUserId === user.id) {
        tr.classList.add("selected-user");
      }

      tr.classList.add("is-clickable-row");
      tr.addEventListener("click", () => loadUserDetails(user.id));
      tbody.appendChild(tr);
    });

    renderPager(meta, q("prev"), q("next"), q("meta"));
  } finally {
    setTableRefreshing(tbody, false);
  }
}

function bindModalControls() {
  q("user_modal_overlay")?.addEventListener("click", closeUserModal);
  q("user_modal_close")?.addEventListener("click", closeUserModal);

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeUserModal();
  });

  q("btn_add_balance")?.addEventListener("click", async (event) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const amount = Number(q("balance_amount").value || "0");
    if (amount <= 0) return alert("Введите корректную сумму");
    await withButtonLoading(event.currentTarget, async () => {
      await userAction(usersState.selectedUserId, "add_balance", { amount });
      showToast("Баланс пополнен", "success");
    }).catch((error) => alert(error.message));
  });

  q("btn_sub_balance")?.addEventListener("click", async (event) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const amount = Number(q("balance_amount").value || "0");
    if (amount <= 0) return alert("Введите корректную сумму");
    await withButtonLoading(event.currentTarget, async () => {
      await userAction(usersState.selectedUserId, "sub_balance", { amount });
      showToast("Баланс списан", "success");
    }).catch((error) => alert(error.message));
  });

  q("btn_toggle_ban")?.addEventListener("click", async (event) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const current = (q("btn_toggle_ban").textContent || "").toLowerCase();
    const action = current.includes("разбан") ? "unban" : "ban";
    await withButtonLoading(event.currentTarget, async () => {
      await userAction(usersState.selectedUserId, action);
      showToast(action === "ban" ? "Пользователь забанен" : "Пользователь разбанен", "success");
    }).catch((error) => alert(error.message));
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "users",
    title: "Пользователи",
    subtitle: "Поиск, фильтрация, управление статусом",
    contentHtml: renderUsersLayout(),
  });

  bindModalControls();
  renderUsersTableHead();

  q("apply").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      usersState.page = 1;
      await loadUsers();
    }).catch((error) => alert(error.message));
  });

  q("export_users").addEventListener("click", async (event) => {
    const params = new URLSearchParams({
      search: q("search").value || "",
      banned: q("banned").value,
    });
    await withButtonLoading(event.currentTarget, async () => {
      await downloadAdminFile(`/api/admin/export/users?${params.toString()}`, "users.csv");
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

  try {
    await renderSessionInfo();
    bindEnterSubmit(["search"], "apply");
    await loadUsers();
  } catch (error) {
    alert(error.message);
  }
});
