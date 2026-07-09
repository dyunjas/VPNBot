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
    const activationSeries = Array.isArray(s.activation_chart) && s.activation_chart.length
      ? s.activation_chart
      : buildActivationSeries(usersSeries, subscriptionsSeries);

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

    const totalActivationUsers = activationSeries.reduce((sum, item) => sum + Number(item.users || 0), 0);
    const totalActivationSubs = activationSeries.reduce((sum, item) => sum + Number(item.subscriptions || 0), 0);
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
        <div class="card dashboard-card dashboard-section-card">
          <div class="dashboard-section-card__head">
            <div>
              <div class="dashboard-section-card__eyebrow">Статусы</div>
              <h3>Ключевые индикаторы</h3>
            </div>
          </div>
          <div id="health">Загрузка...</div>
        </div>
      </div>
      <div class="card dashboard-card dashboard-section-card">
        <div class="dashboard-section-card__head">
          <div>
            <div class="dashboard-section-card__eyebrow">Система</div>
            <h3>Техработы</h3>
          </div>
        </div>
        <div id="maintenance_panel">Загрузка...</div>
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

  bindChartPeriodSwitch();
  await loadDashboard();
}
