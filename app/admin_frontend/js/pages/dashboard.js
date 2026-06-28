const dashboardState = {
  chartPeriod: "14d",
};

function dashboardIcon(kind) {
  const icons = {
    users: "<circle cx='12' cy='8.5' r='3'/><path d='M5.5 18c1-3 3.7-4.7 6.5-4.7s5.5 1.7 6.5 4.7'/><path d='M18.5 11.5c1 .1 1.8.9 1.8 1.9s-.8 1.8-1.8 1.9'/>",
    banned: "<circle cx='12' cy='12' r='7.25'/><path d='M8.5 8.5l7 7M15.5 8.5l-7 7'/><path d='M12 4.75v2.5M12 16.75v2.5M4.75 12h2.5M16.75 12h2.5'/>",
    subs: "<path d='M5.5 8h13v8h-13z'/><path d='M8 6v4M16 6v4M8 12h8'/><path d='M9 15h5'/>",
    paid: "<rect x='5.5' y='7' width='13' height='10' rx='2'/><path d='M5.5 11h13'/><path d='M8 15h3'/>",
    revenue: "<circle cx='12' cy='12' r='7'/><path d='M12 8v8'/><path d='M9.5 10.2c0-1.1 1.1-2 2.5-2s2.5.9 2.5 2-.9 1.7-2.5 2.2-2.5 1.2-2.5 2.3 1.1 2 2.5 2 2.5-.9 2.5-2'/>",
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
    <div class="card dashboard-card dashboard-chart-card">
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

function chartPointPath(points) {
  if (!points.length) return "";
  return points.map((point, index) => `${index === 0 ? "M" : "L"} ${point.x} ${point.y}`).join(" ");
}

function buildChartSvg(chartId, items, values, options = {}) {
  const width = 920;
  const height = 240;
  const padding = { top: 18, right: 14, bottom: 42, left: 18 };
  const innerWidth = width - padding.left - padding.right;
  const innerHeight = height - padding.top - padding.bottom;
  const maxValue = Math.max(...values, 1);
  const minValue = options.minValue || 0;
  const denominator = Math.max(maxValue - minValue, 1);
  const step = items.length > 1 ? innerWidth / (items.length - 1) : 0;

  const points = items.map((item, index) => {
    const value = Number(values[index] || 0);
    const ratio = Math.max(0, Math.min(1, (value - minValue) / denominator));
    return {
      x: Number((padding.left + step * index).toFixed(1)),
      y: Number((padding.top + innerHeight - ratio * innerHeight).toFixed(1)),
      value,
    };
  });

  const linePath = chartPointPath(points);
  const areaPath = points.length
    ? `${linePath} L ${points[points.length - 1].x} ${padding.top + innerHeight} L ${points[0].x} ${padding.top + innerHeight} Z`
    : "";

  const gridLines = [0, 0.25, 0.5, 0.75, 1]
    .map((ratio) => {
      const y = padding.top + innerHeight - ratio * innerHeight;
      return `<line x1="${padding.left}" y1="${y.toFixed(1)}" x2="${width - padding.right}" y2="${y.toFixed(1)}" />`;
    })
    .join("");

  const xLabels = points
    .map((point, index) => {
      const item = items[index];
      const label = String(item.label || item.key || "");
      return `<text x="${point.x}" y="${height - 14}" text-anchor="middle">${safeText(label)}</text>`;
    })
    .join("");

  const markers = points
    .map((point, index) => {
      const item = items[index];
      const tooltip = options.tooltipBuilder ? options.tooltipBuilder(item, point.value) : `${item.label || item.key || ""}`;
      const r = index === points.length - 1 ? 5.5 : 4.5;
      return `
        <g class="metric-chart__point" data-index="${index}">
          <circle class="metric-chart__point-halo" cx="${point.x}" cy="${point.y}" r="${(r + 5).toFixed(1)}"></circle>
          <circle class="metric-chart__point-dot" cx="${point.x}" cy="${point.y}" r="${r}"></circle>
          <title>${safeText(tooltip)}</title>
        </g>
      `;
    })
    .join("");

  const gradientAreaId = `metric-area-gradient-${chartId}`;
  const gradientLineId = `metric-line-gradient-${chartId}`;

  return `
    <svg class="metric-chart__svg" viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" aria-hidden="true">
      <defs>
        <linearGradient id="${gradientAreaId}" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stop-color="#1f6feb" stop-opacity="0.28" />
          <stop offset="100%" stop-color="#1f6feb" stop-opacity="0.02" />
        </linearGradient>
        <linearGradient id="${gradientLineId}" x1="0" y1="0" x2="1" y2="0">
          <stop offset="0%" stop-color="#5ca0ff" />
          <stop offset="100%" stop-color="#1f6feb" />
        </linearGradient>
      </defs>
      <rect x="0" y="0" width="${width}" height="${height}" rx="18" fill="#fbfdff" />
      <g class="metric-chart__grid">${gridLines}</g>
      ${areaPath ? `<path class="metric-chart__area" style="fill:url(#${gradientAreaId})" d="${areaPath}"></path>` : ""}
      ${linePath ? `<path class="metric-chart__line" style="stroke:url(#${gradientLineId})" d="${linePath}"></path>` : ""}
      ${markers}
      <g class="metric-chart__axis">${xLabels}</g>
    </svg>
  `;
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

  host.innerHTML = `
    <div class="metric-chart">
      ${buildChartSvg(hostId, items, values, { tooltipBuilder })}
      ${buildMetricLegend(
        items,
        valueGetter,
        valueFormatter,
        legendMetaBuilder || ((item) => {
          if (showCountBelow) return `${countFormatter(item.count || 0)} записей`;
          return "";
        }),
      )}
    </div>
  `;
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

document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
  renderShell({
    activeKey: "dashboard",
    title: "Обзор",
    subtitle: "Пользователи, подписки, пополнения и состояние системы",
    contentHtml: `
      <div class="dashboard-grid-stats" id="stats"></div>
      <div class="dashboard-layout">
        <div class="card dashboard-card">
          <h3>Сводка системы</h3>
          <div id="quick">Загрузка...</div>
        </div>
        <div class="card dashboard-card">
          <h3>Ключевые статусы</h3>
          <div id="health">Загрузка...</div>
        </div>
      </div>
      <div class="dashboard-charts-grid">
        ${chartCardHtml({
          prefix: "payments_chart",
          title: "График платежей",
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
          title: "Купленные подписки",
          subtitle: "Загрузка...",
        })}
        ${chartCardHtml({
          prefix: "activation_chart",
          title: "Конверсия в подписку",
          subtitle: "Загрузка...",
        })}
      </div>
      <div class="card dashboard-card">
        <h3>Оперативные индикаторы</h3>
        <div id="signals" class="signals">Загрузка...</div>
      </div>
    `,
  });

  bindChartPeriodSwitch();
  await loadDashboard();
});

async function loadDashboard() {
  const chartHost = q("payments_chart");
  if (chartHost) chartHost.textContent = "Загрузка...";

  try {
    await renderSessionInfo();
    const data = await api(`/admin-api/stats?chart_period=${encodeURIComponent(dashboardState.chartPeriod)}`);
    const s = data.stats || {};

    const cards = [
      ["Пользователи", s.total_users || 0, "users"],
      ["Забаненные", s.banned_users || 0, "banned"],
      ["Активные подписки", s.active_subscriptions || 0, "subs"],
      ["Оплаченные транзакции", s.paid_transactions || 0, "paid"],
      ["Оборот за месяц", `${s.month_revenue || 0} ₽`, "revenue"],
    ];

    q("stats").innerHTML = cards
      .map(([label, val, icon]) => `
        <div class="stat-card dashboard-stat-card">
          <div class="stat-icon">${dashboardIcon(icon)}</div>
          <div class="stat-copy">
            <div class="stat-label">${safeText(label)}</div>
            <div class="stat-value">${safeText(val)}</div>
          </div>
        </div>
      `)
      .join("");

    q("quick").innerHTML = `
      <div class="summary-list">
        <div><span>Пользователи в системе</span><b>${s.total_users || 0}</b></div>
        <div><span>Забаненные пользователи</span><b>${s.banned_users || 0}</b></div>
        <div><span>Активные подписки</span><b>${s.active_subscriptions || 0}</b></div>
        <div><span>Оплаченные транзакции</span><b>${s.paid_transactions || 0}</b></div>
        <div><span>Пополнений за текущий месяц</span><b>${s.month_revenue || 0} ₽</b></div>
      </div>
    `;

    q("health").innerHTML = `
      <div class="summary-list">
        <div><span>Подписки</span><b>${statusBadge("active")} Активных: ${s.active_subscriptions || 0}</b></div>
        <div><span>Платежи</span><b>${statusBadge("paid")} Оплачено: ${s.paid_transactions || 0}</b></div>
        <div><span>Оборот</span><b>${statusBadge("ok")} За месяц: ${s.month_revenue || 0} ₽</b></div>
        <div><span>Модерация</span><b>${statusBadge("warn")} Заблокировано: ${s.banned_users || 0}</b></div>
      </div>
    `;

    q("signals").innerHTML = `
      <div class="signal-row"><span>Пользователи</span><b>${s.total_users || 0}</b></div>
      <div class="signal-row"><span>Подписок активных</span><b>${s.active_subscriptions || 0}</b></div>
      <div class="signal-row"><span>Платежей оплачено</span><b>${s.paid_transactions || 0}</b></div>
      <div class="signal-row"><span>Оборот за месяц</span><b>${s.month_revenue || 0} ₽</b></div>
      <div class="signal-row"><span>Пользователей в бане</span><b>${s.banned_users || 0}</b></div>
    `;

    const paymentsSeries = s.payments_chart || [];
    const usersSeries = s.users_chart || [];
    const subscriptionsSeries = s.subscriptions_chart || [];
    const activationSeries = buildActivationSeries(usersSeries, subscriptionsSeries);

    renderMetricChart({
      hostId: "payments_chart",
      totalId: "payments_chart_total",
      subtitleId: "payments_chart_subtitle",
      period: dashboardState.chartPeriod,
      items: paymentsSeries,
      valueGetter: (item) => Number(item.amount || 0),
      valueFormatter: formatMoney,
      totalFormatter: formatMoney,
      countFormatter: formatNumber,
      tooltipBuilder: (item, value) => `${item.label} · ${formatMoney(value)} · ${Number(item.count || 0)} платежей`,
      showCountBelow: false,
      legendMetaBuilder: (item) => `${formatNumber(item.count || 0)} платежей`,
    });

    renderMetricChart({
      hostId: "new_users_chart",
      totalId: "new_users_chart_total",
      subtitleId: "new_users_chart_subtitle",
      period: dashboardState.chartPeriod,
      items: usersSeries,
      valueGetter: (item) => Number(item.count || 0),
      valueFormatter: formatNumber,
      totalFormatter: formatNumber,
      tooltipBuilder: (item, value) => `${item.label} · ${formatNumber(value)} новых пользователей`,
      legendMetaBuilder: (item) => `${formatNumber(item.count || 0)} регистраций`,
    });

    renderMetricChart({
      hostId: "subscriptions_chart",
      totalId: "subscriptions_chart_total",
      subtitleId: "subscriptions_chart_subtitle",
      period: dashboardState.chartPeriod,
      items: subscriptionsSeries,
      valueGetter: (item) => Number(item.count || 0),
      valueFormatter: formatNumber,
      totalFormatter: formatNumber,
      tooltipBuilder: (item, value) => `${item.label} · ${formatNumber(value)} купленных подписок`,
      legendMetaBuilder: (item) => `${formatNumber(item.count || 0)} подписок`,
    });

    const totalActivationUsers = usersSeries.reduce((sum, item) => sum + Number(item.count || 0), 0);
    const totalActivationSubs = subscriptionsSeries.reduce((sum, item) => sum + Number(item.count || 0), 0);
    const totalActivationRate = totalActivationUsers > 0 ? (totalActivationSubs / totalActivationUsers) * 100 : 0;

    renderMetricChart({
      hostId: "activation_chart",
      totalId: "activation_chart_total",
      subtitleId: "activation_chart_subtitle",
      period: dashboardState.chartPeriod,
      items: activationSeries,
      valueGetter: (item) => Number(item.rate || 0),
      valueFormatter: formatPercent,
      totalFormatter: formatPercent,
      totalValue: totalActivationRate,
      tooltipBuilder: (item, value) => `${item.label} · ${formatPercent(value)} · ${item.subscriptions} / ${item.users}`,
      legendMetaBuilder: (item) => `${item.subscriptions} / ${item.users}`,
    });

    syncChartPeriodButtons();
  } catch (e) {
    alert(e.message);
  }
}

function bindChartPeriodSwitch() {
  document.querySelectorAll(".chart-period").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const nextPeriod = btn.dataset.period || "14d";
      if (nextPeriod === dashboardState.chartPeriod) return;
      dashboardState.chartPeriod = nextPeriod;
      syncChartPeriodButtons();
      await withButtonLoading(btn, async () => {
        await loadDashboard();
      });
    });
  });
}

function syncChartPeriodButtons() {
  document.querySelectorAll(".chart-period").forEach((btn) => {
    btn.classList.toggle("is-active", btn.dataset.period === dashboardState.chartPeriod);
  });
}
