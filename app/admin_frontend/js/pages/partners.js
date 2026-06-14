const partnerState = { createdUrl: "" };

document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
  renderShell({
    activeKey: "partners",
    title: "Партнерская система",
    subtitle: "Создание ссылок и статистика по новым пользователям и пополнениям",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <h3>Создать ссылку</h3>
          <div class="form-grid">
            <input id="partner_name" type="text" placeholder="Название партнера" />
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
                  <th>Пополнения</th>
                  <th>Сумма</th>
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
    const data = await api(`/admin-api/partners?${params.toString()}`);
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

      const actions = document.createElement("div");
      actions.className = "row-actions";

      const copy = document.createElement("button");
      copy.textContent = "Копировать";
      copy.addEventListener("click", async () => {
        await navigator.clipboard.writeText(item.url);
        showToast("Ссылка скопирована", "success");
      });

      const toggle = document.createElement("button");
      toggle.className = item.is_active ? "btn-warn" : "btn-ok";
      toggle.textContent = item.is_active ? "Выключить" : "Включить";
      toggle.addEventListener("click", async (event) => {
        await withButtonLoading(event.currentTarget, async () => {
          await api(`/admin-api/partners/${item.id}`, {
            method: "PATCH",
            body: JSON.stringify({ is_active: !item.is_active }),
          });
          await loadPartners();
        }).catch((error) => alert(error.message));
      });

      actions.append(copy, toggle);
      tr.querySelector("td:last-child").appendChild(actions);
      tbody.appendChild(tr);
    });
  }

  q("create_partner").addEventListener("click", async (event) => {
    const payload = {
      name: q("partner_name").value.trim(),
      code: q("partner_code").value.trim() || null,
    };

    await withButtonLoading(event.currentTarget, async () => {
      const data = await api("/admin-api/partners", {
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
      showToast("Партнерская ссылка создана", "success");
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
