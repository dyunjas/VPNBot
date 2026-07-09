const partnerState = { createdUrl: "", expandedPartnerId: null };

function renderPartnerDetails(details) {
  const summary = details.summary || {};
  const users = details.users || [];
  const payments = details.recent_payments || [];

  return `
    <div class="partner-details">
      <div class="partner-details__summary">
        <div><span>Привязанных пользователей</span><b>${safeText(summary.attributed_users)}</b></div>
        <div><span>Пользователей с оплатами</span><b>${safeText(summary.paid_users)}</b></div>
        <div><span>Всего пополнений</span><b>${safeText(summary.paid_topups)}</b></div>
        <div><span>Общая сумма</span><b>${safeText(summary.paid_amount)} RUB</b></div>
        <div><span>Последнее пополнение</span><b>${formatDateTime(summary.last_payment_at)}</b></div>
      </div>

      <div class="partner-details__grid">
        <div class="partner-details__card">
          <h4>Пользователи по ссылке</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>User ID</th>
                  <th>Telegram ID</th>
                  <th>Username</th>
                  <th>Пополнений</th>
                  <th>Сумма</th>
                  <th>Макс. чек</th>
                  <th>Последнее пополнение</th>
                  <th>Пришёл по ссылке</th>
                </tr>
              </thead>
              <tbody>
                ${
                  users.length
                    ? users
                        .map(
                          (user) => `
                            <tr>
                              <td>${safeText(user.user_id)}</td>
                              <td>${safeText(user.tg_id)}</td>
                              <td>${safeText(user.username)}</td>
                              <td>${safeText(user.paid_topups)}</td>
                              <td>${safeText(user.paid_amount)} RUB</td>
                              <td>${safeText(user.max_paid_amount)} RUB</td>
                              <td>${formatDateTime(user.last_paid_at)}</td>
                              <td>${formatDateTime(user.attributed_at)}</td>
                            </tr>
                          `,
                        )
                        .join("")
                    : "<tr><td colspan='8'>Нет пользователей по этой ссылке</td></tr>"
                }
              </tbody>
            </table>
          </div>
        </div>

        <div class="partner-details__card">
          <h4>Последние пополнения</h4>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>TX ID</th>
                  <th>User ID</th>
                  <th>Telegram ID</th>
                  <th>Username</th>
                  <th>Сумма</th>
                  <th>Система</th>
                  <th>Дата оплаты</th>
                </tr>
              </thead>
              <tbody>
                ${
                  payments.length
                    ? payments
                        .map(
                          (payment) => `
                            <tr>
                              <td>${safeText(payment.transaction_id)}</td>
                              <td>${safeText(payment.user_id)}</td>
                              <td>${safeText(payment.tg_id)}</td>
                              <td>${safeText(payment.username)}</td>
                              <td>${safeText(payment.amount)} RUB</td>
                              <td>${safeText(payment.payment_system)}</td>
                              <td>${formatDateTime(payment.paid_at)}</td>
                            </tr>
                          `,
                        )
                        .join("")
                    : "<tr><td colspan='7'>Нет оплаченных пополнений</td></tr>"
                }
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  `;
}

async function togglePartnerDetails(item, hostRow, triggerBtn) {
  const alreadyOpen = hostRow.dataset.open === "1";

  document.querySelectorAll(".partner-details-row").forEach((row) => {
    row.dataset.open = "0";
    row.style.display = "none";
  });
  document.querySelectorAll(".js-partner-details").forEach((btn) => {
    btn.textContent = "Детали";
    btn.classList.remove("is-active");
  });

  if (alreadyOpen) {
    partnerState.expandedPartnerId = null;
    return;
  }

  await withButtonLoading(triggerBtn, async () => {
    const data = await api(`/api/admin/partners/${item.id}/details`);
    const detailsCell = hostRow.querySelector("td");
    detailsCell.innerHTML = renderPartnerDetails(data);
    hostRow.style.display = "";
    hostRow.dataset.open = "1";
    triggerBtn.textContent = "Скрыть";
    triggerBtn.classList.add("is-active");
    partnerState.expandedPartnerId = item.id;
  }).catch((error) => alert(error.message));
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "partners",
    title: "Партнёрская система",
    subtitle: "Создание ссылок и статистика по новым пользователям и пополнениям",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <h3>Создать ссылку</h3>
          <div class="form-grid">
            <input id="partner_name" type="text" placeholder="Название партнёра" />
            <input id="partner_code" type="text" placeholder="Код ссылки (необязательно)" />
          </div>
          <div class="toolbar" style="margin-top:10px">
            <button id="create_partner" class="btn-primary">Создать</button>
            <button id="reload_partners">Обновить список</button>
          </div>
          <div id="created_link" class="summary-list" style="margin-top:10px; display:none;"></div>
        </div>

        <div class="card">
          <h3>Ссылки</h3>
          <div class="toolbar">
            <input id="search" type="text" placeholder="Поиск по названию или коду" />
            <button id="apply" class="btn-primary">Фильтр</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Код</th>
                  <th>Ссылка</th>
                  <th>Новые пользователи</th>
                  <th>Оплаченные пополнения</th>
                  <th>Сумма пополнений</th>
                  <th>Статус</th>
                  <th>Создана</th>
                  <th>Действия</th>
                </tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
        </div>
      </div>
    `,
  });

  async function loadPartners() {
    const params = new URLSearchParams({ search: q("search").value || "" });
    const data = await api(`/api/admin/partners?${params.toString()}`);
    const items = data.items || [];
    const tbody = q("tbody");
    tbody.innerHTML = "";

    items.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${safeText(item.id)}</td>
        <td>${safeText(item.name)}</td>
        <td><span class="mono">${safeText(item.code)}</span></td>
        <td><span class="mono">${safeText(item.url)}</span></td>
        <td>${safeText(item.new_users)}</td>
        <td>${safeText(item.paid_topups)}</td>
        <td>${safeText(item.paid_amount)} RUB</td>
        <td>${item.is_active ? statusBadge("active") : statusBadge("disabled")}</td>
        <td>${formatDateTime(item.created_at)}</td>
        <td></td>
      `;
      const detailsTr = document.createElement("tr");
      detailsTr.className = "partner-details-row";
      detailsTr.style.display = "none";
      detailsTr.dataset.open = "0";
      detailsTr.innerHTML = `<td colspan="10"></td>`;

      const actions = document.createElement("div");
      actions.className = "row-actions";

      const copy = document.createElement("button");
      copy.className = "btn-outline-primary";
      copy.textContent = "Копировать";
      copy.addEventListener("click", async () => {
        await navigator.clipboard.writeText(item.url);
        showToast("Ссылка скопирована", "success");
      });

      const details = document.createElement("button");
      details.className = "btn-outline-primary js-partner-details";
      details.textContent = "Детали";
      details.addEventListener("click", async (event) => {
        event.stopPropagation();
        await togglePartnerDetails(item, detailsTr, event.currentTarget);
      });

      const toggle = document.createElement("button");
      toggle.className = item.is_active ? "btn-danger" : "btn-success";
      toggle.textContent = item.is_active ? "Выключить" : "Включить";
      toggle.addEventListener("click", async (event) => {
        await withButtonLoading(event.currentTarget, async () => {
          await api(`/api/admin/partners/${item.id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !item.is_active }),
          });
          await loadPartners();
        }).catch((error) => alert(error.message));
      });

      actions.append(copy, details, toggle);
      tr.querySelector("td:last-child").appendChild(actions);
      tbody.appendChild(tr);
      tbody.appendChild(detailsTr);

      if (partnerState.expandedPartnerId === item.id) {
        details.click();
      }
    });
  }

  q("create_partner").addEventListener("click", async (event) => {
    const payload = {
      name: q("partner_name").value.trim(),
      code: q("partner_code").value.trim() || null,
    };

    await withButtonLoading(event.currentTarget, async () => {
      const data = await api("/api/admin/partners", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      partnerState.createdUrl = data.item?.url || "";
      q("partner_name").value = "";
      q("partner_code").value = "";
      const created = q("created_link");
      if (created) {
        created.style.display = "grid";
        created.innerHTML = `
          <div><span>Ссылка создана</span><b class="mono">${safeText(partnerState.createdUrl)}</b></div>
          <div><span>Код</span><b class="mono">${safeText(data.item?.code)}</b></div>
        `;
      }
      await loadPartners();
      showToast("Партнёрская ссылка создана", "success");
    }).catch((error) => alert(error.message));
  });

  q("reload_partners").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      await loadPartners();
    }).catch((error) => alert(error.message));
  });

  q("apply").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      await loadPartners();
    }).catch((error) => alert(error.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["partner_name", "partner_code"], "create_partner");
    bindEnterSubmit(["search"], "apply");
    await loadPartners();
  } catch (error) {
    alert(error.message);
  }
});
