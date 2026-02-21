const txState = { page: 1, pages: 1 };

document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
  renderShell({
    activeKey: "transactions",
    title: "Транзакции",
    subtitle: "Журнал оплат и пополнений",
    contentHtml: `
      <div class="toolbar">
        <input id="search" type="text" placeholder="Поиск: ID / Provider ID / Telegram / username" />
        <select id="paid">
          <option value="all">Все</option>
          <option value="paid">Оплаченные</option>
          <option value="unpaid">Неоплаченные</option>
        </select>
        <input id="payment_system" type="text" placeholder="Платежная система" />
        <button id="apply" class="btn-primary">Фильтр</button>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Пользователь</th><th>TG</th><th>Username</th><th>Provider ID</th><th>Сумма</th><th>Система</th><th>Статус</th><th>Создана</th><th>Оплачена</th>
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
    `,
  });

  async function loadRows() {
    const params = new URLSearchParams({
      page: String(txState.page),
      page_size: "30",
      paid: q("paid").value,
      payment_system: q("payment_system").value || "",
      search: q("search").value || "",
    });
    const data = await api(`/admin-api/transactions?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    txState.pages = meta.pages;

    q("tbody").innerHTML = "";
    items.forEach((t) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${t.id}</td>
        <td>${t.user_id}</td>
        <td>${safeText(t.tg_id)}</td>
        <td>${safeText(t.username)}</td>
        <td>${safeText(t.transaction_id)}</td>
        <td>${safeText(t.amount)} RUB</td>
        <td>${safeText(t.payment_system)}</td>
        <td>${statusBadge(t.paid ? "paid" : "unpaid")}</td>
        <td>${formatDateTime(t.created_at)}</td>
        <td>${formatDateTime(t.paid_at)}</td>
      `;
      q("tbody").appendChild(tr);
    });

    renderPager(meta, q("prev"), q("next"), q("meta"));
  }

  q("apply").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      txState.page = 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("prev").addEventListener("click", async (e) => {
    if (txState.page <= 1) return;
    await withButtonLoading(e.currentTarget, async () => {
      txState.page -= 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("next").addEventListener("click", async (e) => {
    if (txState.page >= txState.pages) return;
    await withButtonLoading(e.currentTarget, async () => {
      txState.page += 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["search", "payment_system"], "apply");
    await loadRows();
  } catch (e) {
    alert(e.message);
  }
});
