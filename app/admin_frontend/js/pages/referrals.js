const refState = { page: 1, pages: 1 };

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "referrals",
    title: "Реферальная система",
    subtitle: "Аккаунты, проценты и балансы",
    contentHtml: `
      <div class="toolbar">
        <input id="search" type="text" placeholder="Поиск: ID пользователя / Telegram ID / username" />
        <button id="apply" class="btn-primary">Фильтр</button>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Пользователь</th><th>TG</th><th>Username</th><th>Инвайтов</th><th>Баланс</th><th>Процент</th><th>Создан</th><th>Действия</th></tr>
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
      page: String(refState.page),
      page_size: "25",
      search: q("search").value || "",
    });
    const data = await api(`/api/admin/referrals?${params.toString()}`);
    const items = data.items || [];
    const meta = data.meta || { page: 1, pages: 1, total: 0 };
    refState.pages = meta.pages;

    q("tbody").innerHTML = "";
    items.forEach((r) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${r.id}</td>
        <td>${r.user_id}</td>
        <td>${safeText(r.tg_id)}</td>
        <td>${safeText(r.username)}</td>
        <td>${r.invited_count}</td>
        <td>${r.referral_balance} RUB</td>
        <td>${r.referral_percent}%</td>
        <td>${formatDateTime(r.created_at)}</td>
        <td></td>
      `;
      const row = document.createElement("div");
      row.className = "row-actions";

      const p = document.createElement("input");
      p.type = "number";
      p.min = "0";
      p.max = "100";
      p.value = String(r.referral_percent);
      p.title = "Процент";
      p.style.width = "100px";

      const b = document.createElement("input");
      b.type = "number";
      b.min = "0";
      b.value = String(r.referral_balance);
      b.title = "Баланс";
      b.style.width = "120px";

      const save = document.createElement("button");
      save.className = "btn-primary";
      save.textContent = "Сохранить";
      save.addEventListener("click", async (e) => {
        const params = new URLSearchParams({
          referral_percent: p.value,
          referral_balance: b.value,
        });
        await withButtonLoading(e.currentTarget, async () => {
          await api(`/api/admin/referrals/${r.id}?${params.toString()}`, { method: "PATCH" });
          await loadRows();
          showToast("Реферальные данные обновлены", "success");
        }).catch((err) => alert(err.message));
      });

      row.append(p, b, save);
      tr.querySelector("td:last-child").appendChild(row);
      q("tbody").appendChild(tr);
    });

    renderPager(meta, q("prev"), q("next"), q("meta"));
  }

  q("apply").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      refState.page = 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("prev").addEventListener("click", async (e) => {
    if (refState.page <= 1) return;
    await withButtonLoading(e.currentTarget, async () => {
      refState.page -= 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("next").addEventListener("click", async (e) => {
    if (refState.page >= refState.pages) return;
    await withButtonLoading(e.currentTarget, async () => {
      refState.page += 1;
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["search"], "apply");
    await loadRows();
  } catch (e) {
    alert(e.message);
  }
});
