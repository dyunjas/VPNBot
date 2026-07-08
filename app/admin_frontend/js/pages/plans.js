document.addEventListener("DOMContentLoaded", async () => {
  let latestPlans = [];

  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "plans",
    title: "Тарифы",
    subtitle: "Настройка планов подписок",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <h3>Список тарифов</h3>
          <div id="plans_mobile_list" class="plans-mobile-list"></div>
          <div class="table-wrap plans-table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>Название</th><th>Статус</th><th>Цена</th><th>Дней</th><th>Лимит ГБ</th><th>Подписок</th><th>Действие</th></tr>
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
            <div class="plans-flags">
              <label class="plans-flag"><input id="new_hidden" type="checkbox" /> <span>Скрыть от пользователей</span></label>
              <label class="plans-flag"><input id="new_trial" type="checkbox" /> <span>Trial для новых пользователей</span></label>
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
            <div class="plans-flags">
              <label class="plans-flag"><input id="edit_hidden" type="checkbox" /> <span>Скрыть от пользователей</span></label>
              <label class="plans-flag"><input id="edit_trial" type="checkbox" /> <span>Trial для новых пользователей</span></label>
            </div>
            <div class="toolbar" style="margin-top:10px">
              <button id="update_plan">Сохранить</button>
            </div>
          </div>
        </div>
      </div>
    `,
  });

  function planBadges(plan) {
    const badges = [];
    badges.push(plan.is_hidden ? `<span class="badge warn">Скрыт</span>` : `<span class="badge ok">Виден</span>`);
    if (plan.is_trial) badges.push(`<span class="badge">Trial</span>`);
    return badges.join(" ");
  }

  function resetCreateForm() {
    q("new_name").value = "";
    q("new_price").value = "";
    q("new_days").value = "30";
    q("new_gb").value = "100";
    q("new_hidden").checked = false;
    q("new_trial").checked = false;
  }

  function fillEditForm(plan) {
    q("edit_id").value = plan.id;
    q("edit_name").value = plan.name || "";
    q("edit_price").value = plan.price ?? "";
    q("edit_days").value = plan.period_days ?? "";
    q("edit_gb").value = plan.gb_limit ?? "";
    q("edit_hidden").checked = Boolean(plan.is_hidden);
    q("edit_trial").checked = Boolean(plan.is_trial);
  }

  function bindDelete(selector, attr, reload) {
    document.querySelectorAll(selector).forEach((button) => {
      button.addEventListener("click", async (e) => {
        const planId = Number(button.getAttribute(attr) || "0");
        if (!planId) return;
        if (!confirm(`Удалить тариф #${planId}? Действие необратимо.`)) return;

        await withButtonLoading(e.currentTarget, async () => {
          await api(`/api/admin/plans/${planId}`, { method: "DELETE" });
          await reload();
          showToast("Тариф удален", "success");
        }).catch((err) => alert(err.message));
      });
    });
  }

  async function loadPlans() {
    const data = await api("/api/admin/plans");
    const items = data.items || [];
    latestPlans = items;
    q("tbody").innerHTML = "";
    q("plans_mobile_list").innerHTML = "";

    items.forEach((plan) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${plan.id}</td>
        <td>${safeText(plan.name)}</td>
        <td>${planBadges(plan)}</td>
        <td>${plan.price}</td>
        <td>${plan.period_days}</td>
        <td>${plan.gb_limit ?? 0}</td>
        <td>${plan.subscriptions_count}</td>
        <td class="row-actions">
          <button data-edit="${plan.id}">Изменить</button>
          <button class="btn-danger" data-delete="${plan.id}">Удалить</button>
        </td>
      `;
      q("tbody").appendChild(tr);

      const card = document.createElement("article");
      card.className = "plans-mobile-card";
      card.innerHTML = `
        <div class="plans-mobile-card__head">
          <div>
            <div class="plans-mobile-card__id">#${plan.id}</div>
            <h4>${safeText(plan.name)}</h4>
          </div>
          <div class="plans-mobile-card__badges">${planBadges(plan)}</div>
        </div>
        <div class="plans-mobile-card__grid">
          <div><span>Цена</span><b>${plan.price} RUB</b></div>
          <div><span>Период</span><b>${plan.period_days} дн.</b></div>
          <div><span>Лимит</span><b>${plan.gb_limit ?? 0} ГБ</b></div>
          <div><span>Подписок</span><b>${plan.subscriptions_count}</b></div>
        </div>
        <div class="row-actions">
          <button data-mobile-edit="${plan.id}">Изменить</button>
          <button class="btn-danger" data-mobile-delete="${plan.id}">Удалить</button>
        </div>
      `;
      q("plans_mobile_list").appendChild(card);
    });

    q("tbody").querySelectorAll("button[data-edit]").forEach((button) => {
      button.addEventListener("click", () => {
        const planId = Number(button.getAttribute("data-edit") || "0");
        const plan = items.find((item) => item.id === planId);
        if (plan) fillEditForm(plan);
      });
    });

    document.querySelectorAll("button[data-mobile-edit]").forEach((button) => {
      button.addEventListener("click", () => {
        const planId = Number(button.getAttribute("data-mobile-edit") || "0");
        const plan = items.find((item) => item.id === planId);
        if (plan) fillEditForm(plan);
      });
    });

    bindDelete("button[data-delete]", "data-delete", loadPlans);
    bindDelete("button[data-mobile-delete]", "data-mobile-delete", loadPlans);
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
          is_hidden: q("new_hidden").checked,
          is_trial: q("new_trial").checked,
        }),
      });
      resetCreateForm();
      await loadPlans();
      showToast("Тариф создан", "success");
    }).catch((err) => alert(err.message));
  });

  q("update_plan").addEventListener("click", async (e) => {
    const id = Number(q("edit_id").value || "0");
    if (!id) return alert("Введите ID тарифа");

    const payload = {
      is_hidden: q("edit_hidden").checked,
      is_trial: q("edit_trial").checked,
    };
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

  q("edit_id").addEventListener("input", () => {
    const id = Number(q("edit_id").value || "0");
    if (!id) return;
    const plan = latestPlans.find((item) => item.id === id);
    if (plan) fillEditForm(plan);
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["new_name", "new_price", "new_days", "new_gb"], "create_plan");
    bindEnterSubmit(["edit_id", "edit_name", "edit_price", "edit_days", "edit_gb"], "update_plan");
    resetCreateForm();
    await loadPlans();
  } catch (e) {
    alert(e.message);
  }
});
