document.addEventListener("DOMContentLoaded", async () => {
  function closePromocodeModal() {
    const modal = q("promocode_modal");
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("user-modal-open");
  }

  function openPromocodeModal() {
    q("new_code").value = "";
    q("new_amount").value = "";
    q("new_usages").value = "1";
    q("promocode_modal").hidden = false;
    document.body.classList.add("user-modal-open");
    setTimeout(() => q("new_code")?.focus(), 0);
  }

  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "promocodes",
    title: "Промокоды",
    subtitle: "Создание, просмотр и удаление промокодов",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <div class="admin-section-head">
            <h3>Список промокодов</h3>
            <div class="toolbar toolbar--compact">
              <button id="reload" type="button">Обновить</button>
              <button id="export_promocodes" type="button">CSV</button>
              <button id="open_create_promocode" class="btn-primary" type="button">Создать</button>
            </div>
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
                </tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
        </div>

        <div id="promocode_modal" class="user-modal admin-form-modal" hidden>
          <button id="promocode_modal_overlay" class="user-modal__overlay" type="button" aria-label="Закрыть окно"></button>
          <div class="user-modal__dialog admin-form-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="promocode_modal_title">
            <div class="user-modal__topbar">
              <div>
                <div class="user-modal__eyebrow">Промокоды</div>
                <h3 id="promocode_modal_title" class="user-modal__title">Создание промокода</h3>
              </div>
              <button id="promocode_modal_close" class="user-modal__close" type="button" aria-label="Закрыть окно">×</button>
            </div>
            <div class="admin-form-modal__body">
              <div class="form-grid">
                <input id="new_code" type="text" placeholder="Код (например, WELCOME500)" />
                <input id="new_amount" type="number" placeholder="Сумма начисления" />
                <input id="new_usages" type="number" placeholder="Количество активаций" value="1" />
              </div>
              <div class="admin-form-modal__actions">
                <button id="create_promocode" class="btn-primary" type="button">Создать</button>
              </div>
            </div>
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
      `;
      tr.classList.add("is-clickable-row");
      tr.addEventListener("click", (event) => {
        event.stopPropagation();
        showRowContextMenu(tr, [
          {
            label: "Удалить",
            className: "row-action-menu__item--danger",
            onClick: async (event, button) => {
              if (!confirm(`Удалить промокод #${promo.id}? Действие необратимо.`)) return;

              await withButtonLoading(button, async () => {
                await api(`/api/admin/promocodes/${promo.id}`, { method: "DELETE" });
                await loadPromocodes();
                showToast("Промокод удален", "success");
              }).catch((err) => alert(err.message));
            },
          },
        ], {
          title: `Промокод #${promo.id}`,
          meta: [
            { label: "Код", value: promo.code },
            { label: "Сумма", value: promo.amount },
            { label: "Осталось", value: promo.usages_left },
            { label: "Использовано", value: promo.used_count },
            { label: "Создан", value: formatDateTime(promo.created_at) },
            { label: "Последняя активация", value: formatDateTime(promo.activated_at) },
          ],
        });
      });
      q("tbody").appendChild(tr);
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
      closePromocodeModal();
      showToast("Промокод создан", "success");
    }).catch((err) => alert(err.message));
  });

  q("reload").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      await loadPromocodes();
    }).catch((err) => alert(err.message));
  });

  q("export_promocodes").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      await downloadAdminFile("/api/admin/export/promocodes", "promocodes.csv");
    }).catch((error) => alert(error.message));
  });

  q("open_create_promocode").addEventListener("click", openPromocodeModal);
  q("promocode_modal_overlay")?.addEventListener("click", closePromocodeModal);
  q("promocode_modal_close")?.addEventListener("click", closePromocodeModal);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePromocodeModal();
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["new_code", "new_amount", "new_usages"], "create_promocode");
    await loadPromocodes();
  } catch (e) {
    alert(e.message);
  }
});
