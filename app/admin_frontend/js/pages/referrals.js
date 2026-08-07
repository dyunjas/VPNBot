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
        <button id="export_referrals" type="button">CSV</button>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr><th>ID</th><th>Пользователь</th><th>TG</th><th>Username</th><th>Инвайтов</th><th>Баланс</th><th>Процент</th><th>Создан</th></tr>
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
      `;
      tr.classList.add("is-clickable-row");
      tr.addEventListener("click", (event) => {
        event.stopPropagation();
        showRowContextMenu(tr, [], {
          title: `Реферал #${r.id}`,
          className: "row-context-menu--form",
          meta: [
            { label: "Пользователь", value: r.user_id },
            { label: "Telegram", value: r.tg_id || "—" },
            { label: "Username", value: r.username || "—" },
            { label: "Инвайтов", value: r.invited_count },
            { label: "Баланс", value: `${r.referral_balance} RUB` },
            { label: "Процент", value: `${r.referral_percent}%` },
            { label: "Создан", value: formatDateTime(r.created_at) },
          ],
          render: (menu) => {
            const p = document.createElement("input");
            p.type = "number";
            p.min = "0";
            p.max = "100";
            p.value = String(r.referral_percent);
            p.placeholder = "Процент";

            const b = document.createElement("input");
            b.type = "number";
            b.min = "0";
            b.value = String(r.referral_balance);
            b.placeholder = "Баланс";

            const save = createRowContextButton("Сохранить", "row-action-menu__item--success", async (event, button) => {
              const params = new URLSearchParams({
                referral_percent: p.value,
                referral_balance: b.value,
              });
              await withButtonLoading(button, async () => {
                await api(`/api/admin/referrals/${r.id}?${params.toString()}`, { method: "PATCH" });
                await loadRows();
                showToast("Реферальные данные обновлены", "success");
              }).catch((err) => alert(err.message));
            });

            menu.append(p, b, save);
            setTimeout(() => p.focus(), 0);
          },
        });
      });
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

  q("export_referrals").addEventListener("click", async (event) => {
    const params = new URLSearchParams({ search: q("search").value || "" });
    await withButtonLoading(event.currentTarget, async () => {
      await downloadAdminFile(`/api/admin/export/referrals?${params.toString()}`, "referrals.csv");
    }).catch((error) => alert(error.message));
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
