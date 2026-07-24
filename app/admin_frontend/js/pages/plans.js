document.addEventListener("DOMContentLoaded", async () => {
  let latestPlans = [];

  function moveIcon(direction) {
    if (direction === "up") {
      return `<svg viewBox="0 0 24 24" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M12 5l0 14" /><path d="M16 9l-4 -4" /><path d="M8 9l4 -4" /></svg>`;
    }
    return `<svg viewBox="0 0 24 24" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M12 5l0 14" /><path d="M16 15l-4 4" /><path d="M8 15l4 4" /></svg>`;
  }

  function closePlanModal() {
    const modal = q("plan_modal");
    if (!modal) return;
    modal.hidden = true;
    document.body.classList.remove("user-modal-open");
  }

  function openPlanModal(mode) {
    const modal = q("plan_modal");
    if (!modal) return;
    const isEdit = mode === "edit";
    q("plan_modal_title").textContent = isEdit ? "Редактирование тарифа" : "Создание тарифа";
    q("plan_create_form").hidden = isEdit;
    q("plan_edit_form").hidden = !isEdit;
    modal.hidden = false;
    modal.scrollTop = 0;
    modal.querySelector(".user-modal__dialog")?.scrollTo({ top: 0, left: 0 });
    document.body.classList.add("user-modal-open");
    setTimeout(() => q(isEdit ? "edit_name" : "new_name")?.focus(), 0);
  }

  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "plans",
    title: "Тарифы",
    subtitle: "Настройка планов подписок",
    contentHtml: `
      <div class="page-shell">
        <div class="card">
          <div class="admin-section-head">
            <h3>Список тарифов</h3>
            <button id="open_create_plan" class="btn-primary" type="button">Создать тариф</button>
          </div>
          <div id="plans_mobile_list" class="plans-mobile-list"></div>
          <div class="table-wrap plans-table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>Порядок</th><th>Название</th><th>Статус</th><th>Цена</th><th>Дней</th><th>Лимит ГБ</th><th>Лимит устройств</th><th>Лимит пользователей</th><th>Подписок</th></tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
        </div>

        <div id="plan_modal" class="user-modal admin-form-modal" hidden>
          <button id="plan_modal_overlay" class="user-modal__overlay" type="button" aria-label="Закрыть окно"></button>
          <div class="user-modal__dialog admin-form-modal__dialog" role="dialog" aria-modal="true" aria-labelledby="plan_modal_title">
            <div class="user-modal__topbar">
              <div>
                <div class="user-modal__eyebrow">Тарифы</div>
                <h3 id="plan_modal_title" class="user-modal__title">Создание тарифа</h3>
              </div>
              <button id="plan_modal_close" class="user-modal__close" type="button" aria-label="Закрыть окно">×</button>
            </div>

            <div id="plan_create_form" class="admin-form-modal__body">
              <div class="form-grid">
                <input id="new_name" type="text" placeholder="Название тарифа" />
                <input id="new_price" type="number" placeholder="Цена, RUB" />
                <input id="new_days" type="number" placeholder="Период, дней" value="30" />
                <input id="new_gb" type="number" placeholder="Лимит трафика, ГБ" value="100" />
                <input id="new_device_limit" type="number" placeholder="Лимит устройств" value="3" />
                <input id="new_purchase_limit" type="number" placeholder="Лимит пользователей, 0 = без лимита" value="0" />
              </div>
              <div class="plans-flags">
                <label class="plans-flag"><input id="new_hidden" type="checkbox" /> <span>Скрыть от пользователей</span></label>
                <label class="plans-flag"><input id="new_trial" type="checkbox" /> <span>Trial для новых пользователей</span></label>
              </div>
              <div class="admin-form-modal__actions">
                <button id="create_plan" class="btn-primary" type="button">Создать</button>
              </div>
            </div>

            <div id="plan_edit_form" class="admin-form-modal__body" hidden>
              <div class="form-grid">
                <input id="edit_id" type="number" placeholder="ID тарифа" />
                <input id="edit_name" type="text" placeholder="Название" />
                <input id="edit_price" type="number" placeholder="Цена" />
                <input id="edit_days" type="number" placeholder="Период, дней" />
                <input id="edit_gb" type="number" placeholder="Лимит ГБ" />
                <input id="edit_device_limit" type="number" placeholder="Лимит устройств" />
                <input id="edit_purchase_limit" type="number" placeholder="Лимит пользователей, 0 = без лимита" />
              </div>
              <div class="plans-flags">
                <label class="plans-flag"><input id="edit_hidden" type="checkbox" /> <span>Скрыть от пользователей</span></label>
                <label class="plans-flag"><input id="edit_trial" type="checkbox" /> <span>Trial для новых пользователей</span></label>
              </div>
              <div class="admin-form-modal__actions">
                <button id="update_plan" type="button">Сохранить</button>
              </div>
            </div>
          </div>
        </div>
      </div>
    `,
  });

  function planBadges(plan) {
    const badges = [];
    badges.push(plan.is_hidden ? `<span class="badge warn">Скрыт</span>` : `<span class="badge ok">Виден</span>`);
    if (plan.is_trial) badges.push(`<span class="badge">Trial</span>`);
    if (Number(plan.purchase_limit || 0) > 0) {
      badges.push(`<span class="badge warn">Лимит ${plan.purchase_limit}</span>`);
    }
    if (plan.is_exhausted) {
      badges.push(`<span class="badge danger">Лимит достигнут</span>`);
    }
    return badges.join(" ");
  }

  function resetCreateForm() {
    q("new_name").value = "";
    q("new_price").value = "";
    q("new_days").value = "30";
    q("new_gb").value = "100";
    q("new_device_limit").value = "3";
    q("new_purchase_limit").value = "0";
    q("new_hidden").checked = false;
    q("new_trial").checked = false;
  }

  function fillEditForm(plan) {
    q("edit_id").value = plan.id;
    q("edit_name").value = plan.name || "";
    q("edit_price").value = plan.price ?? "";
    q("edit_days").value = plan.period_days ?? "";
    q("edit_gb").value = plan.gb_limit ?? "";
    q("edit_device_limit").value = plan.device_limit ?? 0;
    q("edit_purchase_limit").value = plan.purchase_limit ?? 0;
    q("edit_hidden").checked = Boolean(plan.is_hidden);
    q("edit_trial").checked = Boolean(plan.is_trial);
  }

  function renderPlanInlineEdit(plan, button) {
    const body = button.closest(".row-context-menu")?.querySelector(".row-context-menu__body");
    if (!body) return;
    body.innerHTML = `
      <div class="row-context-inline-form">
        <input data-plan-field="name" type="text" value="${escapeHtml(plan.name || "")}" placeholder="Название" />
        <input data-plan-field="price" type="number" value="${escapeHtml(plan.price ?? "")}" placeholder="Цена" />
        <input data-plan-field="period_days" type="number" value="${escapeHtml(plan.period_days ?? "")}" placeholder="Период, дней" />
        <input data-plan-field="gb_limit" type="number" value="${escapeHtml(plan.gb_limit ?? "")}" placeholder="Лимит ГБ" />
        <input data-plan-field="device_limit" type="number" value="${escapeHtml(plan.device_limit ?? 0)}" placeholder="Лимит устройств" />
        <input data-plan-field="purchase_limit" type="number" value="${escapeHtml(plan.purchase_limit ?? 0)}" placeholder="Лимит пользователей" />
        <label class="plans-flag"><input data-plan-field="is_hidden" type="checkbox" ${plan.is_hidden ? "checked" : ""} /> <span>Скрыть</span></label>
        <label class="plans-flag"><input data-plan-field="is_trial" type="checkbox" ${plan.is_trial ? "checked" : ""} /> <span>Trial</span></label>
        <div class="row-context-inline-form__actions">
          <button class="btn-secondary" type="button" data-inline-cancel>Назад</button>
          <button class="btn-primary" type="button" data-inline-save>Сохранить</button>
        </div>
      </div>
    `;

    body.querySelector("[data-inline-cancel]")?.addEventListener("click", () => closeRowContextMenu());
    body.querySelector("[data-inline-save]")?.addEventListener("click", async (event) => {
      const field = (name) => body.querySelector(`[data-plan-field="${name}"]`);
      const payload = {
        is_hidden: field("is_hidden").checked,
        is_trial: field("is_trial").checked,
      };
      if (field("name").value.trim()) payload.name = field("name").value.trim();
      if (field("price").value) payload.price = Number(field("price").value);
      if (field("period_days").value) payload.period_days = Number(field("period_days").value);
      if (field("gb_limit").value) payload.gb_limit = Number(field("gb_limit").value);
      if (field("device_limit").value !== "") payload.device_limit = Number(field("device_limit").value || 0);
      if (field("purchase_limit").value !== "") payload.purchase_limit = Number(field("purchase_limit").value || 0);

      await withButtonLoading(event.currentTarget, async () => {
        await api(`/api/admin/plans/${plan.id}`, {
          method: "PATCH",
          body: JSON.stringify(payload),
        });
        await loadPlans();
        closeRowContextMenu();
        showToast("Тариф обновлен", "success");
      }).catch((err) => alert(err.message));
    });
  }

  function bindDelete(selector, attr, reload) {
    document.querySelectorAll(selector).forEach((button) => {
      button.addEventListener("click", async (e) => {
        const planId = Number(button.getAttribute(attr) || "0");
        if (!planId) return;
        if (!confirm(`Удалить тариф #${planId}? Действие необратимо.`)) return;

        await withButtonLoading(e.currentTarget, async () => {
          await api(`/api/admin/plans/${planId}`, { method: "DELETE" });
          await reload();
          showToast("Тариф удален", "success");
        }).catch((err) => alert(err.message));
      });
    });
  }

  function bindMoveButtons(items, reload) {
    document.querySelectorAll("button[data-move-id]").forEach((button) => {
      button.addEventListener("click", async (e) => {
        const planId = Number(button.getAttribute("data-move-id") || "0");
        const direction = button.getAttribute("data-move-direction");
        if (!planId || !direction) return;

        await withButtonLoading(e.currentTarget, async () => {
          await api(`/api/admin/plans/${planId}/move`, {
            method: "POST",
            body: JSON.stringify({ direction }),
          });
          await reload();
        }).catch((err) => alert(err.message));
      });
    });
  }

  async function loadPlans() {
    const data = await api("/api/admin/plans");
    const items = data.items || [];
    latestPlans = items;
    q("tbody").innerHTML = "";
    q("plans_mobile_list").innerHTML = "";

    items.forEach((plan) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${plan.id}</td>
        <td>${plan.display_order ?? plan.id}</td>
        <td>${safeText(plan.name)}</td>
        <td>${planBadges(plan)}</td>
        <td>${plan.price}</td>
        <td>${plan.period_days}</td>
        <td>${plan.gb_limit ?? 0}</td>
        <td>${plan.device_limit ?? 0}</td>
        <td>${Number(plan.purchase_limit || 0) > 0 ? plan.purchase_limit : "—"}</td>
        <td>${plan.subscriptions_count}</td>
      `;
      tr.classList.add("is-clickable-row");
      tr.addEventListener("click", (event) => {
        event.stopPropagation();
        showRowContextMenu(tr, [
          {
            label: "Изменить",
            keepOpen: true,
            onClick: (event, button) => {
              renderPlanInlineEdit(plan, button);
            },
          },
          {
            label: "Поднять выше",
            onClick: async (event, button) => {
              await withButtonLoading(button, async () => {
                await api(`/api/admin/plans/${plan.id}/move`, {
                  method: "POST",
                  body: JSON.stringify({ direction: "up" }),
                });
                await loadPlans();
              }).catch((err) => alert(err.message));
            },
          },
          {
            label: "Опустить ниже",
            onClick: async (event, button) => {
              await withButtonLoading(button, async () => {
                await api(`/api/admin/plans/${plan.id}/move`, {
                  method: "POST",
                  body: JSON.stringify({ direction: "down" }),
                });
                await loadPlans();
              }).catch((err) => alert(err.message));
            },
          },
          {
            label: "Удалить",
            className: "row-action-menu__item--danger",
            onClick: async (event, button) => {
              if (!confirm(`Удалить тариф #${plan.id}? Действие необратимо.`)) return;

              await withButtonLoading(button, async () => {
                await api(`/api/admin/plans/${plan.id}`, { method: "DELETE" });
                await loadPlans();
                showToast("Тариф удален", "success");
              }).catch((err) => alert(err.message));
            },
          },
        ], {
          title: `Тариф #${plan.id}`,
          meta: [
            { label: "Название", value: plan.name },
            { label: "Цена", value: `${plan.price} RUB` },
            { label: "Период", value: `${plan.period_days} дн.` },
            { label: "Порядок", value: plan.display_order ?? plan.id },
            { label: "Лимит трафика", value: `${plan.gb_limit ?? 0} ГБ` },
            { label: "Устройств", value: plan.device_limit ?? 0 },
            { label: "Лимит пользователей", value: Number(plan.purchase_limit || 0) > 0 ? plan.purchase_limit : "Без лимита" },
            { label: "Подписок", value: plan.subscriptions_count },
          ],
        });
      });
      q("tbody").appendChild(tr);

      const card = document.createElement("article");
      card.className = "plans-mobile-card";
      card.innerHTML = `
        <div class="plans-mobile-card__head">
          <div>
            <div class="plans-mobile-card__id">#${plan.id}</div>
            <h4>${safeText(plan.name)}</h4>
          </div>
          <div class="plans-mobile-card__badges">${planBadges(plan)}</div>
        </div>
        <div class="plans-mobile-card__grid">
          <div><span>Цена</span><b>${plan.price} RUB</b></div>
          <div><span>Порядок</span><b>${plan.display_order ?? plan.id}</b></div>
          <div><span>Период</span><b>${plan.period_days} дн.</b></div>
          <div><span>Лимит</span><b>${plan.gb_limit ?? 0} ГБ</b></div>
          <div><span>Устройств</span><b>${plan.device_limit ?? 0}</b></div>
          <div><span>Лимит пользователей</span><b>${Number(plan.purchase_limit || 0) > 0 ? plan.purchase_limit : "Без лимита"}</b></div>
          <div><span>Подписок</span><b>${plan.subscriptions_count}</b></div>
        </div>
        <div class="row-actions">
          <button class="btn-outline-primary plan-move-btn plan-move-btn--mobile" data-move-id="${plan.id}" data-move-direction="up">${moveIcon("up")}<span>Выше</span></button>
          <button class="btn-outline-primary plan-move-btn plan-move-btn--mobile" data-move-id="${plan.id}" data-move-direction="down">${moveIcon("down")}<span>Ниже</span></button>
          <button data-mobile-edit="${plan.id}">Изменить</button>
          <button class="btn-danger" data-mobile-delete="${plan.id}">Удалить</button>
        </div>
      `;
      q("plans_mobile_list").appendChild(card);
    });

    document.querySelectorAll("button[data-mobile-edit]").forEach((button) => {
      button.addEventListener("click", () => {
        const planId = Number(button.getAttribute("data-mobile-edit") || "0");
        const plan = items.find((item) => item.id === planId);
        if (plan) {
          fillEditForm(plan);
          openPlanModal("edit");
        }
      });
    });

    bindDelete("button[data-delete]", "data-delete", loadPlans);
    bindDelete("button[data-mobile-delete]", "data-mobile-delete", loadPlans);
    bindMoveButtons(items, loadPlans);
  }

  q("create_plan").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      await api("/api/admin/plans", {
        method: "POST",
        body: JSON.stringify({
          name: q("new_name").value.trim(),
          price: Number(q("new_price").value),
          period_days: Number(q("new_days").value),
          gb_limit: Number(q("new_gb").value),
          device_limit: Number(q("new_device_limit").value || 0),
          purchase_limit: Number(q("new_purchase_limit").value || 0),
          is_hidden: q("new_hidden").checked,
          is_trial: q("new_trial").checked,
        }),
      });
      resetCreateForm();
      await loadPlans();
      closePlanModal();
      showToast("Тариф создан", "success");
    }).catch((err) => alert(err.message));
  });

  q("update_plan").addEventListener("click", async (e) => {
    const id = Number(q("edit_id").value || "0");
    if (!id) return alert("Введите ID тарифа");

    const payload = {
      is_hidden: q("edit_hidden").checked,
      is_trial: q("edit_trial").checked,
    };
    if (q("edit_name").value) payload.name = q("edit_name").value.trim();
    if (q("edit_price").value) payload.price = Number(q("edit_price").value);
    if (q("edit_days").value) payload.period_days = Number(q("edit_days").value);
    if (q("edit_gb").value) payload.gb_limit = Number(q("edit_gb").value);
    if (q("edit_device_limit").value !== "") payload.device_limit = Number(q("edit_device_limit").value || 0);
    if (q("edit_purchase_limit").value !== "") payload.purchase_limit = Number(q("edit_purchase_limit").value || 0);

    await withButtonLoading(e.currentTarget, async () => {
      await api(`/api/admin/plans/${id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
      await loadPlans();
      closePlanModal();
      showToast("Тариф обновлен", "success");
    }).catch((err) => alert(err.message));
  });

  q("open_create_plan").addEventListener("click", () => {
    resetCreateForm();
    openPlanModal("create");
  });

  q("plan_modal_overlay")?.addEventListener("click", closePlanModal);
  q("plan_modal_close")?.addEventListener("click", closePlanModal);
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closePlanModal();
  });

  q("edit_id").addEventListener("input", () => {
    const id = Number(q("edit_id").value || "0");
    if (!id) return;
    const plan = latestPlans.find((item) => item.id === id);
    if (plan) fillEditForm(plan);
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["new_name", "new_price", "new_days", "new_gb", "new_device_limit", "new_purchase_limit"], "create_plan");
    bindEnterSubmit(["edit_id", "edit_name", "edit_price", "edit_days", "edit_gb", "edit_device_limit", "edit_purchase_limit"], "update_plan");
    resetCreateForm();
    await loadPlans();
  } catch (e) {
    alert(e.message);
  }
});
