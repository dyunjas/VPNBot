document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
  renderShell({
    activeKey: "servers",
    title: "Серверы",
    subtitle: "Управление и диагностика узлов",
    contentHtml: `
      <div class="content-grid">
        <div class="card">
          <h3>Список серверов</h3>
          <div class="toolbar">
            <button id="reload" class="btn-primary">Обновить</button>
          </div>
          <div class="table-wrap">
            <table>
              <thead>
                <tr><th>ID</th><th>Страна</th><th>Хост</th><th>Endpoint</th><th>Ключи</th><th>Действия</th></tr>
              </thead>
              <tbody id="tbody"></tbody>
            </table>
          </div>
        </div>

        <div class="content-stack">
          <div class="card">
            <h3>Добавить сервер</h3>
            <div class="toolbar">
              <input id="country" type="text" placeholder="Страна (например, Germany)" />
              <input id="inbound_tag" type="text" placeholder="Inbound tag" />
              <input id="grpc_endpoint" type="text" placeholder="GRPC endpoint (host:port или URL)" />
              <input id="public_host" type="text" placeholder="Публичный хост" />
              <input id="port" type="number" value="443" placeholder="Порт" />
              <input id="sni" type="text" value="telegram.com" placeholder="SNI" />
              <input id="fp" type="text" value="chrome" placeholder="Fingerprint" />
              <input id="pbk" type="text" placeholder="Public key (pbk)" />
              <input id="short_id" type="text" placeholder="Short ID (опционально)" />
              <input id="note" type="text" placeholder="Примечание (опционально)" />
              <button id="create_server" class="btn-primary">Создать сервер</button>
            </div>
          </div>

          <div class="card">
            <h3>Результат действий</h3>
            <div id="server_result">Выберите действие</div>
          </div>
        </div>
      </div>
    `,
  });

  function renderResult(data) {
    const result = (data && data.result) || {};
    const keys = Object.keys(result);
    if (!keys.length) {
      q("server_result").innerHTML = `<div>${statusBadge("ok")} Команда выполнена, пустой ответ</div>`;
      return;
    }
    q("server_result").innerHTML = `
      <div class="table-wrap">
        <table>
          <thead><tr><th>Поле</th><th>Значение</th></tr></thead>
          <tbody>
            ${keys.map((k) => `<tr><td>${k}</td><td>${safeText(result[k])}</td></tr>`).join("")}
          </tbody>
        </table>
      </div>
    `;
  }

  async function serverAction(serverId, action) {
    const data = await api(`/admin-api/servers/${serverId}/action`, {
      method: "POST",
      body: JSON.stringify({ action }),
    });
    renderResult(data);
  }

  async function loadRows() {
    const data = await api("/admin-api/servers");
    const items = data.items || [];
    q("tbody").innerHTML = "";

    items.forEach((s) => {
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td>${s.id}</td>
        <td>${safeText(s.country)}</td>
        <td>${safeText(s.public_host)}:${safeText(s.port)}</td>
        <td>${safeText(s.grpc_endpoint)}</td>
        <td>${safeText(s.active_keys_count)}/${safeText(s.total_keys_count)}</td>
        <td></td>
      `;

      const actions = document.createElement("div");
      actions.className = "row-actions";

      const h = document.createElement("button");
      h.textContent = "Проверка";
      h.addEventListener("click", async () => {
        try { await serverAction(s.id, "health"); } catch (e) { alert(e.message); }
      });

      const st = document.createElement("button");
      st.textContent = "Статистика";
      st.addEventListener("click", async () => {
        try { await serverAction(s.id, "stats"); } catch (e) { alert(e.message); }
      });

      const rs = document.createElement("button");
      rs.textContent = "Ресинк";
      rs.addEventListener("click", async () => {
        try { await serverAction(s.id, "resync"); } catch (e) { alert(e.message); }
      });

      actions.append(h, st, rs);
      tr.querySelector("td:last-child").appendChild(actions);
      q("tbody").appendChild(tr);
    });
  }

  q("create_server").addEventListener("click", async (e) => {
    const payload = {
      country: q("country").value.trim(),
      inbound_tag: q("inbound_tag").value.trim(),
      grpc_endpoint: q("grpc_endpoint").value.trim(),
      public_host: q("public_host").value.trim(),
      port: Number(q("port").value || "443"),
      sni: q("sni").value.trim() || "telegram.com",
      fp: q("fp").value.trim() || "chrome",
      pbk: q("pbk").value.trim(),
      short_id: q("short_id").value.trim() || null,
      note: q("note").value.trim() || null,
    };

    if (!payload.country || !payload.inbound_tag || !payload.grpc_endpoint || !payload.public_host || !payload.pbk) {
      return alert("Заполните обязательные поля: страна, inbound tag, endpoint, public host, pbk");
    }

    await withButtonLoading(e.currentTarget, async () => {
      await api("/admin-api/servers", {
        method: "POST",
        body: JSON.stringify(payload),
      });
      showToast("Сервер добавлен", "success");
      await loadRows();
    }).catch((err) => alert(err.message));
  });

  q("reload").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
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
