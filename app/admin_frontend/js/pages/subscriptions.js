const subState = { page: 1, pages: 1, sortBy: "current_period_end", sortDir: "desc" };

function closeSubscriptionModal() {
  const modal = q("subscription_modal");
  if (!modal) return;
  modal.hidden = true;
  document.body.classList.remove("user-modal-open");
}

function openSubscriptionModal(mode) {
  const modal = q("subscription_modal");
  if (!modal) return;
  const titles = {
    bulk: "Массовое продление",
    create: "Создание подписки",
    edit: "Редактирование подписки",
    traffic: "Добавить трафик",
  };
  q("subscription_modal_title").textContent = titles[mode] || "Действие с подпиской";
  document.querySelectorAll(".subscription-modal-panel").forEach((panel) => {
    panel.hidden = panel.dataset.panel !== mode;
  });
  modal.hidden = false;
  modal.scrollTop = 0;
  modal.querySelector(".user-modal__dialog")?.scrollTo({ top: 0, left: 0 });
  document.body.classList.add("user-modal-open");

  const focusMap = {
    bulk: "bulk_days",
    create: "new_user_id",
    edit: "edit_plan_id",
    traffic: "traffic_gb",
  };
  setTimeout(() => q(focusMap[mode])?.focus(), 0);
}

function renderSubscriptionsTableHead() {
  const thead = document.querySelector(".subscriptions-table thead");
  if (!thead) return;
  thead.innerHTML = `
    <tr>
      ${sortableTh("ID", "id", subState.sortBy, subState.sortDir)}
      ${sortableTh("Пользователь", "user_id", subState.sortBy, subState.sortDir)}
      <th>Telegram</th>
      <th>Тариф</th>
      ${sortableTh("Статус", "status", subState.sortBy, subState.sortDir)}
      <th>Авто</th>
      <th>Устройства</th>
      ${sortableTh("Окончание", "current_period_end", subState.sortBy, subState.sortDir)}
    </tr>
  `;
  bindSortableTable(thead, subState, async (button) => {
    await withButtonLoading(button, loadRows).catch((error) => alert(error.message));
  });
}

function formatBytesAsGb(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 GB";
  return `${(value / 1024 ** 3).toFixed(2)} GB`;
}

function shortText(value, max = 18) {
  const text = String(value || "").trim();
  if (!text) return "";
  return text.length > max ? `${text.slice(0, max)}...` : text;
}

function renderSubInfoRow(label, value) {
  return `<div><span>${label}</span><b>${value}</b></div>`;
}

function renderSubscriptionDetailsBody(details) {
  const sub = details.subscription || {};
  const user = details.user || {};
  const plan = details.plan || {};
  const traffic = details.traffic || {};
  const topups = details.topups || [];
  const activities = details.activities || [];
  const transactions = details.transactions || [];

  return `
    <div class="subscription-card-details">
      <div class="user-modal__summary">
        <div class="user-summary-card">
          <span class="user-summary-card__label">Статус</span>
          <strong>${statusBadge(sub.status || "expired")}</strong>
        </div>
        <div class="user-summary-card">
          <span class="user-summary-card__label">Тариф</span>
          <strong>${safeText(plan.name || `#${sub.plan_id || "—"}`)}</strong>
        </div>
        <div class="user-summary-card">
          <span class="user-summary-card__label">Авто</span>
          <strong>${sub.auto_renew ? "Включено" : "Выключено"}</strong>
        </div>
        <div class="user-summary-card">
          <span class="user-summary-card__label">Трафик</span>
          <strong>${safeText(traffic.topup_gb || 0)} GB</strong>
        </div>
      </div>

      <div class="user-modal__grid user-modal__grid--overview">
        <div class="details-section">
          <h4>Подписка</h4>
          <div class="details-list">
            ${renderSubInfoRow("ID", safeText(sub.id))}
            ${renderSubInfoRow("Старт", formatDateTime(sub.current_period_start))}
            ${renderSubInfoRow("Окончание", formatDateTime(sub.current_period_end))}
            ${renderSubInfoRow("Следующее списание", formatDateTime(sub.next_renewal_at))}
            ${renderSubInfoRow("Устройств", safeText(sub.device_limit ?? 0))}
            ${renderSubInfoRow("GB left", safeText(sub.gb_left ?? 0))}
            ${renderSubInfoRow("Токен", safeText(shortText(sub.subscription_token || "—", 36)))}
          </div>
        </div>

        <div class="details-section">
          <h4>Пользователь</h4>
          <div class="details-list">
            ${renderSubInfoRow("ID", safeText(user.id))}
            ${renderSubInfoRow("Telegram", safeText(user.tg_id || "—"))}
            ${renderSubInfoRow("Username", safeText(user.username || "—"))}
            ${renderSubInfoRow("Email", safeText(user.email || "—"))}
            ${renderSubInfoRow("Баланс", `${safeText(user.balance || 0)} RUB`)}
            <div><span>Доступ</span>${user.banned ? `<span class="badge danger">Заблокирован</span>` : `<span class="badge ok">Открыт</span>`}</div>
          </div>
        </div>

        <div class="details-section">
          <h4>Remnawave</h4>
          <div class="details-list">
            ${renderSubInfoRow("User ID", safeText(user.remnawave_user_id || "—"))}
            ${renderSubInfoRow("UUID", safeText(user.remnawave_user_uuid || "—"))}
            ${renderSubInfoRow("URL", safeText(shortText(user.subscription_url || "—", 44)))}
          </div>
        </div>

        <div class="details-section">
          <h4>Тариф и трафик</h4>
          <div class="details-list">
            ${renderSubInfoRow("Цена", plan.price === null || plan.price === undefined ? "—" : `${safeText(plan.price)} RUB`)}
            ${renderSubInfoRow("Период", plan.period_days ? `${safeText(plan.period_days)} дней` : "—")}
            ${renderSubInfoRow("Лимит тарифа", plan.gb_limit === null || plan.gb_limit === undefined ? "—" : `${safeText(plan.gb_limit)} GB`)}
            ${renderSubInfoRow("Лимит пользователя", formatBytesAsGb(traffic.user_traffic_limit_bytes))}
            ${renderSubInfoRow("Topups", `${safeText(traffic.topup_gb || 0)} GB`)}
          </div>
        </div>
      </div>

      <div class="user-modal__grid user-modal__grid--details">
        <div class="details-section details-section--compact">
          <div class="details-section__head"><h4>Topups</h4><span class="details-section__meta">${topups.length}</span></div>
          <div class="table-wrap table-wrap--modal">
            <table>
              <thead><tr><th>ID</th><th>GB</th><th>Дата</th></tr></thead>
              <tbody>
                ${topups.slice(0, 10).map((item) => `<tr><td>${safeText(item.id)}</td><td>${safeText(item.gb)} GB</td><td>${formatDateTime(item.created_at)}</td></tr>`).join("") || "<tr><td colspan='3'>Нет начислений</td></tr>"}
              </tbody>
            </table>
          </div>
        </div>

        <div class="details-section details-section--compact">
          <div class="details-section__head"><h4>Платежи пользователя</h4><span class="details-section__meta">${transactions.length}</span></div>
          <div class="table-wrap table-wrap--modal">
            <table>
              <thead><tr><th>ID</th><th>Сумма</th><th>Система</th><th>Статус</th></tr></thead>
              <tbody>
                ${transactions.slice(0, 8).map((item) => `<tr><td>${safeText(item.id)}</td><td>${safeText(item.amount)} RUB</td><td>${safeText(item.payment_system)}</td><td>${statusBadge(item.paid ? "paid" : "unpaid")}</td></tr>`).join("") || "<tr><td colspan='4'>Нет платежей</td></tr>"}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div class="details-section details-section--history">
        <div class="details-section__head"><h4>История изменений</h4><span class="details-section__meta">${activities.length}</span></div>
        <div class="table-wrap table-wrap--modal">
          <table>
            <thead><tr><th>Дата</th><th>Действие</th><th>Источник</th><th>Детали</th></tr></thead>
            <tbody>
              ${activities.slice(0, 24).map((item) => `<tr><td>${formatDateTime(item.created_at)}</td><td>${safeText(item.action)}</td><td>${safeText(item.source || item.category || "system")}</td><td>${safeText(item.note || item.amount || item.traffic_gb || "—")}</td></tr>`).join("") || "<tr><td colspan='4'>История пуста</td></tr>"}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  `;
}

async function openSubscriptionCard(row, subscription) {
  const details = await api(`/api/admin/subscriptions/${subscription.id}/details`);
  showRowContextMenu(row, [], {
    title: `Подписка #${subscription.id}`,
    icon: "calendarStats",
    className: "row-context-menu--subscription-card",
    render: (body) => {
      body.innerHTML = renderSubscriptionDetailsBody(details);
      const actions = document.createElement("div");
      actions.className = "subscription-card-actions";
      actions.append(
        createRowContextButton("Изменить", "", (event, button) => {
          renderSubscriptionInlineEdit(subscription, button);
        }, true),
        createRowContextButton("+ трафик", "row-action-menu__item--success", () => {
          q("traffic_sub_id").value = subscription.id;
          q("traffic_gb").value = "";
          openSubscriptionModal("traffic");
          q("traffic_gb").focus();
        }),
        createRowContextButton("Удалить", "row-action-menu__item--danger", async (event, button) => {
          if (!confirm(`Удалить подписку #${subscription.id}? Действие необратимо.`)) return;
          await withButtonLoading(button, async () => {
            await api(`/api/admin/subscriptions/${subscription.id}`, { method: "DELETE" });
            await loadRows();
            showToast("Подписка удалена", "success");
          }).catch((error) => alert(error.message));
        }),
      );
      body.prepend(actions);
    },
  });
}

function renderSubscriptionInlineEdit(subscription, button) {
  const body = button.closest(".row-context-menu")?.querySelector(".row-context-menu__body");
  if (!body) return;
  const status = subscription.status || "";
  body.innerHTML = `
    <div class="row-context-inline-form">
      <input data-sub-field="plan_id" type="number" value="${escapeHtml(subscription.plan_id || "")}" placeholder="ID тарифа" />
      <select data-sub-field="status">
        <option value="">Статус</option>
        <option value="active" ${status === "active" ? "selected" : ""}>Активна</option>
        <option value="past_due" ${status === "past_due" ? "selected" : ""}>Просрочена</option>
        <option value="expired" ${status === "expired" ? "selected" : ""}>Истекла</option>
        <option value="canceled" ${status === "canceled" ? "selected" : ""}>Отменена</option>
      </select>
      <input data-sub-field="device_limit" type="number" value="${escapeHtml(subscription.device_limit ?? 0)}" placeholder="Лимит устройств" />
      <input data-sub-field="extend_days" type="number" placeholder="Продлить на дней" />
      <div class="row-context-inline-form__actions">
        <button class="btn-secondary" type="button" data-inline-cancel>Назад</button>
        <button class="btn-primary" type="button" data-inline-save>Сохранить</button>
      </div>
    </div>
  `;
  initFancySelects(body);

  body.querySelector("[data-inline-cancel]")?.addEventListener("click", () => closeRowContextMenu());
  body.querySelector("[data-inline-save]")?.addEventListener("click", async (event) => {
    const field = (name) => body.querySelector(`[data-sub-field="${name}"]`);
    const payload = {};
    if (field("plan_id").value) payload.plan_id = Number(field("plan_id").value);
    if (field("status").value) payload.status = field("status").value;
    if (field("device_limit").value !== "") payload.device_limit = Number(field("device_limit").value || "0");
    if (field("extend_days").value) payload.extend_days = Number(field("extend_days").value);

    await withButtonLoading(event.currentTarget, async () => {
      await api(`/api/admin/subscriptions/${subscription.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadRows();
      closeRowContextMenu();
      showToast("Подписка обновлена", "success");
    }).catch((error) => alert(error.message));
  });
}

async function loadRows() {
  const tbody = q("tbody");
  setTableRefreshing(tbody, true);
  const params = new URLSearchParams({
    page: String(subState.page),
    page_size: "25",
    search: q("search").value || "",
    status: q("status").value,
    sort_by: subState.sortBy,
    sort_dir: subState.sortDir,
  });

  try {
    const data = await api(`/api/admin/subscriptions?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    subState.pages = meta.pages;

    renderSubscriptionsTableHead();
    tbody.innerHTML = "";
    items.forEach((subscription) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${subscription.id}</td>
        <td>${subscription.user_id}</td>
        <td>${subscription.tg_id || ""}</td>
        <td>${subscription.plan_name || subscription.plan_id}</td>
        <td>${statusBadge(subscription.status)}</td>
        <td>${subscription.auto_renew ? statusBadge("yes") : statusBadge("no")}</td>
        <td>${subscription.device_limit ?? 0}</td>
        <td>${formatDateTime(subscription.current_period_end)}</td>
      `;

      tr.classList.add("is-clickable-row");
      tr.addEventListener("click", async (event) => {
        event.stopPropagation();
        await openSubscriptionCard(tr, subscription).catch((error) => alert(error.message));
      });

      tbody.appendChild(tr);
    });

    renderPager(meta, q("prev"), q("next"), q("meta"));
  } finally {
    setTableRefreshing(tbody, false);
  }
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "subscriptions",
    title: "Подписки",
    subtitle: "Создание, редактирование и фильтрация подписок",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <div class="section-title">Фильтрация подписок</div>
          <div class="toolbar subscriptions-toolbar">
            <input id="search" type="text" placeholder="Поиск: ID пользователя / Telegram ID / username" />
            <select id="status">
              <option value="all">Все статусы</option>
              <option value="active">Активна</option>
              <option value="past_due">Просрочена</option>
              <option value="expired">Истекла</option>
              <option value="canceled">Отменена</option>
            </select>
            <button id="apply" class="btn-primary">Фильтр</button>
            <button id="export_subscriptions" type="button">CSV</button>
            <button id="open_bulk_extend" type="button">Продлить</button>
            <button id="open_create_sub" class="btn-primary" type="button">Создать</button>
          </div>
        </div>

        <div class="card">
          <div class="table-wrap">
            <table class="subscriptions-table">
              <thead></thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
          <div class="pager">
            <button id="prev">Назад</button>
            <span id="meta"></span>
            <button id="next">Вперед</button>
          </div>
        </div>

        <div id="subscription_modal" class="user-modal admin-form-modal" hidden>
          <button id="subscription_modal_overlay" class="user-modal__overlay" type="button" aria-label="Закрыть окно"></button>
          <div class="user-modal__dialog admin-form-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="subscription_modal_title">
            <div class="user-modal__topbar">
              <div>
                <div class="user-modal__eyebrow">Подписки</div>
                <h3 id="subscription_modal_title" class="user-modal__title">Действие с подпиской</h3>
              </div>
              <button id="subscription_modal_close" class="user-modal__close" type="button" aria-label="Закрыть окно">×</button>
            </div>

            <div class="subscription-modal-panel admin-form-modal__body" data-panel="bulk" hidden>
              <div class="section-title">Продлевает срок в панели и в локальной базе, затем рассылает уведомления в Telegram.</div>
              <div class="form-grid" style="margin-top:10px">
                <select id="bulk_target">
                  <option value="all">Все подписки</option>
                  <option value="active">Только активные</option>
                  <option value="inactive">Только неактивные</option>
                </select>
                <input id="bulk_days" type="number" min="1" step="1" placeholder="На сколько дней продлить" />
              </div>
              <div class="admin-form-modal__actions">
                <button id="bulk_extend" class="btn-primary" type="button">Продлить выбранным</button>
              </div>
            </div>

            <div class="subscription-modal-panel admin-form-modal__body" data-panel="create" hidden>
              <div class="form-grid">
                <input id="new_user_id" type="number" placeholder="ID пользователя" />
                <input id="new_plan_id" type="number" placeholder="ID тарифа" />
              </div>
              <div class="admin-form-modal__actions">
                <label class="plans-flag subscription-auto-flag"><input id="new_auto" type="checkbox" /> <span>Автопродление</span></label>
                <button id="create_sub" class="btn-primary" type="button">Создать</button>
              </div>
            </div>

            <div class="subscription-modal-panel admin-form-modal__body" data-panel="edit" hidden>
              <div class="form-grid">
                <input id="edit_sub_id" type="number" placeholder="ID подписки" />
                <input id="edit_plan_id" type="number" placeholder="ID тарифа (опционально)" />
                <select id="edit_status">
                  <option value="">Статус (опционально)</option>
                  <option value="active">Активна</option>
                  <option value="past_due">Просрочена</option>
                  <option value="expired">Истекла</option>
                  <option value="canceled">Отменена</option>
                </select>
                <input id="edit_device_limit" type="number" placeholder="Лимит устройств" />
                <input id="edit_extend_days" type="number" placeholder="Продлить на дней" />
              </div>
              <div class="admin-form-modal__actions">
                <button id="update_sub" type="button">Сохранить</button>
              </div>
            </div>

            <div class="subscription-modal-panel admin-form-modal__body" data-panel="traffic" hidden>
              <div class="form-grid">
                <input id="traffic_sub_id" type="number" placeholder="ID активной подписки" />
                <input id="traffic_gb" type="number" min="1" step="1" placeholder="Сколько GB добавить" />
              </div>
              <div class="admin-form-modal__actions">
                <button id="add_traffic" class="btn-primary" type="button">Начислить трафик</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `,
  });

  q("apply").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      subState.page = 1;
      await loadRows();
    }).catch((error) => alert(error.message));
  });

  q("export_subscriptions").addEventListener("click", async (event) => {
    const params = new URLSearchParams({
      search: q("search").value || "",
      status: q("status").value,
    });
    await withButtonLoading(event.currentTarget, async () => {
      await downloadAdminFile(`/api/admin/export/subscriptions?${params.toString()}`, "subscriptions.csv");
    }).catch((error) => alert(error.message));
  });

  q("prev").addEventListener("click", async (event) => {
    if (subState.page <= 1) return;
    await withButtonLoading(event.currentTarget, async () => {
      subState.page -= 1;
      await loadRows();
    }).catch((error) => alert(error.message));
  });

  q("next").addEventListener("click", async (event) => {
    if (subState.page >= subState.pages) return;
    await withButtonLoading(event.currentTarget, async () => {
      subState.page += 1;
      await loadRows();
    }).catch((error) => alert(error.message));
  });

  q("create_sub").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      await api("/api/admin/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          user_id: Number(q("new_user_id").value),
          plan_id: Number(q("new_plan_id").value),
          auto_renew: q("new_auto").checked,
        }),
      });
      await loadRows();
      closeSubscriptionModal();
      showToast("Подписка создана", "success");
    }).catch((error) => alert(error.message));
  });

  q("update_sub").addEventListener("click", async (event) => {
    const id = Number(q("edit_sub_id").value || "0");
    if (!id) return alert("Введите ID подписки");

    const payload = {};
    if (q("edit_plan_id").value) payload.plan_id = Number(q("edit_plan_id").value);
    if (q("edit_status").value) payload.status = q("edit_status").value;
    if (q("edit_device_limit").value !== "") payload.device_limit = Number(q("edit_device_limit").value || "0");
    if (q("edit_extend_days").value) payload.extend_days = Number(q("edit_extend_days").value);

    await withButtonLoading(event.currentTarget, async () => {
      await api(`/api/admin/subscriptions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadRows();
      closeSubscriptionModal();
      showToast("Подписка обновлена", "success");
    }).catch((error) => alert(error.message));
  });

  q("add_traffic").addEventListener("click", async (event) => {
    const subscriptionId = Number(q("traffic_sub_id").value || "0");
    const gb = Number(q("traffic_gb").value || "0");
    if (!subscriptionId) return alert("Введите ID подписки");
    if (gb <= 0) return alert("Введите количество GB");

    await withButtonLoading(event.currentTarget, async () => {
      await api(`/api/admin/subscriptions/${subscriptionId}/traffic`, {
        method: "POST",
        body: JSON.stringify({ gb }),
      });
      await loadRows();
      closeSubscriptionModal();
      showToast("Трафик начислен", "success");
    }).catch((error) => alert(error.message));
  });

  q("bulk_extend").addEventListener("click", async (event) => {
    const days = Number(q("bulk_days").value || "0");
    const target = q("bulk_target").value || "all";
    if (!days || days < 1) return alert("Введите количество дней");

    const targetLabel = {
      all: "всем пользователям с подписками",
      active: "пользователям с активной подпиской",
      inactive: "пользователям с неактивной подпиской",
    }[target] || "выбранной группе";

    if (!confirm(`Продлить подписку на ${days} дн. ${targetLabel}?`)) return;

    await withButtonLoading(event.currentTarget, async () => {
      const result = await api("/api/admin/subscriptions/bulk-extend", {
        method: "POST",
        body: JSON.stringify({ target, days }),
      });
      await loadRows();
      closeSubscriptionModal();
      const failed = Array.isArray(result.failed) ? result.failed : [];
      showToast(
        `Продлено: ${result.updated || 0}. Уведомления: ${result.notified || 0}. Ошибки: ${failed.length}.`,
        failed.length ? "error" : "success",
      );
      if (failed.length) {
        const preview = failed
          .slice(0, 10)
          .map((item) => `#${item.subscription_id} / user ${item.user_id}: ${item.error}`)
          .join("\n");
        alert(`Часть подписок не обработана:\n${preview}`);
      }
    }).catch((error) => alert(error.message));
  });

  q("open_bulk_extend").addEventListener("click", () => openSubscriptionModal("bulk"));
  q("open_create_sub").addEventListener("click", () => {
    q("new_user_id").value = "";
    q("new_plan_id").value = "";
    q("new_auto").checked = false;
    openSubscriptionModal("create");
  });
  q("subscription_modal_overlay")?.addEventListener("click", closeSubscriptionModal);
  q("subscription_modal_close")?.addEventListener("click", closeSubscriptionModal);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeSubscriptionModal();
  });

  try {
    await renderSessionInfo();
    renderSubscriptionsTableHead();
    bindEnterSubmit(["search"], "apply");
    bindEnterSubmit(["bulk_days"], "bulk_extend");
    bindEnterSubmit(["new_user_id", "new_plan_id"], "create_sub");
    bindEnterSubmit(["edit_sub_id", "edit_plan_id", "edit_device_limit", "edit_extend_days"], "update_sub");
    bindEnterSubmit(["traffic_sub_id", "traffic_gb"], "add_traffic");
    await loadRows();
  } catch (error) {
    alert(error.message);
  }
});
