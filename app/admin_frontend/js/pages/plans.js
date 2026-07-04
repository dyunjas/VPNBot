document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "plans",
    title: "Тарифы",
    subtitle: "Настройка планов подписок",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <h3>Список тарифов</h3>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>Название</th><th>Цена</th><th>Дней</th><th>Лимит ГБ</th><th>Подписок</th><th>Действие</th></tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
        </div>

        <div class="content-grid">
          <div class="card">
            <h3>Создать тариф</h3>
            <div class="form-grid">
              <input id="new_name" type="text" placeholder="Название тарифа" />
              <input id="new_price" type="number" placeholder="Цена, RUB" />
              <input id="new_days" type="number" placeholder="Период, дней" value="30" />
              <input id="new_gb" type="number" placeholder="Лимит трафика, ГБ" value="100" />
            </div>
            <div class="toolbar" style="margin-top:10px">
              <button id="create_plan" class="btn-primary">Создать</button>
            </div>
          </div>

          <div class="card">
            <h3>Редактировать тариф</h3>
            <div class="form-grid">
              <input id="edit_id" type="number" placeholder="ID тарифа" />
              <input id="edit_name" type="text" placeholder="Название" />
              <input id="edit_price" type="number" placeholder="Цена" />
              <input id="edit_days" type="number" placeholder="Период, дней" />
              <input id="edit_gb" type="number" placeholder="Лимит ГБ" />
            </div>
            <div class="toolbar" style="margin-top:10px">
              <button id="update_plan">Сохранить</button>
            </div>
          </div>
        </div>
      </div>
    `,
  });

  async function loadPlans() {
    const data = await api("/api/admin/plans");
    const items = data.items || [];
    q("tbody").innerHTML = "";

    items.forEach((p) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${p.id}</td>
        <td>${p.name}</td>
        <td>${p.price}</td>
        <td>${p.period_days}</td>
        <td>${p.gb_limit ?? 0}</td>
        <td>${p.subscriptions_count}</td>
        <td class="row-actions">
          <button data-edit="${p.id}">Изменить</button>
          <button class="btn-danger" data-delete="${p.id}">Удалить</button>
        </td>
      `;
      q("tbody").appendChild(tr);
    });

    q("tbody").querySelectorAll("button[data-edit]").forEach((b) => {
      b.addEventListener("click", () => {
        q("edit_id").value = b.getAttribute("data-edit");
      });
    });

    q("tbody").querySelectorAll("button[data-delete]").forEach((b) => {
      b.addEventListener("click", async (e) => {
        const planId = Number(b.getAttribute("data-delete") || "0");
        if (!planId) return;
        if (!confirm(`Удалить тариф #${planId}? Действие необратимо.`)) return;

        await withButtonLoading(e.currentTarget, async () => {
          await api(`/api/admin/plans/${planId}`, { method: "DELETE" });
          await loadPlans();
          showToast("Тариф удален", "success");
        }).catch((err) => alert(err.message));
      });
    });
  }

  q("create_plan").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      await api("/api/admin/plans", {
        method: "POST",
        body: JSON.stringify({
          name: q("new_name").value.trim(),
          price: Number(q("new_price").value),
          period_days: Number(q("new_days").value),
          gb_limit: Number(q("new_gb").value),
        }),
      });
      await loadPlans();
      showToast("Тариф создан", "success");
    }).catch((err) => alert(err.message));
  });

  q("update_plan").addEventListener("click", async (e) => {
    const id = Number(q("edit_id").value || "0");
    if (!id) return alert("Введите ID тарифа");

    const payload = {};
    if (q("edit_name").value) payload.name = q("edit_name").value.trim();
    if (q("edit_price").value) payload.price = Number(q("edit_price").value);
    if (q("edit_days").value) payload.period_days = Number(q("edit_days").value);
    if (q("edit_gb").value) payload.gb_limit = Number(q("edit_gb").value);

    await withButtonLoading(e.currentTarget, async () => {
      await api(`/api/admin/plans/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadPlans();
      showToast("Тариф обновлен", "success");
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["new_name", "new_price", "new_days", "new_gb"], "create_plan");
    bindEnterSubmit(["edit_id", "edit_name", "edit_price", "edit_days", "edit_gb"], "update_plan");
    await loadPlans();
  } catch (e) {
    alert(e.message);
  }
});
