const subState = { page: 1, pages: 1 };

document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
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
          </div>
        </div>

        <div class="content-grid subscriptions-grid">
          <div class="card">
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th><th>Пользователь</th><th>Telegram</th><th>Тариф</th><th>Статус</th><th>Авто</th><th>Окончание</th><th>Действия</th>
                </tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
          <div class="pager">
            <button id="prev">Назад</button>
            <span id="meta"></span>
            <button id="next">Вперед</button>
          </div>
          </div>

          <div class="content-stack">
            <div class="card">
              <h3>Массовое продление</h3>
              <div class="section-title">Продлевает срок в панели и в локальной базе, затем рассылает уведомления в Telegram.</div>
              <div class="form-grid" style="margin-top:10px">
                <select id="bulk_target">
                  <option value="all">Все подписки</option>
                  <option value="active">Только активные</option>
                  <option value="inactive">Только неактивные</option>
                </select>
                <input id="bulk_days" type="number" min="1" step="1" placeholder="На сколько дней продлить" />
              </div>
              <div class="toolbar" style="margin-top:10px">
                <button id="bulk_extend" class="btn-primary">Продлить выбранным</button>
              </div>
            </div>

            <div class="card">
              <h3>Создать подписку</h3>
              <div class="form-grid">
                <input id="new_user_id" type="number" placeholder="ID пользователя" />
                <input id="new_plan_id" type="number" placeholder="ID тарифа" />
              </div>
              <div class="toolbar" style="margin-top:10px">
                <label class="inline-field"><input id="new_auto" type="checkbox" /> Автопродление</label>
                <button id="create_sub" class="btn-primary">Создать</button>
              </div>
            </div>

            <div class="card">
              <h3>Редактирование подписки</h3>
              <div class="toolbar">
                <input id="edit_sub_id" type="number" placeholder="ID подписки" />
                <input id="edit_plan_id" type="number" placeholder="ID тарифа (опционально)" />
                <select id="edit_status">
                  <option value="">Статус (опционально)</option>
                  <option value="active">Активна</option>
                  <option value="past_due">Просрочена</option>
                  <option value="expired">Истекла</option>
                  <option value="canceled">Отменена</option>
                </select>
                <input id="edit_extend_days" type="number" placeholder="Продлить на дней" />
                <button id="update_sub">Сохранить</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `,
  });

  async function loadRows() {
    const params = new URLSearchParams({
      page: String(subState.page),
      page_size: "25",
      search: q("search").value || "",
      status: q("status").value,
    });
    const data = await api(`/admin-api/subscriptions?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    subState.pages = meta.pages;

    q("tbody").innerHTML = "";
    items.forEach((s) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${s.id}</td>
        <td>${s.user_id}</td>
        <td>${s.tg_id || ""}</td>
        <td>${s.plan_name || s.plan_id}</td>
        <td>${statusBadge(s.status)}</td>
        <td>${s.auto_renew ? "Да" : "Нет"}</td>
        <td>${formatDateTime(s.current_period_end)}</td>
        <td class="row-actions">
          <button data-edit="${s.id}">Изменить</button>
          <button class="btn-danger" data-delete="${s.id}">Удалить</button>
        </td>
      `;
      q("tbody").appendChild(tr);
    });

    q("tbody").querySelectorAll("button[data-edit]").forEach((b) => {
      b.addEventListener("click", () => {
        q("edit_sub_id").value = b.getAttribute("data-edit");
      });
    });

    q("tbody").querySelectorAll("button[data-delete]").forEach((b) => {
      b.addEventListener("click", async (e) => {
        const subId = Number(b.getAttribute("data-delete") || "0");
        if (!subId) return;
        if (!confirm(`Удалить подписку #${subId}? Действие необратимо.`)) return;

        await withButtonLoading(e.currentTarget, async () => {
          await api(`/admin-api/subscriptions/${subId}`, { method: "DELETE" });
          await loadRows();
          showToast("Подписка удалена", "success");
        }).catch((err) => alert(err.message));
      });
    });

    renderPager(meta, q("prev"), q("next"), q("meta"));
  }

  q("apply").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      subState.page = 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("prev").addEventListener("click", async (e) => {
    if (subState.page <= 1) return;
    await withButtonLoading(e.currentTarget, async () => {
      subState.page -= 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("next").addEventListener("click", async (e) => {
    if (subState.page >= subState.pages) return;
    await withButtonLoading(e.currentTarget, async () => {
      subState.page += 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("create_sub").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      await api("/admin-api/subscriptions", {
        method: "POST",
        body: JSON.stringify({
          user_id: Number(q("new_user_id").value),
          plan_id: Number(q("new_plan_id").value),
          auto_renew: q("new_auto").checked,
        }),
      });
      await loadRows();
      showToast("Подписка создана", "success");
    }).catch((err) => alert(err.message));
  });

  q("update_sub").addEventListener("click", async (e) => {
    const id = Number(q("edit_sub_id").value || "0");
    if (!id) return alert("Введите ID подписки");

    const payload = {};
    if (q("edit_plan_id").value) payload.plan_id = Number(q("edit_plan_id").value);
    if (q("edit_status").value) payload.status = q("edit_status").value;
    if (q("edit_extend_days").value) payload.extend_days = Number(q("edit_extend_days").value);

    await withButtonLoading(e.currentTarget, async () => {
      await api(`/admin-api/subscriptions/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadRows();
      showToast("Подписка обновлена", "success");
    }).catch((err) => alert(err.message));
  });

  q("bulk_extend").addEventListener("click", async (e) => {
    const days = Number(q("bulk_days").value || "0");
    const target = q("bulk_target").value || "all";
    if (!days || days < 1) return alert("Введите количество дней");

    const targetLabel = {
      all: "всем пользователям с подписками",
      active: "пользователям с активной подпиской",
      inactive: "пользователям с неактивной подпиской",
    }[target] || "выбранной группе";

    if (!confirm(`Продлить подписку на ${days} дн. ${targetLabel}?`)) return;

    await withButtonLoading(e.currentTarget, async () => {
      const result = await api("/admin-api/subscriptions/bulk-extend", {
        method: "POST",
        body: JSON.stringify({ target, days }),
      });
      await loadRows();
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
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["search"], "apply");
    bindEnterSubmit(["bulk_days"], "bulk_extend");
    bindEnterSubmit(["new_user_id", "new_plan_id"], "create_sub");
    bindEnterSubmit(["edit_sub_id", "edit_plan_id", "edit_extend_days"], "update_sub");
    await loadRows();
  } catch (e) {
    alert(e.message);
  }
});
