const wdState = { page: 1, pages: 1 };

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "withdrawals",
    title: "Заявки на вывод",
    subtitle: "Просмотр и обработка заявок пользователей",
    contentHtml: `
      <div class="toolbar">
        <select id="status">
          <option value="all">Все статусы</option>
          <option value="pending">На проверке</option>
          <option value="approved">Подтвержденные</option>
          <option value="rejected">Отклоненные</option>
        </select>
        <button id="apply" class="btn-primary">Фильтр</button>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Пользователь</th><th>TG</th><th>Username</th><th>Сумма</th><th>Метод</th><th>Статус</th><th>Дата</th></tr>
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
    `,
  });

  async function loadRows() {
    const params = new URLSearchParams({
      page: String(wdState.page),
      page_size: "25",
      status: q("status").value,
    });
    const data = await api(`/api/admin/withdrawals?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    wdState.pages = meta.pages;

    q("tbody").innerHTML = "";
    items.forEach((w) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${w.id}</td>
        <td>${w.user_id}</td>
        <td>${safeText(w.tg_id)}</td>
        <td>${safeText(w.username)}</td>
        <td>${w.amount} RUB</td>
        <td>${safeText(w.method)}</td>
        <td>${statusBadge(w.status)}</td>
        <td>${formatDateTime(w.created_at)}</td>
      `;
      if (w.status === "pending") {
        tr.classList.add("is-clickable-row");
        tr.addEventListener("click", (event) => {
          event.stopPropagation();
          showRowContextMenu(tr, [
            {
              label: "Подтвердить",
              className: "row-action-menu__item--success",
              onClick: async (event, button) => {
                await withButtonLoading(button, async () => {
                  await api(`/api/admin/withdrawals/${w.id}/approve`, { method: "POST" });
                  await loadRows();
                  showToast(`Заявка #${w.id} подтверждена`, "success");
                }).catch((err) => alert(err.message));
              },
            },
            {
              label: "Отклонить",
              className: "row-action-menu__item--danger",
              onClick: async (event, button) => {
                await withButtonLoading(button, async () => {
                  await api(`/api/admin/withdrawals/${w.id}/reject`, { method: "POST" });
                  await loadRows();
                  showToast(`Заявка #${w.id} отклонена`, "success");
                }).catch((err) => alert(err.message));
              },
            },
          ], {
            title: `Заявка #${w.id}`,
            meta: [
              { label: "Пользователь", value: w.user_id },
              { label: "Telegram", value: w.tg_id || "—" },
              { label: "Username", value: w.username || "—" },
              { label: "Сумма", value: `${w.amount} RUB` },
              { label: "Метод", value: w.method },
              { label: "Статус", html: statusBadge(w.status) },
              { label: "Дата", value: formatDateTime(w.created_at) },
            ],
          });
        });
      }
      q("tbody").appendChild(tr);
    });

    renderPager(meta, q("prev"), q("next"), q("meta"));
  }

  q("apply").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      wdState.page = 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("prev").addEventListener("click", async (e) => {
    if (wdState.page <= 1) return;
    await withButtonLoading(e.currentTarget, async () => {
      wdState.page -= 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("next").addEventListener("click", async (e) => {
    if (wdState.page >= wdState.pages) return;
    await withButtonLoading(e.currentTarget, async () => {
      wdState.page += 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    await loadRows();
  } catch (e) {
    alert(e.message);
  }
});
