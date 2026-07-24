const dashboardState = {
  chartPeriod: "14d",
};

function dashboardIcon(kind) {
  const icons = {
    users: "<path stroke='none' d='M0 0h24v24H0z' fill='none' /><path d='M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0' /><path d='M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2'/>",
    banned: "<path stroke='none' d='M0 0h24v24H0z' fill='none' /><path d='M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0' /><path d='M5.7 5.7l12.6 12.6'/>",
    subs: "<path stroke='none' d='M0 0h24v24H0z' fill='none' /><path d='M11.795 21h-6.795a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v4' /><path d='M14 18a4 4 0 1 0 8 0a4 4 0 1 0 -8 0' /><path d='M15 3v4' /><path d='M7 3v4' /><path d='M3 11h16' /><path d='M18 16.496v1.504l1 1'/>",
    paid: "<path stroke='none' d='M0 0h24v24H0z' fill='none' /><path d='M12 19h-6a3 3 0 0 1 -3 -3v-8a3 3 0 0 1 3 -3h12a3 3 0 0 1 3 3v4.5' /><path d='M3 10h18' /><path d='M16 19h6' /><path d='M19 16l3 3l-3 3' /><path d='M7.005 15h.005' /><path d='M11 15h2'/>",
    revenue: "<path stroke='none' d='M0 0h24v24H0z' fill='none' /><path d='M13 21h-7a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v3' /><path d='M16 3v4' /><path d='M8 3v4' /><path d='M4 11h12.5' /><path d='M21 15h-2.5a1.5 1.5 0 0 0 0 3h1a1.5 1.5 0 0 1 0 3h-2.5' /><path d='M19 21v1m0 -8v1'/>",
  };
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${icons[kind] || icons.users}</svg>`;
}

function formatNumber(value) {
  return Number(value || 0).toLocaleString("ru-RU");
}

function formatMoney(value) {
  return `${formatNumber(value)} ₽`;
}

function formatPercent(value) {
  return `${Number(value || 0).toLocaleString("ru-RU", { maximumFractionDigits: 1 })}%`;
}

function chartWindowLabel(period) {
  if (period === "30d") return "30 дней";
  if (period === "12m") return "12 месяцев";
  return "14 дней";
}

function chartSubtitle(period, kind) {
  const windowLabel = chartWindowLabel(period);
  const map = {
    payments: `Последние ${windowLabel} по пополнениям`,
    new_users: `Последние ${windowLabel} по новым пользователям`,
    subscriptions: `Последние ${windowLabel} по купленным подпискам`,
    activation: `Купленные подписки / новые пользователи за ${windowLabel}`,
  };
  return map[kind] || `Последние ${windowLabel}`;
}

function chartCardHtml({ prefix, title, subtitle, controls = "" }) {
  return `
    <div class="card dashboard-card dashboard-chart-card dashboard-section-card">
      <div class="dashboard-chart-head">
        <div>
          <h3>${title}</h3>
          <div id="${prefix}_subtitle" class="section-title">${subtitle}</div>
        </div>
        <div class="dashboard-chart-tools">
          ${controls}
          <div id="${prefix}_total" class="dashboard-chart-total">—</div>
        </div>
      </div>
      <div id="${prefix}" class="payments-chart">Загрузка...</div>
    </div>
  `;
}

function compactChartLabel(label) {
  const text = String(label || "").trim();
  if (!text) return "";
  if (/^\d{2}\.\d{2}\.\d{4}$/.test(text)) return text.slice(0, 5);
  if (/^\d{4}-\d{2}-\d{2}$/.test(text)) return `${text.slice(8, 10)}.${text.slice(5, 7)}`;
  return text;
}

function buildXAxisLabels(items, points, width, padding) {
  const labels = items.map((item) => compactChartLabel(item.label || item.key || ""));
  const longestLabel = labels.reduce((max, label) => Math.max(max, label.length), 0);
  const approxLabelWidth = Math.max(28, longestLabel * 7);
  const availableWidth = Math.max(width - padding.left - padding.right, 1);
  const maxVisibleLabels = Math.max(2, Math.floor(availableWidth / approxLabelWidth));
  const step = Math.max(1, Math.ceil(items.length / maxVisibleLabels));

  return points
    .map((point, index) => {
      const isFirst = index === 0;
      const isLast = index === points.length - 1;
      const visible = isFirst || isLast || index % step === 0;
      if (!visible) return "";
      return `<text x="${point.x}" y="294" text-anchor="middle">${safeText(labels[index])}</text>`;
    })
    .join("");
}

function buildChartSvg(chartId, items, values, options = {}) {
  const width = 920;
  const height = 335;
  const padding = { top: 22, right: 22, bottom: 66, left: 50 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(...values, 1);
  const minValue = options.minValue || 0;
  const denominator = Math.max(maxValue - minValue, 1);
  const step = items.length > 1 ? innerWidth / (items.length - 1) : 0;
  const baseline = padding.top + innerHeight;

  const points = items.map((item, index) => {
    const value = Number(values[index] || 0);
    const ratio = Math.max(0, Math.min(1, (value - minValue) / denominator));
    return {
      x: Number((padding.left + (items.length > 1 ? step * index : innerWidth / 2)).toFixed(1)),
      y: Number((padding.top + innerHeight - ratio * innerHeight).toFixed(1)),
      value,
    };
  });

  const valueFormatter = options.valueFormatter || ((value) => formatNumber(value));
  const gridLines = [0, 0.25, 0.5, 0.75, 1]
    .map((ratio) => {
      const y = Number((padding.top + innerHeight - ratio * innerHeight).toFixed(1));
      const gridValue = minValue + ratio * denominator;
      return `
        <g>
          <line x1="${padding.left}" y1="${y}" x2="${width - padding.right}" y2="${y}" />
          <text x="${padding.left - 14}" y="${y + 4}" text-anchor="end">${safeText(valueFormatter(gridValue))}</text>
        </g>
      `;
    })
    .join("");

  const xLabels = buildXAxisLabels(items, points, width, padding);
  const slotWidth = innerWidth / Math.max(items.length, 1);
  const barWidth = Math.max(10, Math.min(22, slotWidth * 0.48));
  const bars = points
    .map((point, index) => {
      const item = items[index];
      const h = Math.max(3, baseline - point.y);
      const tooltip = options.tooltipBuilder ? options.tooltipBuilder(item, point.value) : `${item.label || item.key || ""}`;
      return `
        <g class="metric-bar-chart__bar" data-chart-label="${safeText(item.label || item.key || "")}" data-chart-value="${safeText(valueFormatter(point.value))}" data-chart-meta="${safeText(tooltip)}">
          <rect x="${(point.x - barWidth / 2).toFixed(1)}" y="${(baseline - h).toFixed(1)}" width="${barWidth.toFixed(1)}" height="${h.toFixed(1)}" rx="3"></rect>
        </g>
      `;
    })
    .join("");

  const gradientBarId = `metric-bar-gradient-${chartId}`;

  return `
    <svg class="metric-chart__svg metric-chart__svg--tailadmin metric-chart__svg--tailadmin-bars" viewBox="0 0 ${width} ${height}" preserveAspectRatio="xMidYMid meet" aria-hidden="true">
      <defs>
        <linearGradient id="${gradientBarId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#3c50e0" />
          <stop offset="100%" stop-color="#3c50e0" />
        </linearGradient>
      </defs>
      <rect class="metric-chart__frame" x="0" y="0" width="${width}" height="${height}" rx="0" />
      <g class="metric-chart__grid">${gridLines}</g>
      <g style="fill:url(#${gradientBarId})">${bars}</g>
      <g class="metric-chart__axis">${xLabels}</g>
    </svg>
  `;
}

function bindMetricChartTooltip(host) {
  if (!host || host.dataset.chartTooltipInit === "1") return;
  host.dataset.chartTooltipInit = "1";

  const tooltip = document.createElement("div");
  tooltip.className = "metric-chart-tooltip";
  tooltip.hidden = true;
  host.appendChild(tooltip);

  const moveTooltip = (event, bar) => {
    const wrap = host.getBoundingClientRect();
    const label = bar.dataset.chartLabel || "";
    const value = bar.dataset.chartValue || "";
    const meta = bar.dataset.chartMeta || "";
    tooltip.innerHTML = `
      <div class="metric-chart-tooltip__top">
        <span>${safeText(label)}</span>
        <b>${safeText(value)}</b>
      </div>
      <div class="metric-chart-tooltip__meta">${safeText(meta)}</div>
    `;
    tooltip.hidden = false;

    const tooltipWidth = tooltip.offsetWidth || 220;
    const tooltipHeight = tooltip.offsetHeight || 88;
    const left = Math.min(Math.max(event.clientX - wrap.left + 14, 10), Math.max(wrap.width - tooltipWidth - 10, 10));
    const top = Math.max(event.clientY - wrap.top - tooltipHeight - 12, 10);
    tooltip.style.left = `${left}px`;
    tooltip.style.top = `${top}px`;
  };

  host.querySelectorAll(".metric-bar-chart__bar").forEach((bar) => {
    bar.addEventListener("pointerenter", (event) => {
      bar.classList.add("is-hovered");
      moveTooltip(event, bar);
    });
    bar.addEventListener("pointermove", (event) => moveTooltip(event, bar));
    bar.addEventListener("pointerleave", () => {
      bar.classList.remove("is-hovered");
      tooltip.hidden = true;
    });
  });
}

function buildMetricLegend(items, valueGetter, valueFormatter, metaBuilder) {
  return `
    <div class="metric-chart__legend">
      ${items
        .map((item) => {
          const value = Number(valueGetter(item) || 0);
          const label = String(item.label || item.key || "");
          const meta = metaBuilder ? metaBuilder(item, value) : "";
          return `
            <div class="metric-chart__legend-item">
              <div class="metric-chart__legend-label">${safeText(label)}</div>
              <div class="metric-chart__legend-value">${valueFormatter(value)}</div>
              ${meta ? `<div class="metric-chart__legend-meta">${safeText(meta)}</div>` : ""}
            </div>
          `;
        })
        .join("")}
    </div>
  `;
}

function renderMetricChart({
  hostId,
  totalId,
  subtitleId,
  period,
  items,
  valueGetter,
  valueFormatter,
  totalFormatter,
  countFormatter = valueFormatter,
  tooltipBuilder,
  showCountBelow = false,
  totalValue,
  emptyText = "Нет данных",
  legendMetaBuilder,
}) {
  const host = q(hostId);
  if (!host) return;

  const totalEl = totalId ? q(totalId) : null;
  const subtitleEl = subtitleId ? q(subtitleId) : null;
  if (subtitleEl) subtitleEl.textContent = chartSubtitle(period, hostId.replace("_chart", ""));

  if (!Array.isArray(items) || !items.length) {
    host.textContent = emptyText;
    if (totalEl) totalEl.textContent = totalFormatter(0);
    return;
  }

  const values = items.map((item) => Number(valueGetter(item) || 0));
  const total = typeof totalValue === "number" ? totalValue : values.reduce((sum, value) => sum + value, 0);
  if (totalEl) totalEl.textContent = totalFormatter(total);

  host.dataset.chartTooltipInit = "0";
  host.innerHTML = `
    <div class="metric-chart metric-chart--flowbite">
      ${buildChartSvg(hostId, items, values, { tooltipBuilder, valueFormatter })}
    </div>
  `;
  bindMetricChartTooltip(host);
}

function buildActivationSeries(usersSeries, subscriptionsSeries) {
  const subscriptionsByKey = new Map((subscriptionsSeries || []).map((item) => [String(item.key), item]));

  return (usersSeries || []).map((item) => {
    const users = Number(item.count || 0);
    const subscriptions = Number(subscriptionsByKey.get(String(item.key))?.count || 0);
    const rate = users > 0 ? (subscriptions / users) * 100 : 0;
    return {
      key: item.key,
      label: item.label,
      users,
      subscriptions,
      rate,
    };
  });
}

function renderMaintenanceCard(state) {
  const host = q("maintenance_panel");
  if (!host) return;

  const maintenance = state || {};
  const enabled = Boolean(maintenance.enabled);
  const source = maintenance.source ? safeText(maintenance.source) : "—";
  const updatedAt = maintenance.updated_at ? formatDateTime(maintenance.updated_at) : "—";
  const modeLabel = String(maintenance.mode || "").toLowerCase() === "auto" ? "Авто" : "Ручной";
  const toggleLabel = enabled ? "Завершить техработы" : "Запустить техработы";
  const toggleClass = enabled ? "btn-solid-danger" : "btn-outline-success";
  const stateTitle = enabled ? "Сервер на техработах" : "Сервер запущен";
  const stateMessage = enabled
    ? safeText(maintenance.message || "Сервер на технических работах.")
    : "Сервер работает в штатном режиме.";

  host.innerHTML = `
    <div class="maintenance-card ${enabled ? "maintenance-card--enabled" : "maintenance-card--disabled"}">
      <div class="maintenance-card__top">
        <div>
          <div class="maintenance-card__eyebrow">Статус сервера</div>
          <div class="maintenance-card__title">${stateTitle}</div>
        </div>
      </div>
      <div class="maintenance-card__grid">
        <div><span>Режим</span><b>${modeLabel}</b></div>
        <div><span>Источник</span><b>${source}</b></div>
        <div><span>Обновлено</span><b>${updatedAt}</b></div>
      </div>
      <div class="maintenance-card__message">${stateMessage}</div>
      <div class="maintenance-card__actions">
        <button id="maintenance_toggle" class="${toggleClass}" type="button">${toggleLabel}</button>
      </div>
    </div>
  `;

  q("maintenance_toggle")?.addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      await api("/api/admin/system/maintenance", {
        method: "POST",
        body: JSON.stringify(
          enabled
            ? { enabled: false }
            : { enabled: true, message: "Сервер на технических работах." },
        ),
      });
      showToast(enabled ? "Техработы завершены" : "Техработы запущены", "success");
      await loadDashboard();
    });
  });
}

function bindStarsTopupControls() {
  const button = q("stars_invoice_create");
  if (!button) return;

  button.addEventListener("click", async (event) => {
    const amount = Number(q("stars_invoice_amount")?.value || "0");
    if (!Number.isFinite(amount) || amount <= 0) {
      alert("Введите количество Telegram Stars");
      return;
    }

    await withButtonLoading(event.currentTarget, async () => {
      const result = await api("/api/admin/system/stars-invoice", {
        method: "POST",
        body: JSON.stringify({ amount: Math.floor(amount) }),
      });

      const invoiceUrl = result.invoice_url || "";
      q("stars_invoice_result").innerHTML = invoiceUrl
        ? `
          <div class="dashboard-list" style="margin-top:10px">
            <div><span>Инвойс</span><b>${safeText(result.amount)} ⭐</b></div>
            <div><span>Ссылка</span><b><a href="${safeText(invoiceUrl)}" target="_blank" rel="noopener noreferrer">Открыть оплату</a></b></div>
          </div>
        `
        : "Инвойс создан, но ссылка не получена";
      showToast("Stars-инвойс создан", "success");
    }).catch((error) => alert(error.message));
  });
}

async function initDashboardPage() {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "dashboard",
    title: "Обзор",
    subtitle: "Пользователи, подписки, пополнения и состояние системы",
    contentHtml: `
      <div class="dashboard-grid-stats dashboard-grid-stats--strict" id="stats"></div>
      <div class="dashboard-layout dashboard-overview-grid">
        <div class="card dashboard-card dashboard-section-card">
          <div class="dashboard-section-card__head">
            <div>
              <div class="dashboard-section-card__eyebrow">Сводка</div>
              <h3>Общее состояние системы</h3>
            </div>
          </div>
          <div id="quick">Загрузка...</div>
        </div>
      </div>
      <div class="card dashboard-card dashboard-section-card">
        <div class="dashboard-section-card__head">
          <div>
            <div class="dashboard-section-card__eyebrow">Telegram Stars</div>
            <h3>Пополнение баланса бота</h3>
          </div>
        </div>
        <div class="toolbar">
          <input id="stars_invoice_amount" type="number" min="1" step="1" value="100" placeholder="Количество Stars" />
          <button id="stars_invoice_create" class="btn-primary" type="button">Создать инвойс</button>
        </div>
        <div id="stars_invoice_result"></div>
      </div>
      <div class="dashboard-charts-grid">
        ${chartCardHtml({
          prefix: "payments_chart",
          title: "Выручка по периодам",
          subtitle: "Загрузка...",
          controls: `
            <div id="payments_chart_periods" class="chart-periods">
              <button class="chart-period is-active" data-period="14d" type="button">14 дней</button>
              <button class="chart-period" data-period="30d" type="button">30 дней</button>
              <button class="chart-period" data-period="12m" type="button">12 месяцев</button>
            </div>
          `,
        })}
        ${chartCardHtml({
          prefix: "new_users_chart",
          title: "Новые пользователи",
          subtitle: "Загрузка...",
        })}
        ${chartCardHtml({
          prefix: "subscriptions_chart",
          title: "Покупки подписок",
          subtitle: "Загрузка...",
        })}
        ${chartCardHtml({
          prefix: "activation_chart",
          title: "Конверсия регистраций",
          subtitle: "Загрузка...",
        })}
      </div>
      <div class="card dashboard-card dashboard-section-card">
        <div class="dashboard-section-card__head">
          <div>
            <div class="dashboard-section-card__eyebrow">Мониторинг</div>
            <h3>Оперативные индикаторы</h3>
          </div>
        </div>
        <div id="signals" class="signals">Загрузка...</div>
      </div>
    `,
  });

  bindStarsTopupControls();
  bindChartPeriodSwitch();
  await loadDashboard();
}
