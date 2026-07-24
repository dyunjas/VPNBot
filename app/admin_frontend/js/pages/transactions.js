const txState = { page: 1, pages: 1, sortBy: "created_at", sortDir: "desc" };

function renderTransactionsTableHead() {
  const thead = document.querySelector(".transactions-table thead");
  if (!thead) return;
  thead.innerHTML = `
    <tr>
      ${sortableTh("ID", "id", txState.sortBy, txState.sortDir)}
      <th>Пользователь</th>
      <th>TG</th>
      <th>Username</th>
      <th>Provider ID</th>
      ${sortableTh("Сумма", "amount", txState.sortBy, txState.sortDir)}
      <th>Система</th>
      <th>Статус</th>
      ${sortableTh("Создана", "created_at", txState.sortBy, txState.sortDir)}
      ${sortableTh("Оплачена", "paid_at", txState.sortBy, txState.sortDir)}
    </tr>
  `;
  bindSortableTable(thead, txState, async (button) => {
    await withButtonLoading(button, loadRows).catch((error) => alert(error.message));
  });
}

async function confirmPayment(id, button, amount, providerId) {
  const providerLabel = String(providerId || id);
  if (!confirm(`Подтвердить платеж на ${amount} RUB?\n\nProvider ID: ${providerLabel}\nСумма будет зачислена пользователю на баланс.`)) {
    return;
  }

  await withButtonLoading(button, async () => {
    const result = await api(`/api/admin/transactions/${id}/confirm`, { method: "POST" });
    await loadRows();
    showToast(
      result.already_paid ? "Платеж уже был подтвержден" : `Платеж подтвержден, баланс: ${result.balance} RUB`,
      "success",
    );
  }).catch((error) => alert(error.message));
}

async function loadRows() {
  const tbody = q("tbody");
  setTableRefreshing(tbody, true);
  const params = new URLSearchParams({
    page: String(txState.page),
    page_size: "30",
    paid: q("paid").value,
    payment_system: q("payment_system").value || "",
    search: q("search").value || "",
    sort_by: txState.sortBy,
    sort_dir: txState.sortDir,
  });

  try {
    const data = await api(`/api/admin/transactions?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    txState.pages = meta.pages;

    renderTransactionsTableHead();
    tbody.innerHTML = "";
    items.forEach((transaction) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${safeText(transaction.id)}</td>
        <td>${safeText(transaction.user_id)}</td>
        <td>${safeText(transaction.tg_id)}</td>
        <td>${safeText(transaction.username || "—")}</td>
        <td class="mono">${safeText(transaction.transaction_id)}</td>
        <td><span class="money-cell">${safeText(transaction.amount)} RUB</span></td>
        <td>${safeText(transaction.payment_system)}</td>
        <td>${statusBadge(transaction.paid ? "paid" : "unpaid")}</td>
        <td>${formatDateTime(transaction.created_at)}</td>
        <td>${formatDateTime(transaction.paid_at)}</td>
      `;

      if (!transaction.paid) {
        tr.classList.add("is-clickable-row");
        tr.addEventListener("click", (event) => {
          event.stopPropagation();
          showRowContextMenu(tr, [
            {
              label: "Подтвердить платеж",
              className: "row-action-menu__item--success",
              onClick: (event, button) =>
                confirmPayment(transaction.id, button, transaction.amount, transaction.transaction_id),
            },
          ], {
            title: `Транзакция #${transaction.id}`,
            meta: [
              { label: "Пользователь", value: transaction.user_id },
              { label: "Telegram", value: transaction.tg_id || "—" },
              { label: "Username", value: transaction.username || "—" },
              { label: "Provider ID", value: transaction.transaction_id || "—" },
              { label: "Сумма", value: `${transaction.amount} RUB` },
              { label: "Система", value: transaction.payment_system || "—" },
              { label: "Статус", html: statusBadge(transaction.paid ? "paid" : "unpaid") },
              { label: "Создана", value: formatDateTime(transaction.created_at) },
            ],
          });
        });
      }

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
          <table class="transactions-table">
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
    `,
  });

  q("apply").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      txState.page = 1;
      await loadRows();
    }).catch((error) => alert(error.message));
  });

  q("prev").addEventListener("click", async (event) => {
    if (txState.page <= 1) return;
    await withButtonLoading(event.currentTarget, async () => {
      txState.page -= 1;
      await loadRows();
    }).catch((error) => alert(error.message));
  });

  q("next").addEventListener("click", async (event) => {
    if (txState.page >= txState.pages) return;
    await withButtonLoading(event.currentTarget, async () => {
      txState.page += 1;
      await loadRows();
    }).catch((error) => alert(error.message));
  });

  try {
    await renderSessionInfo();
    renderTransactionsTableHead();
    bindEnterSubmit(["search", "payment_system"], "apply");
    await loadRows();
  } catch (error) {
    alert(error.message);
  }
});
