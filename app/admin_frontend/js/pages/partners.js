const partnerState = { createdUrl: "", expandedPartnerId: null };

function renderPartnerDetails(details) {
  const summary = details.summary || {};
  const users = details.users || [];
  const payments = details.recent_payments || [];

  return `
    <div class="partner-details">
      <div class="partner-details__summary">
        <div><span>Привязано</span><b>${safeText(summary.attributed_users)}</b><small>пользователей</small></div>
        <div><span>С оплатами</span><b>${safeText(summary.paid_users)}</b><small>пользователей</small></div>
        <div><span>Пополнений</span><b>${safeText(summary.paid_topups)}</b><small>всего</small></div>
        <div><span>Сумма</span><b>${safeText(summary.paid_amount)} RUB</b><small>оборот</small></div>
        <div><span>Последняя оплата</span><b>${formatDateTime(summary.last_payment_at)}</b><small>по ссылке</small></div>
      </div>

      <div class="partner-details__grid">
        <div class="partner-details__card">
          <h4>Пользователи по ссылке</h4>
          <div class="partner-details__list">
            ${
              users.length
                ? users
                    .map(
                      (user) => `
                        <div class="partner-details__item">
                          <div class="partner-details__item-main">
                            <b>${safeText(user.username || `User #${user.user_id}`)}</b>
                            <span>ID ${safeText(user.user_id)} · TG ${safeText(user.tg_id)}</span>
                          </div>
                          <div class="partner-details__item-grid">
                            <div><span>Пополнений</span><b>${safeText(user.paid_topups)}</b></div>
                            <div><span>Сумма</span><b>${safeText(user.paid_amount)} RUB</b></div>
                            <div><span>Макс. чек</span><b>${safeText(user.max_paid_amount)} RUB</b></div>
                            <div><span>Пришёл</span><b>${formatDateTime(user.attributed_at)}</b></div>
                            <div class="partner-details__item-wide"><span>Последняя оплата</span><b>${formatDateTime(user.last_paid_at)}</b></div>
                          </div>
                        </div>
                      `,
                    )
                    .join("")
                : "<div class='partner-details__empty'>Нет пользователей по этой ссылке</div>"
            }
          </div>
        </div>

        <div class="partner-details__card">
          <h4>Последние пополнения</h4>
          <div class="partner-details__list">
            ${
              payments.length
                ? payments
                    .map(
                      (payment) => `
                        <div class="partner-details__item partner-details__item--payment">
                          <div class="partner-details__item-main">
                            <b>${safeText(payment.amount)} RUB</b>
                            <span>${safeText(payment.payment_system || "—")} · ${formatDateTime(payment.paid_at)}</span>
                          </div>
                          <div class="partner-details__item-grid">
                            <div><span>TX</span><b>${safeText(payment.transaction_id)}</b></div>
                            <div><span>User ID</span><b>${safeText(payment.user_id)}</b></div>
                            <div><span>Telegram</span><b>${safeText(payment.tg_id)}</b></div>
                            <div><span>Username</span><b>${safeText(payment.username || "—")}</b></div>
                          </div>
                        </div>
                      `,
                    )
                    .join("")
                : "<div class='partner-details__empty'>Нет оплаченных пополнений</div>"
            }
          </div>
        </div>
      </div>
    </div>
  `;
}

async function togglePartnerDetails(item, hostRow, triggerBtn) {
  const alreadyOpen = hostRow.dataset.open === "1";

  document.querySelectorAll(".partner-details-row").forEach((row) => {
    row.dataset.open = "0";
    row.style.display = "none";
  });
  document.querySelectorAll(".js-partner-details").forEach((btn) => {
    btn.textContent = "Детали";
    btn.classList.remove("is-active");
  });

  if (alreadyOpen) {
    partnerState.expandedPartnerId = null;
    return;
  }

  await withButtonLoading(triggerBtn, async () => {
    const data = await api(`/api/admin/partners/${item.id}/details`);
    const detailsCell = hostRow.querySelector("td");
    detailsCell.innerHTML = renderPartnerDetails(data);
    hostRow.style.display = "";
    hostRow.dataset.open = "1";
    triggerBtn.textContent = "Скрыть";
    triggerBtn.classList.add("is-active");
    partnerState.expandedPartnerId = item.id;
  }).catch((error) => alert(error.message));
}

document.addEventListener("DOMContentLoaded", async () => {
  function closePartnerModal() {
    const modal = q("partner_modal");
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("user-modal-open");
  }

  function openPartnerModal() {
    q("partner_name").value = "";
    q("partner_code").value = "";
    const created = q("created_link");
    if (created) {
      created.style.display = "none";
      created.innerHTML = "";
    }
    q("partner_modal").hidden = false;
    document.body.classList.add("user-modal-open");
    setTimeout(() => q("partner_name")?.focus(), 0);
  }

  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "partners",
    title: "Партнёрская система",
    subtitle: "Создание ссылок и статистика по новым пользователям и пополнениям",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <div class="admin-section-head">
            <h3>Ссылки</h3>
            <div class="toolbar toolbar--compact">
              <button id="reload_partners" type="button">Обновить</button>
              <button id="open_create_partner" class="btn-primary" type="button">Создать ссылку</button>
            </div>
          </div>
          <div class="toolbar">
            <input id="search" type="text" placeholder="Поиск по названию или коду" />
            <button id="apply" class="btn-primary">Фильтр</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Название</th>
                  <th>Код</th>
                  <th>Ссылка</th>
                  <th>Новые пользователи</th>
                  <th>Оплаченные пополнения</th>
                  <th>Сумма пополнений</th>
                  <th>Статус</th>
                  <th>Создана</th>
                </tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
        </div>

        <div id="partner_modal" class="user-modal admin-form-modal" hidden>
          <button id="partner_modal_overlay" class="user-modal__overlay" type="button" aria-label="Закрыть окно"></button>
          <div class="user-modal__dialog admin-form-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="partner_modal_title">
            <div class="user-modal__topbar">
              <div>
                <div class="user-modal__eyebrow">Партнёрская система</div>
                <h3 id="partner_modal_title" class="user-modal__title">Создание ссылки</h3>
              </div>
              <button id="partner_modal_close" class="user-modal__close" type="button" aria-label="Закрыть окно">×</button>
            </div>
            <div class="admin-form-modal__body">
              <div class="form-grid">
                <input id="partner_name" type="text" placeholder="Название партнёра" />
                <input id="partner_code" type="text" placeholder="Код ссылки (необязательно)" />
              </div>
              <div id="created_link" class="summary-list" style="display:none;"></div>
              <div class="admin-form-modal__actions">
                <button id="create_partner" class="btn-primary" type="button">Создать</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `,
  });

  async function loadPartners() {
    const params = new URLSearchParams({ search: q("search").value || "" });
    const data = await api(`/api/admin/partners?${params.toString()}`);
    const items = data.items || [];
    const tbody = q("tbody");
    tbody.innerHTML = "";

    items.forEach((item) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${safeText(item.id)}</td>
        <td>${safeText(item.name)}</td>
        <td><span class="mono">${safeText(item.code)}</span></td>
        <td><span class="mono">${safeText(item.url)}</span></td>
        <td>${safeText(item.new_users)}</td>
        <td>${safeText(item.paid_topups)}</td>
        <td>${safeText(item.paid_amount)} RUB</td>
        <td>${item.is_active ? statusBadge("active") : statusBadge("disabled")}</td>
        <td>${formatDateTime(item.created_at)}</td>
      `;
      const detailsTr = document.createElement("tr");
      detailsTr.className = "partner-details-row";
      detailsTr.style.display = "none";
      detailsTr.dataset.open = "0";
      detailsTr.innerHTML = `<td colspan="9"></td>`;

      tr.classList.add("is-clickable-row");
      tr.addEventListener("click", (event) => {
        event.stopPropagation();
        showRowContextMenu(tr, [
          {
            label: "Копировать ссылку",
            onClick: async () => {
              await navigator.clipboard.writeText(item.url);
              showToast("Ссылка скопирована", "success");
            },
          },
          {
            label: detailsTr.dataset.open === "1" ? "Скрыть детали" : "Детали",
            onClick: async (event, button) => {
              await togglePartnerDetails(item, detailsTr, button);
            },
          },
          {
            label: item.is_active ? "Выключить" : "Включить",
            className: item.is_active ? "row-action-menu__item--danger" : "row-action-menu__item--success",
            onClick: async (event, button) => {
              await withButtonLoading(button, async () => {
                await api(`/api/admin/partners/${item.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({ is_active: !item.is_active }),
                });
                await loadPartners();
              }).catch((error) => alert(error.message));
            },
          },
        ], {
          title: `Партнер #${item.id}`,
          meta: [
            { label: "Название", value: item.name },
            { label: "Код", value: item.code },
            { label: "Ссылка", value: item.url },
            { label: "Новые пользователи", value: item.new_users },
            { label: "Оплаченные пополнения", value: item.paid_topups },
            { label: "Сумма", value: `${item.paid_amount} RUB` },
            { label: "Статус", html: item.is_active ? statusBadge("active") : statusBadge("disabled") },
            { label: "Создана", value: formatDateTime(item.created_at) },
          ],
        });
      });
      tbody.appendChild(tr);
      tbody.appendChild(detailsTr);

      if (partnerState.expandedPartnerId === item.id) {
        togglePartnerDetails(item, detailsTr, document.createElement("button"));
      }
    });
  }

  q("create_partner").addEventListener("click", async (event) => {
    const payload = {
      name: q("partner_name").value.trim(),
      code: q("partner_code").value.trim() || null,
    };

    await withButtonLoading(event.currentTarget, async () => {
      const data = await api("/api/admin/partners", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      partnerState.createdUrl = data.item?.url || "";
      q("partner_name").value = "";
      q("partner_code").value = "";
      const created = q("created_link");
      if (created) {
        created.style.display = "grid";
        created.innerHTML = `
          <div><span>Ссылка создана</span><b class="mono">${safeText(partnerState.createdUrl)}</b></div>
          <div><span>Код</span><b class="mono">${safeText(data.item?.code)}</b></div>
        `;
      }
      await loadPartners();
      showToast("Партнёрская ссылка создана", "success");
    }).catch((error) => alert(error.message));
  });

  q("reload_partners").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      await loadPartners();
    }).catch((error) => alert(error.message));
  });

  q("apply").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      await loadPartners();
    }).catch((error) => alert(error.message));
  });

  q("open_create_partner").addEventListener("click", openPartnerModal);
  q("partner_modal_overlay")?.addEventListener("click", closePartnerModal);
  q("partner_modal_close")?.addEventListener("click", closePartnerModal);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePartnerModal();
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["partner_name", "partner_code"], "create_partner");
    bindEnterSubmit(["search"], "apply");
    await loadPartners();
  } catch (error) {
    alert(error.message);
  }
});
