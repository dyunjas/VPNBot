async function loadDashboard() {
  const chartHost = q("payments_chart");
  if (chartHost) chartHost.textContent = "Загрузка...";

  try {
    await renderSessionInfo();
    const [data, maintenanceData] = await Promise.all([
      api(`/api/admin/stats?chart_period=${encodeURIComponent(dashboardState.chartPeriod)}`),
      api("/api/admin/system/maintenance"),
    ]);
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
        <div class="stat-card dashboard-stat-card dashboard-stat-card--strict">
          <div class="stat-icon dashboard-stat-icon">${dashboardIcon(icon)}</div>
          <div class="stat-copy">
            <div class="stat-label">${safeText(label)}</div>
            <div class="stat-value">${safeText(val)}</div>
          </div>
        </div>
      `)
      .join("");

    q("quick").innerHTML = `
      <div class="dashboard-list">
        <div><span>Пользователи в системе</span><b>${s.total_users || 0}</b></div>
        <div><span>Забаненные пользователи</span><b>${s.banned_users || 0}</b></div>
        <div><span>Активные подписки</span><b>${s.active_subscriptions || 0}</b></div>
        <div><span>Оплаченные транзакции</span><b>${s.paid_transactions || 0}</b></div>
        <div><span>Пополнений за текущий месяц</span><b>${s.month_revenue || 0} ₽</b></div>
      </div>
    `;

    q("health").innerHTML = `
      <div class="dashboard-list dashboard-list--statuses">
        <div><span>Подписки</span><b>Активных: ${s.active_subscriptions || 0}</b></div>
        <div><span>Платежи</span><b>Оплачено: ${s.paid_transactions || 0}</b></div>
        <div><span>Оборот</span><b>За месяц: ${s.month_revenue || 0} ₽</b></div>
        <div><span>Модерация</span><b>Заблокировано: ${s.banned_users || 0}</b></div>
      </div>
    `;

    q("signals").innerHTML = `
      <div class="dashboard-signals-grid">
        <div class="signal-row"><span>Пользователи</span><b>${s.total_users || 0}</b></div>
        <div class="signal-row"><span>Подписок активных</span><b>${s.active_subscriptions || 0}</b></div>
        <div class="signal-row"><span>Платежей оплачено</span><b>${s.paid_transactions || 0}</b></div>
        <div class="signal-row"><span>Оборот за месяц</span><b>${s.month_revenue || 0} ₽</b></div>
        <div class="signal-row"><span>Пользователей в бане</span><b>${s.banned_users || 0}</b></div>
      </div>
    `;

    renderMaintenanceCard(maintenanceData.maintenance || {});

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
      tooltipBuilder: (item, value) => `${item.label} • ${formatMoney(value)} • ${Number(item.count || 0)} платежей`,
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
      tooltipBuilder: (item, value) => `${item.label} • ${formatNumber(value)} новых пользователей`,
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
      tooltipBuilder: (item, value) => `${item.label} • ${formatNumber(value)} купленных подписок`,
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
      tooltipBuilder: (item, value) => `${item.label} • ${formatPercent(value)} • ${item.subscriptions} / ${item.users}`,
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
