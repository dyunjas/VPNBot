const diagnosticsState = {
  tab: "errors",
};

function renderDiagnosticsLayout() {
  return `
    <div class="diagnostics-page">
      <div class="card diagnostics-tabs-card">
        <div class="toolbar toolbar--compact diagnostics-tabs">
          <button id="tab_errors" class="btn-secondary is-active" type="button">Центр ошибок</button>
          <button id="refresh_diagnostics" class="btn-primary" type="button">Обновить</button>
        </div>
      </div>
      <div id="diagnostics_content"></div>
    </div>
  `;
}

function setDiagnosticsTab(tab) {
  diagnosticsState.tab = tab;
  q("tab_errors")?.classList.toggle("is-active", tab === "errors");
}

function renderSummaryCards(items) {
  return `
    <div class="dashboard-stats-grid diagnostics-summary">
      ${items.map(([label, value]) => `
        <div class="stat-card">
          <div class="stat-label">${safeText(label)}</div>
          <div class="stat-value">${safeText(value)}</div>
        </div>
      `).join("")}
    </div>
  `;
}

async function loadErrors() {
  setDiagnosticsTab("errors");
  const host = q("diagnostics_content");
  host.innerHTML = `<div class="card"><div class="section-title">Загрузка ошибок...</div></div>`;
  const data = await api("/api/admin/diagnostics/errors?limit=80");
  const summary = data.summary || {};
  const items = data.items || [];
  host.innerHTML = `
    ${renderSummaryCards([
      ["Групп ошибок", summary.groups || 0],
      ["Событий", summary.events || 0],
      ["Файлов", summary.files || 0],
    ])}
    <div class="card diagnostics-list-card">
      <div class="admin-section-head">
        <div>
          <h3>Центр ошибок</h3>
          <div class="section-title">Группировка последних ERROR/CRITICAL из логов</div>
        </div>
      </div>
      <div class="table-wrap">
        <table>
          <thead><tr><th>Ошибка</th><th>Файл</th><th>Уровень</th><th>Количество</th><th>Последняя</th></tr></thead>
          <tbody>
            ${items.map((item) => `
              <tr class="is-clickable-row" data-error-key="${safeText(item.key)}">
                <td><b>${safeText(item.message)}</b></td>
                <td class="mono">${safeText(item.file)}</td>
                <td><span class="badge ${item.level === "CRITICAL" ? "danger" : "warn"}">${safeText(item.level)}</span></td>
                <td>${safeText(item.count)}</td>
                <td>${safeText(item.last_time || "—")}</td>
              </tr>
            `).join("") || "<tr><td colspan='5'>Ошибок не найдено</td></tr>"}
          </tbody>
        </table>
      </div>
    </div>
  `;

  host.querySelectorAll("[data-error-key]").forEach((row, index) => {
    const item = items[index];
    row.addEventListener("click", () => {
      showRowContextMenu(row, [], {
        title: item.message,
        icon: "info",
        meta: [
          { label: "Файл", value: item.file },
          { label: "Уровень", value: item.level },
          { label: "Количество", value: item.count },
          { label: "Последняя", value: item.last_time || "—" },
        ],
        render: (body) => {
          const box = document.createElement("div");
          box.className = "diagnostics-examples";
          box.innerHTML = (item.examples || []).map((example) => `
            <div class="diagnostics-example">
              <div><b>${safeText(example.file)}</b><span>${safeText(example.time || "без времени")}</span></div>
              <pre>${safeText(example.message)}</pre>
            </div>
          `).join("");
          body.appendChild(box);
        },
      });
    });
  });
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "diagnostics",
    title: "Диагностика",
    subtitle: "Ошибки и быстрый разбор инцидентов",
    contentHtml: renderDiagnosticsLayout(),
  });

  q("tab_errors")?.addEventListener("click", () => loadErrors().catch((error) => alert(error.message)));
  q("refresh_diagnostics")?.addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, loadErrors).catch((error) => alert(error.message));
  });

  try {
    await renderSessionInfo();
    await loadErrors();
  } catch (error) {
    alert(error.message);
  }
});
