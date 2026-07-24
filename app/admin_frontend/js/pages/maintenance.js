let currentMaintenanceState = null;
let currentHealthState = null;
let currentServerLoadState = null;

function maintenanceStatusBadge(enabled) {
  const tone = enabled ? "warn" : "ok";
  const label = enabled ? "\u0412\u043a\u043b\u044e\u0447\u0435\u043d\u044b" : "\u0410\u043a\u0442\u0438\u0432\u043d\u0430";
  return `<span class="badge ${tone}">${label}</span>`;
}

function maintenanceModeLabel(value) {
  return String(value || "").toLowerCase() === "auto" ? "\u0410\u0432\u0442\u043e" : "\u0420\u0443\u0447\u043d\u043e\u0439";
}

function healthStatusLabel(status) {
  const value = String(status || "").toLowerCase();
  if (value === "ok") return "Работает";
  if (value === "warn") return "Проверьте";
  return "Ошибка";
}

function healthStatusTone(status) {
  const value = String(status || "").toLowerCase();
  if (value === "ok" || value === "warn" || value === "danger") return value;
  return "danger";
}

function formatLatency(value) {
  const ms = Number(value);
  if (!Number.isFinite(ms) || ms < 0) return "—";
  if (ms >= 1000) return `${(ms / 1000).toFixed(1)} с`;
  return `${Math.round(ms)} мс`;
}

function serviceIcon(key) {
  const icons = {
    api: "<path d='M4 7a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2z'/><path d='M8 9h.01'/><path d='M12 9h.01'/><path d='M16 9h.01'/><path d='M8 13h8'/>",
    database: "<path d='M4 6c0 1.657 3.582 3 8 3s8 -1.343 8 -3s-3.582 -3 -8 -3s-8 1.343 -8 3'/><path d='M4 6v6c0 1.657 3.582 3 8 3s8 -1.343 8 -3v-6'/><path d='M4 12v6c0 1.657 3.582 3 8 3s8 -1.343 8 -3v-6'/>",
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[key] || icons.api}</svg>`;
}

function maintenanceInfoIcon(key) {
  const icons = {
    mode: "<path d='M4 13a8 8 0 1 0 4 -6.928'/><path d='M4 4v5h5'/><path d='M12 12l3 2'/>",
    source: "<path d='M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0'/><path d='M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2'/>",
    updated: "<path d='M5 12a7 7 0 1 0 2.05 -4.95'/><path d='M5 6v4h4'/><path d='M12 8v4l2 2'/>",
  };
  return `<span class="maintenance-data-grid__icon"><svg viewBox="0 0 24 24" aria-hidden="true">${icons[key] || icons.mode}</svg></span>`;
}


function formatServerPercent(value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return "—";
  return `${num.toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}

function formatLoadAverage(values) {
  if (!Array.isArray(values) || !values.length) return "—";
  return values.map((value) => Number(value || 0).toFixed(2)).join(" / ");
}

function serverMetricDetails(metric) {
  const details = metric?.details || {};
  if (metric?.key === "cpu") {
    const cores = details.logical_cores ? `${details.logical_cores} потоков` : "—";
    const freq = details.frequency_mhz ? `${details.frequency_mhz} MHz` : "—";
    return `${cores} · ${freq}`;
  }
  if (metric?.key === "memory") {
    return `${details.used_gb ?? "—"} / ${details.total_gb ?? "—"} GB · свободно ${details.available_gb ?? "—"} GB`;
  }
  if (metric?.key === "disk") {
    return `${details.used_gb ?? "—"} / ${details.total_gb ?? "—"} GB · свободно ${details.free_gb ?? "—"} GB`;
  }
  if (metric?.key === "process_memory") {
    return `PID ${details.pid ?? "—"} · ${details.threads ?? "—"} потоков · VMS ${details.vms_gb ?? "—"} GB`;
  }
  return "";
}

function renderMaintenanceDetails(state) {
  const host = q("maintenance_panel");
  if (!host) return;

  const maintenance = state || {};
  const enabled = Boolean(maintenance.enabled);
  const message = maintenance.message || "Сервер на технических работах.";
  const updatedAt = maintenance.updated_at ? formatDateTime(maintenance.updated_at) : "—";
  const source = maintenance.source || "—";

  host.innerHTML = `
    <div class="maintenance-control ${enabled ? "maintenance-control--enabled" : "maintenance-control--disabled"}">
      <div class="maintenance-status-strip ${enabled ? "maintenance-status-strip--enabled" : "maintenance-status-strip--disabled"}">
        <div>
          <span>Текущий режим</span>
          <b>${enabled ? "Технические работы включены" : "Сервис работает"}</b>
        </div>
        ${maintenanceStatusBadge(enabled)}
      </div>

      <div class="maintenance-data-grid">
        <div>${maintenanceInfoIcon("mode")}<span>Режим</span><b>${safeText(maintenanceModeLabel(maintenance.mode))}</b></div>
        <div>${maintenanceInfoIcon("source")}<span>Источник</span><b>${safeText(source)}</b></div>
        <div>${maintenanceInfoIcon("updated")}<span>Обновлено</span><b>${safeText(updatedAt)}</b></div>
      </div>

      <label class="maintenance-field">
        <span>Сообщение для пользователей</span>
        <textarea id="maintenance_message" rows="5">${safeText(message)}</textarea>
      </label>

      <div class="maintenance-actions">
        <button id="maintenance_enable" class="btn-primary" type="button">Включить техработы</button>
        <button id="maintenance_disable" class="btn-solid-danger" type="button">Выключить</button>
        <button id="maintenance_refresh" class="btn-secondary" type="button">Обновить</button>
      </div>
    </div>
  `;

  q("maintenance_enable")?.toggleAttribute("disabled", enabled);
  q("maintenance_disable")?.toggleAttribute("disabled", !enabled);

  q("maintenance_enable")?.addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      const nextMessage = q("maintenance_message")?.value.trim() || "Сервер на технических работах.";
      await api("/api/admin/system/maintenance", {
        method: "POST",
        body: JSON.stringify({ enabled: true, message: nextMessage }),
      });
      showToast("Техработы включены", "success");
      await loadMaintenance();
    }).catch((error) => alert(error.message));
  });

  q("maintenance_disable")?.addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, async () => {
      await api("/api/admin/system/maintenance", {
        method: "POST",
        body: JSON.stringify({ enabled: false }),
      });
      showToast("Техработы выключены", "success");
      await loadMaintenance();
    }).catch((error) => alert(error.message));
  });

  q("maintenance_refresh")?.addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, loadAllMaintenanceData).catch((error) => alert(error.message));
  });
}

function renderSystemHealth(data) {
  const host = q("maintenance_health_panel");
  if (!host) return;

  const items = Array.isArray(data?.items) ? data.items : [];
  const checkedAt = data?.checked_at ? formatDateTime(data.checked_at) : "—";
  const overall = healthStatusTone(data?.overall || "danger");

  host.innerHTML = `
    <div class="maintenance-health-card maintenance-health-card--${overall}">
      <div class="maintenance-panel-head">
        <div>
          <div class="dashboard-section-card__eyebrow">Мониторинг</div>
          <h3>Статус сервисов</h3>
          <p>Последняя проверка: ${safeText(checkedAt)}</p>
        </div>
        <button id="system_health_refresh" class="btn-secondary" type="button">Обновить</button>
      </div>
      <div class="maintenance-health-grid">
        ${items.map((item) => {
          const status = healthStatusTone(item.status);
          const label = item.label || item.key || "Сервис";
          const checked = item.checked_at ? formatDateTime(item.checked_at) : "—";
          return `
            <div class="maintenance-health-item maintenance-health-item--${status}">
              <div class="maintenance-health-item__top">
                <div class="maintenance-health-item__icon">${serviceIcon(item.key)}</div>
                <div>
                  <b>${safeText(label)}</b>
                  <span>${safeText(item.message || "Нет данных")}</span>
                </div>
                <span class="badge ${status === "ok" ? "ok" : status === "warn" ? "warn" : "danger"}">${healthStatusLabel(status)}</span>
              </div>
              <div class="maintenance-health-item__meta">
                <span>${safeText(checked)}</span>
                <span>${safeText(formatLatency(item.latency_ms))}</span>
              </div>
            </div>
          `;
        }).join("") || '<div class="system-health__empty">Нет данных проверки</div>'}
      </div>
    </div>
  `;

  q("system_health_refresh")?.addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, loadHealth).catch((error) => alert(error.message));
  });
}

function renderServerLoad(data) {
  const host = q("maintenance_load_panel");
  if (!host) return;

  const metrics = Array.isArray(data?.metrics) ? data.metrics : [];
  const checkedAt = data?.checked_at ? formatDateTime(data.checked_at) : "—";
  const summary = data?.summary || {};
  const unavailable = data && data.metrics_available === false;

  host.innerHTML = `
    <div class="maintenance-load-card">
      <div class="maintenance-panel-head">
        <div>
          <div class="dashboard-section-card__eyebrow">Нагрузка сервера</div>
          <h3>Сервер API</h3>
          <p>${safeText(data?.hostname || "—")} · ${safeText(checkedAt)}</p>
        </div>
        <button id="server_load_refresh" class="btn-secondary" type="button">Обновить</button>
      </div>

      <div class="maintenance-load-metrics">
        <div><span>Uptime</span><b>${safeText(summary.uptime || "—")}</b></div>
        <div><span>CPU cores</span><b>${safeText(summary.cpu_count || "—")}</b></div>
        <div><span>Load avg</span><b>${safeText(formatLoadAverage(summary.load_average))}</b></div>
      </div>

      <div class="maintenance-load-list">
        ${unavailable ? '<div class="system-health__empty">Метрики сервера недоступны: установите psutil</div>' : metrics.map((metric) => {
          const status = healthStatusTone(metric.status);
          const percent = Math.max(0, Math.min(100, Number(metric.percent) || 0));
          return `
            <div class="maintenance-load-row maintenance-load-row--${status}">
              <div class="maintenance-load-row__head">
                <span>${safeText(metric.label || metric.key || "Метрика")}</span>
                <b>${safeText(metric.value || formatServerPercent(percent))}</b>
              </div>
              <div class="maintenance-load-row__bar">
                <i style="width:${percent}%"></i>
              </div>
              <div class="maintenance-load-row__details">${safeText(serverMetricDetails(metric))}</div>
            </div>
          `;
        }).join("") || '<div class="system-health__empty">Нет данных нагрузки сервера</div>'}
      </div>
    </div>
  `;

  q("server_load_refresh")?.addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, loadServerLoad).catch((error) => alert(error.message));
  });
}

async function loadMaintenance() {
  const host = q("maintenance_panel");
  if (host) host.textContent = "Загрузка...";
  const data = await api("/api/admin/system/maintenance");
  currentMaintenanceState = data.maintenance || {};
  renderMaintenanceDetails(currentMaintenanceState);
}

async function loadHealth() {
  const healthHost = q("maintenance_health_panel");
  if (healthHost) healthHost.textContent = "Загрузка...";
  currentHealthState = await api("/api/admin/system/health");
  renderSystemHealth(currentHealthState);
}
async function loadServerLoad() {
  const loadHost = q("maintenance_load_panel");
  if (loadHost) loadHost.textContent = "Загрузка...";
  currentServerLoadState = await api("/api/admin/system/server-load");
  renderServerLoad(currentServerLoadState);
}
async function loadAllMaintenanceData() {
  await Promise.all([loadMaintenance(), loadHealth(), loadServerLoad()]);
}

async function initMaintenancePage() {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "maintenance",
    title: "Техработы",
    subtitle: "Режим обслуживания, статус сервисов и нагрузка сервера",
    contentHtml: `
      <div class="maintenance-dashboard">
        <div class="card dashboard-card dashboard-section-card maintenance-page-card maintenance-page-card--control">
          <div class="dashboard-section-card__head">
            <div>
              <div class="dashboard-section-card__eyebrow">Система</div>
              <h3>Технические работы</h3>
            </div>
          </div>
          <div id="maintenance_panel">Загрузка...</div>
        </div>

        <div id="maintenance_health_panel" class="maintenance-dashboard__health">Загрузка...</div>
        <div id="maintenance_load_panel" class="maintenance-dashboard__load">Загрузка...</div>
      </div>
    `,
  });

  await renderSessionInfo();
  await loadAllMaintenanceData();
}

document.addEventListener("DOMContentLoaded", initMaintenancePage);
