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

document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
  renderShell({
    activeKey: "dashboard",
    title: "Обзор",
    subtitle: "Пользователи, подписки, транзакции и состояние системы",
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
      <div class="card dashboard-card">
        <div class="dashboard-chart-head">
          <div>
            <h3>График платежей</h3>
            <div id="payments_chart_subtitle" class="section-title">Загрузка...</div>
          </div>
          <div class="dashboard-chart-tools">
            <div id="payments_chart_periods" class="chart-periods">
              <button class="chart-period is-active" data-period="14d" type="button">14 дней</button>
              <button class="chart-period" data-period="30d" type="button">30 дней</button>
              <button class="chart-period" data-period="12m" type="button">12 месяцев</button>
            </div>
            <div id="payments_chart_total" class="dashboard-chart-total">—</div>
          </div>
        </div>
        <div id="payments_chart" class="payments-chart">Загрузка...</div>
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

    renderPaymentsChart(s.payments_chart || [], s.payments_chart_period || dashboardState.chartPeriod);
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

function formatMoney(value) {
  return `${Number(value || 0).toLocaleString("ru-RU")} ₽`;
}

function chartSubtitle(period) {
  if (period === "30d") return "Последние 30 дней по оплаченным пополнениям";
  if (period === "12m") return "Последние 12 месяцев по оплаченным пополнениям";
  return "Последние 14 дней по оплаченным пополнениям";
}

function renderPaymentsChart(items, period) {
  const host = q("payments_chart");
  const totalEl = q("payments_chart_total");
  const subtitleEl = q("payments_chart_subtitle");
  if (!host) return;

  if (subtitleEl) subtitleEl.textContent = chartSubtitle(period);

  if (!Array.isArray(items) || !items.length) {
    host.textContent = "Нет данных по платежам";
    if (totalEl) totalEl.textContent = "0 ₽";
    return;
  }

  const maxAmount = Math.max(...items.map((item) => Number(item.amount || 0)), 1);
  const total = items.reduce((sum, item) => sum + Number(item.amount || 0), 0);
  if (totalEl) totalEl.textContent = formatMoney(total);

  const cols = items.length;
  host.innerHTML = `
    <div class="payments-chart__grid" style="grid-template-columns: repeat(${cols}, minmax(0, 1fr));">
      ${items.map((item) => {
        const amount = Number(item.amount || 0);
        const count = Number(item.count || 0);
        const barHeight = Math.max(10, Math.round((amount / maxAmount) * 132));
        const label = item.label || String(item.key || "");
        return `
          <div class="payments-chart__col">
            <div class="payments-chart__value">${amount ? formatMoney(amount) : "0 ₽"}</div>
            <div class="payments-chart__bar-wrap" title="${safeText(label)} · ${safeText(formatMoney(amount))} · ${safeText(count)} платежей">
              <div class="payments-chart__bar" style="height:${barHeight}px"></div>
            </div>
            <div class="payments-chart__count">${count}</div>
            <div class="payments-chart__label">${label}</div>
          </div>
        `;
      }).join("")}
    </div>
  `;
}
