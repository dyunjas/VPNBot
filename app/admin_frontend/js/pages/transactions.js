const txState = { page: 1, pages: 1 };

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
          <table>
            <thead>
              <tr>
                <th>ID</th><th>Пользователь</th><th>TG</th><th>Username</th><th>Provider ID</th><th>Сумма</th><th>Система</th><th>Статус</th><th>Создана</th><th>Оплачена</th><th class="tx-actions-head">Действия</th>
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
    const params = new URLSearchParams({
      page: String(txState.page),
      page_size: "30",
      paid: q("paid").value,
      payment_system: q("payment_system").value || "",
      search: q("search").value || "",
    });

    const data = await api(`/api/admin/transactions?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    txState.pages = meta.pages;

    q("tbody").innerHTML = "";
    items.forEach((transaction) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${safeText(transaction.id)}</td>
        <td>${safeText(transaction.user_id)}</td>
        <td>${safeText(transaction.tg_id)}</td>
        <td>${safeText(transaction.username)}</td>
        <td>${safeText(transaction.transaction_id)}</td>
        <td>${safeText(transaction.amount)} RUB</td>
        <td>${safeText(transaction.payment_system)}</td>
        <td>${statusBadge(transaction.paid ? "paid" : "unpaid")}</td>
        <td>${formatDateTime(transaction.created_at)}</td>
        <td>${formatDateTime(transaction.paid_at)}</td>
        <td class="tx-actions-cell"><div class="row-actions tx-actions-wrap"></div></td>
      `;

      const actions = tr.querySelector(".tx-actions-wrap");
      if (!transaction.paid) {
        const button = document.createElement("button");
        button.className = "btn-primary tx-confirm-btn";
        button.textContent = "Подтвердить";
        button.addEventListener("click", () =>
          confirmPayment(transaction.id, button, transaction.amount, transaction.transaction_id)
        );
        actions.appendChild(button);
      } else {
        actions.textContent = "—";
      }

      q("tbody").appendChild(tr);
    });

    renderPager(meta, q("prev"), q("next"), q("meta"));
  }

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
    bindEnterSubmit(["search", "payment_system"], "apply");
    await loadRows();
  } catch (error) {
    alert(error.message);
  }
});
