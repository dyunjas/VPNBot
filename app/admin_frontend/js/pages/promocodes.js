document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "promocodes",
    title: "Промокоды",
    subtitle: "Создание, просмотр и удаление промокодов",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <h3>Список промокодов</h3>
          <div class="toolbar">
            <button id="reload" class="btn-primary">Обновить</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Код</th>
                  <th>Сумма</th>
                  <th>Осталось активаций</th>
                  <th>Использовано</th>
                  <th>Создан</th>
                  <th>Последняя активация</th>
                  <th>Действие</th>
                </tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
        </div>

        <div class="card">
          <h3>Создать промокод</h3>
          <div class="form-grid">
            <input id="new_code" type="text" placeholder="Код (например, WELCOME500)" />
            <input id="new_amount" type="number" placeholder="Сумма начисления" />
            <input id="new_usages" type="number" placeholder="Количество активаций" value="1" />
          </div>
          <div class="toolbar" style="margin-top:10px">
            <button id="create_promocode" class="btn-primary">Создать</button>
          </div>
        </div>
      </div>
    `,
  });

  async function loadPromocodes() {
    const data = await api("/api/admin/promocodes");
    const items = data.items || [];
    q("tbody").innerHTML = "";

    items.forEach((promo) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${promo.id}</td>
        <td>${safeText(promo.code)}</td>
        <td>${safeText(promo.amount)}</td>
        <td>${safeText(promo.usages_left)}</td>
        <td>${safeText(promo.used_count)}</td>
        <td>${formatDateTime(promo.created_at)}</td>
        <td>${formatDateTime(promo.activated_at)}</td>
        <td class="row-actions">
          <button class="btn-danger" data-delete="${promo.id}">Удалить</button>
        </td>
      `;
      q("tbody").appendChild(tr);
    });

    q("tbody").querySelectorAll("button[data-delete]").forEach((b) => {
      b.addEventListener("click", async (e) => {
        const promocodeId = Number(b.getAttribute("data-delete") || "0");
        if (!promocodeId) return;
        if (!confirm(`Удалить промокод #${promocodeId}? Действие необратимо.`)) return;

        await withButtonLoading(e.currentTarget, async () => {
          await api(`/api/admin/promocodes/${promocodeId}`, { method: "DELETE" });
          await loadPromocodes();
          showToast("Промокод удален", "success");
        }).catch((err) => alert(err.message));
      });
    });
  }

  q("create_promocode").addEventListener("click", async (e) => {
    const payload = {
      code: q("new_code").value.trim(),
      amount: Number(q("new_amount").value),
      usages: Number(q("new_usages").value || "1"),
    };

    await withButtonLoading(e.currentTarget, async () => {
      await api("/api/admin/promocodes", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      q("new_code").value = "";
      q("new_amount").value = "";
      q("new_usages").value = "1";
      await loadPromocodes();
      showToast("Промокод создан", "success");
    }).catch((err) => alert(err.message));
  });

  q("reload").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      await loadPromocodes();
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["new_code", "new_amount", "new_usages"], "create_promocode");
    await loadPromocodes();
  } catch (e) {
    alert(e.message);
  }
});
