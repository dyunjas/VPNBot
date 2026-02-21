document.addEventListener("DOMContentLoaded", async () => {
  ensureAuthOrRedirect();
  renderShell({
    activeKey: "dashboard",
    title: "Обзор",
    subtitle: "Пользователи, подписки, транзакции и состояние системы",
    contentHtml: `
      <div class="grid-stats" id="stats"></div>
      <div class="content-grid">
        <div class="card">
          <h3>Сводка системы</h3>
          <div id="quick">Загрузка...</div>
        </div>
        <div class="content-stack">
          <div class="card">
            <h3>Состояние подписок</h3>
            <div id="subHealth">Загрузка...</div>
          </div>
          <div class="card">
            <h3>Состояние платежей</h3>
            <div id="txHealth">Загрузка...</div>
          </div>
        </div>
      </div>
      <div class="card">
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
      ["Активные ключи", s.active_keys || 0],
      ["Серверы", s.total_servers || 0],
      ["Устройства", s.total_devices || 0],
      ["Оплаченные транзакции", s.paid_transactions || 0],
    ];

    q("stats").innerHTML = cards
      .map(([label, val]) => `<div class="stat-card"><div class="stat-label">${label}</div><div class="stat-value">${val}</div></div>`)
      .join("");

    q("quick").innerHTML = `
      <div class="summary-list">
        <div><span>Активные ключи</span><b>${s.active_keys || 0}</b></div>
        <div><span>Забаненные пользователи</span><b>${s.banned_users || 0}</b></div>
        <div><span>Всего устройств</span><b>${s.total_devices || 0}</b></div>
      </div>
    `;

    q("subHealth").innerHTML = `${statusBadge("active")} Активных: ${s.active_subscriptions || 0}`;
    q("txHealth").innerHTML = `${statusBadge("paid")} Оплачено: ${s.paid_transactions || 0}`;
    q("signals").innerHTML = `
      <div class="signal-row"><span>Пользователи</span><b>${s.total_users || 0}</b></div>
      <div class="signal-row"><span>Серверы</span><b>${s.total_servers || 0}</b></div>
      <div class="signal-row"><span>Подписок активных</span><b>${s.active_subscriptions || 0}</b></div>
      <div class="signal-row"><span>Платежей оплачено</span><b>${s.paid_transactions || 0}</b></div>
    `;
  } catch (e) {
    alert(e.message);
  }
});
