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
        <h3>Оперативные индикаторы</h3>
        <div id="signals" class="signals">Загрузка...</div>
      </div>
    `,
  });

  try {
    await renderSessionInfo();
    const data = await api("/admin-api/stats");
    const s = data.stats || {};

    const cards = [
      ["Пользователи", s.total_users || 0],
      ["Забаненные", s.banned_users || 0],
      ["Активные подписки", s.active_subscriptions || 0],
      ["Оплаченные транзакции", s.paid_transactions || 0],
    ];

    q("stats").innerHTML = cards
      .map(([label, val]) => `
        <div class="stat-card dashboard-stat-card">
          <div class="stat-label">${label}</div>
          <div class="stat-value">${val}</div>
        </div>
      `)
      .join("");

    q("quick").innerHTML = `
      <div class="summary-list">
        <div><span>Пользователи в системе</span><b>${s.total_users || 0}</b></div>
        <div><span>Забаненные пользователи</span><b>${s.banned_users || 0}</b></div>
        <div><span>Активные подписки</span><b>${s.active_subscriptions || 0}</b></div>
        <div><span>Оплаченные транзакции</span><b>${s.paid_transactions || 0}</b></div>
      </div>
    `;

    q("health").innerHTML = `
      <div class="summary-list">
        <div><span>Подписки</span><b>${statusBadge("active")} Активных: ${s.active_subscriptions || 0}</b></div>
        <div><span>Платежи</span><b>${statusBadge("paid")} Оплачено: ${s.paid_transactions || 0}</b></div>
        <div><span>Модерация</span><b>${statusBadge("warn")} Заблокировано: ${s.banned_users || 0}</b></div>
      </div>
    `;

    q("signals").innerHTML = `
      <div class="signal-row"><span>Пользователи</span><b>${s.total_users || 0}</b></div>
      <div class="signal-row"><span>Подписок активных</span><b>${s.active_subscriptions || 0}</b></div>
      <div class="signal-row"><span>Платежей оплачено</span><b>${s.paid_transactions || 0}</b></div>
      <div class="signal-row"><span>Пользователей в бане</span><b>${s.banned_users || 0}</b></div>
    `;
  } catch (e) {
    alert(e.message);
  }
});
