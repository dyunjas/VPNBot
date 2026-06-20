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
  const maxValue = Math.max(...values, 1);
  const total = typeof totalValue === "number" ? totalValue : values.reduce((sum, value) => sum + value, 0);

  if (totalEl) totalEl.textContent = totalFormatter(total);

  host.innerHTML = `
    <div class="payments-chart__grid" style="grid-template-columns: repeat(${items.length}, minmax(0, 1fr));">
      ${items
        .map((item, index) => {
          const value = Number(values[index] || 0);
          const barHeight = Math.max(10, Math.round((value / maxValue) * 132));
          const label = String(item.label || item.key || "");
          const tooltip = tooltipBuilder ? tooltipBuilder(item, value) : `${label} · ${valueFormatter(value)}`;
          const countBlock = showCountBelow
            ? `<div class="payments-chart__count">${countFormatter(item.count || 0)}</div>`
            : "";

          return `
            <div class="payments-chart__col">
              <div class="payments-chart__value">${valueFormatter(value)}</div>
              <div class="payments-chart__bar-wrap" title="${safeText(tooltip)}">
                <div class="payments-chart__bar" style="height:${barHeight}px"></div>
              </div>
              ${countBlock}
              <div class="payments-chart__label">${safeText(label)}</div>
            </div>
          `;
        })
        .join("")}
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
      showCountBelow: true,
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
