document.addEventListener("DOMContentLoaded", async () => {
  const roleLabel = (role) => ({
    support: "Support",
  }[String(role || "").toLowerCase()] || role || "—");

  const roleBadge = (role) => {
    const value = String(role || "support").toLowerCase();
    return `<span class="badge ok">${safeText(roleLabel(value))}</span>`;
  };

  const adminStatusBadge = (isActive) => (
    isActive
      ? `<span class="badge ok">Активен</span>`
      : `<span class="badge danger">Отключен</span>`
  );

  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "admins",
    title: "Администраторы",
    subtitle: "Выдача доступа и роль support для администрирования",
    contentHtml: `
      <div class="page-shell admins-page">
        <div class="card admin-access-card">
          <div class="admin-section-head">
            <div>
              <div class="dashboard-section-card__eyebrow">Доступ</div>
              <h3>Новый администратор</h3>
            </div>
          </div>
          <div class="toolbar admin-access-toolbar">
            <input id="admin_user_id" type="number" min="1" placeholder="User ID из таблицы пользователей" />
            <input id="admin_login" type="text" autocomplete="off" placeholder="Логин для входа" />
            <input id="admin_password" type="password" autocomplete="new-password" placeholder="Пароль от 8 символов" />
            <select id="admin_role">
              <option value="support">Support</option>
            </select>
            <select id="admin_active">
              <option value="true">Активен</option>
              <option value="false">Отключен</option>
            </select>
            <button id="create_admin" class="btn-primary" type="button">Создать доступ</button>
          </div>
          <div class="admin-access-hints">
            <div><b>Support</b><span>доступ только к пользователям, подпискам, транзакциям и реферальной системе</span></div>
          </div>
        </div>

        <div class="card">
          <div class="admin-section-head">
            <h3>Список администраторов</h3>
            <button id="reload_admins" class="btn-secondary" type="button">Обновить</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>ID</th>
                  <th>Логин</th>
                  <th>Пользователь</th>
                  <th>Telegram</th>
                  <th>Роль</th>
                  <th>Статус</th>
                  <th>Создан</th>
                </tr>
              </thead>
              <tbody id="admins_tbody"></tbody>
            </table>
          </div>
        </div>
      </div>
    `,
  });

  async function loadAdmins() {
    const data = await api("/api/admin/admins");
    const items = data.items || [];
    const tbody = q("admins_tbody");
    tbody.innerHTML = "";

    if (!items.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td colspan="7">Администраторы не найдены</td>`;
      tbody.appendChild(tr);
      return;
    }

    items.forEach((admin) => {
      const tr = document.createElement("tr");
      tr.classList.add("is-clickable-row");
      tr.innerHTML = `
        <td>${safeText(admin.id)}</td>
        <td>${safeText(admin.login || "—")}</td>
        <td><b>#${safeText(admin.user_id)}</b><span class="table-sub">${safeText(admin.username || "—")}</span></td>
        <td>${safeText(admin.tg_id || "—")}</td>
        <td>${roleBadge(admin.role)}</td>
        <td>${adminStatusBadge(admin.is_active)}</td>
        <td>${formatDateTime(admin.created_at)}</td>
      `;
      tr.addEventListener("click", () => openAdminCard(tr, admin));
      tbody.appendChild(tr);
    });
  }

  function openAdminCard(row, admin) {
    showRowContextMenu(row, [], {
      title: `Администратор #${admin.id}`,
      icon: "user-cog",
      meta: [
        { label: "User ID", value: admin.user_id },
        { label: "Логин", value: admin.login || "—" },
        { label: "Telegram", value: admin.tg_id || "—" },
        { label: "Username", value: admin.username || "—" },
        { label: "Роль", html: roleBadge(admin.role) },
        { label: "Статус", html: adminStatusBadge(admin.is_active) },
      ],
      render: (body, close) => {
        const form = document.createElement("div");
        form.className = "row-context-inline-form";
        form.innerHTML = `
          <label><span>Логин</span><input id="ctx_admin_login" type="text" autocomplete="off" value="${safeText(admin.login || "")}" /></label>
          <label><span>Роль</span><div class="admin-role-static">${roleBadge("support")}</div></label>
          <label><span>Новый пароль</span><input id="ctx_admin_password" type="password" autocomplete="new-password" placeholder="Оставьте пустым, чтобы не менять" /></label>
          <div class="row-context-inline-form__actions admin-card-actions">
            <button id="ctx_admin_save" class="btn-primary" type="button">Сохранить</button>
            <button id="ctx_admin_toggle" class="${admin.is_active ? "btn-secondary" : "btn-primary"}" type="button">${admin.is_active ? "Отключить" : "Включить"}</button>
            <button id="ctx_admin_delete" class="btn-danger" type="button">Удалить</button>
          </div>
        `;
        body.appendChild(form);

        const loginInput = form.querySelector("#ctx_admin_login");
        const passwordInput = form.querySelector("#ctx_admin_password");
        const saveButton = form.querySelector("#ctx_admin_save");
        const toggleButton = form.querySelector("#ctx_admin_toggle");
        const deleteButton = form.querySelector("#ctx_admin_delete");

        saveButton?.addEventListener("click", async (event) => {
          await withButtonLoading(event.currentTarget, async () => {
            const payload = {
              login: (loginInput?.value || "").trim(),
              role: "support",
            };
            const password = (passwordInput?.value || "").trim();
            if (password) payload.password = password;
            await api(`/api/admin/admins/${admin.id}`, {
              method: "PATCH",
              body: JSON.stringify(payload),
            });
            close();
            await loadAdmins();
            showToast("Доступ обновлен", "success");
          }).catch((err) => alert(err.message));
        });

        toggleButton?.addEventListener("click", async (event) => {
          await withButtonLoading(event.currentTarget, async () => {
            await api(`/api/admin/admins/${admin.id}`, {
              method: "PATCH",
              body: JSON.stringify({ is_active: !admin.is_active }),
            });
            close();
            await loadAdmins();
            showToast("Доступ обновлен", "success");
          }).catch((err) => alert(err.message));
        });

        deleteButton?.addEventListener("click", async (event) => {
          if (!confirm(`Удалить админ-доступ #${admin.id}?`)) return;
          await withButtonLoading(event.currentTarget, async () => {
            await api(`/api/admin/admins/${admin.id}`, { method: "DELETE" });
            close();
            await loadAdmins();
            showToast("Доступ удален", "success");
          }).catch((err) => alert(err.message));
        });
      },
    });
  }

  q("create_admin").addEventListener("click", async (event) => {
    const userId = Number(q("admin_user_id").value);
    const login = (q("admin_login").value || "").trim();
    const password = (q("admin_password").value || "").trim();
    if (!userId) {
      alert("Укажите User ID");
      return;
    }
    if (login.length < 3) {
      alert("Укажите логин от 3 символов");
      return;
    }
    if (password.length < 8) {
      alert("Укажите пароль от 8 символов");
      return;
    }
    await withButtonLoading(event.currentTarget, async () => {
      await api("/api/admin/admins", {
        method: "POST",
        body: JSON.stringify({
          user_id: userId,
          login,
          password,
          role: q("admin_role").value,
          is_active: q("admin_active").value === "true",
        }),
      });
      q("admin_user_id").value = "";
      q("admin_login").value = "";
      q("admin_password").value = "";
      await loadAdmins();
      showToast("Администратор добавлен", "success");
    }).catch((err) => alert(err.message));
  });

  q("reload_admins").addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, loadAdmins).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    bindEnterSubmit(["admin_user_id", "admin_login", "admin_password"], "create_admin");
    await loadAdmins();
  } catch (err) {
    alert(err.message);
  }
});
