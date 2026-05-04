const usersState = { page: 1, pages: 1, selectedUserId: null };

function renderUsersLayout() {
  return `
    <div class="users-layout">
      <div class="toolbar">
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

      <div class="users-main-grid">
        <div class="card">
          <h3>Список пользователей</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>TG</th><th>Пользователь</th><th>Баланс</th><th>Подписка</th><th>Бан</th><th>Действия</th>
                </tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
          <div class="pager">
            <button id="prev">Назад</button>
            <span id="meta"></span>
            <button id="next">Вперёд</button>
          </div>
        </div>

        <div class="content-stack">
          <div class="card">
            <h3>Данные пользователя</h3>
            <div id="details" class="details-grid">Выберите пользователя из таблицы</div>
          </div>

          <div class="card">
            <h3>Управление</h3>
            <div class="toolbar">
              <input id="balance_amount" type="number" min="1" value="100" placeholder="Сумма" />
              <button id="btn_add_balance" class="btn-ok">Пополнить</button>
              <button id="btn_sub_balance" class="btn-warn">Списать</button>
              <button id="btn_toggle_ban" class="btn-danger">Бан / Разбан</button>
            </div>
            <div class="page-sub">Все действия применяются к выбранному пользователю.</div>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function userAction(userId, action, extra = {}) {
  await api(`/admin-api/users/${userId}/action`, {
    method: "POST",
    body: JSON.stringify({ action, ...extra }),
  });
  await loadUsers();
  await loadUserDetails(userId);
}

async function loadUserDetails(userId) {
  usersState.selectedUserId = userId;
  const data = await api(`/admin-api/users/${userId}`);

  const u = data.user || {};
  const sub = data.subscription || {};
  const txs = data.transactions || [];

  q("details").innerHTML = `
    <div class="card">
      <h4>Основное</h4>
      <div>ID: <b>${safeText(u.id)}</b></div>
      <div>Telegram ID: <b>${safeText(u.tg_id)}</b></div>
      <div>Username: <b>${safeText(u.username)}</b></div>
      <div>Email: <b>${safeText(u.email)}</b></div>
      <div>Баланс: <b>${safeText(u.balance)} RUB</b></div>
      <div>Статус: ${u.banned ? statusBadge("ban") : statusBadge("ok")}</div>
    </div>

    <div class="card">
      <h4>Подписка</h4>
      <div>План: <b>${safeText(sub.plan_name)}</b></div>
      <div>Статус: ${statusBadge(sub.status || "expired")}</div>
      <div>Активна до: <b>${formatDateTime(sub.current_period_end)}</b></div>
      <div>Автопродление: ${sub.auto_renew ? statusBadge("yes") : statusBadge("no")}</div>
    </div>

    <div class="card">
      <h4>Последние транзакции</h4>
      <div class="table-wrap">
        <table>
          <thead><tr><th>ID</th><th>Сумма</th><th>Система</th><th>Статус</th></tr></thead>
          <tbody>
            ${txs.slice(0, 8).map((t) => `<tr><td>${t.id}</td><td>${safeText(t.amount)} RUB</td><td>${safeText(t.payment_system)}</td><td>${statusBadge(t.paid ? "paid" : "unpaid")}</td></tr>`).join("") || "<tr><td colspan='4'>Нет транзакций</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>
  `;

  const toggle = q("btn_toggle_ban");
  if (toggle) toggle.textContent = u.banned ? "Разбанить" : "Забанить";
  await loadUsers();
}

function actionBtn(label, className, onClick) {
  const b = document.createElement("button");
  b.textContent = label;
  b.className = className || "";
  b.addEventListener("click", onClick);
  return b;
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

  const data = await api(`/admin-api/users?${params.toString()}`);
  const items = data.items || [];
  const meta = data.meta || { page: 1, pages: 1, total: 0 };
  usersState.pages = meta.pages;

  q("tbody").innerHTML = "";
  items.forEach((u) => {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${u.id}</td>
      <td>${u.tg_id}</td>
      <td>${safeText(u.username)}</td>
      <td>${u.balance}</td>
      <td>${u.subscription_active ? statusBadge("active") : statusBadge("expired")}</td>
      <td>${u.banned ? statusBadge("ban") : statusBadge("ok")}</td>
      <td></td>
    `;

    if (usersState.selectedUserId === u.id) {
      tr.classList.add("selected-user");
    }

    tr.style.cursor = "pointer";
    tr.addEventListener("click", () => loadUserDetails(u.id));

    const row = document.createElement("div");
    row.className = "row-actions";
    row.appendChild(actionBtn("Открыть", "", () => loadUserDetails(u.id)));
    row.appendChild(actionBtn("+100", "btn-ok", () => userAction(u.id, "add_balance", { amount: 100 })));
    row.appendChild(actionBtn("-100", "btn-warn", () => userAction(u.id, "sub_balance", { amount: 100 })));
    row.appendChild(actionBtn(u.banned ? "Разбан" : "Бан", "btn-danger", () => userAction(u.id, u.banned ? "unban" : "ban")));

    tr.querySelector("td:last-child").appendChild(row);
    q("tbody").appendChild(tr);
  });

  renderPager(meta, q("prev"), q("next"), q("meta"));
}

document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
  renderShell({
    activeKey: "users",
    title: "Пользователи",
    subtitle: "Поиск, фильтрация, управление балансом и статусом",
    contentHtml: renderUsersLayout(),
  });

  q("apply").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      usersState.page = 1;
      await loadUsers();
    }).catch((err) => alert(err.message));
  });

  q("prev").addEventListener("click", async (e) => {
    if (usersState.page <= 1) return;
    await withButtonLoading(e.currentTarget, async () => {
      usersState.page -= 1;
      await loadUsers();
    }).catch((err) => alert(err.message));
  });

  q("next").addEventListener("click", async (e) => {
    if (usersState.page >= usersState.pages) return;
    await withButtonLoading(e.currentTarget, async () => {
      usersState.page += 1;
      await loadUsers();
    }).catch((err) => alert(err.message));
  });

  q("btn_add_balance").addEventListener("click", async (e) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const amount = Number(q("balance_amount").value || "0");
    if (amount <= 0) return alert("Введите корректную сумму");
    await withButtonLoading(e.currentTarget, async () => {
      await userAction(usersState.selectedUserId, "add_balance", { amount });
      showToast("Баланс пополнен", "success");
    }).catch((err) => alert(err.message));
  });

  q("btn_sub_balance").addEventListener("click", async (e) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const amount = Number(q("balance_amount").value || "0");
    if (amount <= 0) return alert("Введите корректную сумму");
    await withButtonLoading(e.currentTarget, async () => {
      await userAction(usersState.selectedUserId, "sub_balance", { amount });
      showToast("Баланс списан", "success");
    }).catch((err) => alert(err.message));
  });

  q("btn_toggle_ban").addEventListener("click", async (e) => {
    if (!usersState.selectedUserId) return alert("Сначала выберите пользователя");
    const current = (q("btn_toggle_ban").textContent || "").toLowerCase();
    const action = current.includes("разбан") ? "ban" : "unban";
    await withButtonLoading(e.currentTarget, async () => {
      await userAction(usersState.selectedUserId, action);
      showToast(action === "ban" ? "Пользователь забанен" : "Пользователь разбанен", "success");
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["search"], "apply");
    await loadUsers();
  } catch (e) {
    alert(e.message);
  }
});