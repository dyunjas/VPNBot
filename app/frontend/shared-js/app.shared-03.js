function renderPlans(plans) {
  const host = $("plans-list");
  if (!plans.length) {
    host.textContent = "Тарифов пока нет";
    return;
  }

  host.innerHTML = "";
  plans.forEach((plan) => {
    const isFree = Number(plan.price || 0) <= 0;
    const limitValue = Number(plan.gb_limit || 0);
    const trafficText = limitValue > 0 ? `${limitValue} ГБ` : "Безлимит";
    const el = document.createElement("div");
    el.className = "item plan-card";
    el.innerHTML = `
      <div class="plan-card__head">
        <div class="plan-card__title-wrap">
          <div class="item__title plan-card__title">${plan.name}</div>
          <div class="item__meta plan-card__subtitle">Подписка активируется сразу после оплаты.</div>
        </div>
        <div class="plan-card__price-wrap">
          <div class="plan-card__price">${plan.price} ₽</div>
          <div class="plan-card__price-note">${isFree ? "Бесплатно" : "Единоразовый платеж"}</div>
        </div>
      </div>
      <div class="plan-card__meta-grid">
        <div class="plan-card__meta-chip">
          <span>Период</span>
          <strong>${plan.period_days} дней</strong>
        </div>
        <div class="plan-card__meta-chip">
          <span>Устройства</span>
          <strong>3 устройства</strong>
        </div>
        <div class="plan-card__meta-chip">
          <span>Трафик</span>
          <strong>${trafficText}</strong>
        </div>
      </div>
      <div class="plan-card__footer">
        <button class="btn plan-card__cta">${isFree ? "Активировать" : "Купить"}</button>
      </div>
    `;

    el.querySelector("button").addEventListener("click", async () => {
      haptic();
      try {
        await api("/api/subscription/buy", { plan_id: plan.id });
        toastSuccess("Подписка успешно оформлена");
        haptic("success");
        await Promise.all([loadStatus(), loadProfile(), loadDevices()]);
      } catch (e) {
        toast(e.message);
        haptic("error");
      }
    });

    host.appendChild(el);
  });
}

async function loadPlans() {
  try {
    const host = $("plans-list");
    if (host) {
      host.innerHTML = `
        <div class="item plan-card plan-card--skeleton" aria-hidden="true"></div>
        <div class="item plan-card plan-card--skeleton" aria-hidden="true"></div>
        <div class="item plan-card plan-card--skeleton" aria-hidden="true"></div>
      `;
    }
    const data = await api("/api/plans");
    renderPlans(data.plans || []);
  } catch (e) {
    $("plans-list").textContent = e.message;
  }
}

function deviceIconSvg(osText = "") {
  const os = String(osText || "").toLowerCase();
  if (os.includes("windows")) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M17.8 20l-12 -1.5c-1 -.1 -1.8 -.9 -1.8 -1.9v-9.2c0 -1 .8 -1.8 1.8 -1.9l12 -1.5c1.2 -.1 2.2 .8 2.2 1.9v12.1c0 1.2 -1.1 2.1 -2.2 1.9l0 .1" /><path d="M12 5l0 14" /><path d="M4 12l16 0" /></svg>`;
  }
  if (os.includes("android")) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M4 10l0 6" /><path d="M20 10l0 6" /><path d="M7 9h10v8a1 1 0 0 1 -1 1h-8a1 1 0 0 1 -1 -1v-8a5 5 0 0 1 10 0" /><path d="M8 3l1 2" /><path d="M16 3l-1 2" /><path d="M9 18l0 3" /><path d="M15 18l0 3" /></svg>`;
  }
  if (os.includes("ios") || os.includes("iphone") || os.includes("ipad") || os.includes("apple")) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M8.286 7.008c-3.216 0 -4.286 3.23 -4.286 5.92c0 3.229 2.143 8.072 4.286 8.072c1.165 -.05 1.799 -.538 3.214 -.538c1.406 0 1.607 .538 3.214 .538s4.286 -3.229 4.286 -5.381c-.03 -.011 -2.649 -.434 -2.679 -3.23c-.02 -2.335 2.589 -3.179 2.679 -3.228c-1.096 -1.606 -3.162 -2.113 -3.75 -2.153c-1.535 -.12 -3.032 1.077 -3.75 1.077c-.729 0 -2.036 -1.077 -3.214 -1.077" /><path d="M12 4a2 2 0 0 0 2 -2a2 2 0 0 0 -2 2" /></svg>`;
  }
  if (os.includes("linux") || os.includes("debian")) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M12 17c-2.397 -.943 -4 -3.153 -4 -5.635c0 -2.19 1.039 -3.14 1.604 -3.595c2.646 -2.133 6.396 -.27 6.396 3.23c0 2.5 -2.905 2.121 -3.5 1.5c-.595 -.621 -1 -1.5 -.5 -2.5" /><path d="M3 12a9 9 0 1 0 18 0a9 9 0 1 0 -18 0" /></svg>`;
  }
  if (os.includes("tv") || os.includes("television")) {
    return `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path stroke="none" d="M0 0h24v24H0z" fill="none" /><path d="M3 9a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v9a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2l0 -9" /><path d="M16 3l-4 4l-4 -4" /></svg>`;
  }
  return `<svg viewBox="0 0 24 24" aria-hidden="true"><rect x="6" y="4" width="12" height="16" rx="2.6" /><path d="M9 7.5h6M9 16.5h6" /><circle cx="12" cy="19" r="0.8" /></svg>`;
}

function createDeviceCard(d) {
  const title = d.device_model || d.hwid || `Устройство #${d.id}`;
  const os = [d.device_os, d.os_version].filter(Boolean).join(" ");
  const seen = formatDate(d.last_seen_at);
  const el = document.createElement("div");
  el.className = "item device-card";
  el.innerHTML = `
    <div class="device-card__icon">${deviceIconSvg(os)}</div>
    <div class="device-card__body">
      <div class="device-card__top">
        <div class="device-card__title">${escapeHtml(title)}</div>
      </div>
      <div class="device-card__meta">${escapeHtml(os || "ОС не определена")}</div>
      <div class="device-card__meta">Последняя активность: ${escapeHtml(seen)}</div>
    </div>
    <button class="btn btn--danger device-card__action" type="button">Удалить</button>
  `;

  el.querySelector("button").addEventListener("click", async () => {
    haptic();
    if (!confirm("Удалить это устройство?")) return;
    try {
      await api("/api/device/delete", { device_id: d.id });
      toastSuccess("Устройство удалено");
      haptic("success");
      await Promise.all([loadDevices(), loadStatus()]);
    } catch (e) {
      toast(e.message);
      haptic("error");
    }
  });

  return el;
}

function renderDevices(items) {
  const homeHost = $("home-devices-list");
  const devicesHost = $("devices-list");
  if (homeHost) homeHost.innerHTML = "";
  if (devicesHost) devicesHost.innerHTML = "";

  if (!items.length) {
    if (homeHost) homeHost.textContent = "Устройств пока нет";
    if (devicesHost) devicesHost.textContent = "Устройств пока нет";
    return;
  }

  if (homeHost) homeHost.appendChild(createDeviceCard(items[0]));
  if (devicesHost) {
    items.forEach((d) => {
      devicesHost.appendChild(createDeviceCard(d));
    });
  }

}

async function loadDevices() {
  try {
    if ($("home-devices-list")) $("home-devices-list").innerHTML = renderDeviceSkeleton(1);
    if ($("devices-list")) $("devices-list").innerHTML = renderDeviceSkeleton(3);
    setTextSkeleton(["home-device-limit", "device-limit"], true);
    const timeout = new Promise((_, reject) => {
      setTimeout(() => reject(new Error("Превышено время загрузки устройств")), 12000);
    });
    const devicesPromise = api("/api/devices");
    const statusPromise = api("/api/status").catch(() => null);
    const devicesData = await Promise.race([devicesPromise, timeout]);
    const statusData = await Promise.race([statusPromise, timeout]).catch(() => null);

    if (statusData) {
      const sub = statusData.subscription || {};
      const devicesCounter = formatDevicesCounter(sub, statusData.remnawave || {});
      if ($("home-device-limit")) $("home-device-limit").textContent = devicesCounter.text;
      if ($("device-limit")) $("device-limit").textContent = `Лимит: ${devicesCounter.text}`;
    }
    renderDevices(devicesData.items || []);
    setTextSkeleton(["home-device-limit", "device-limit"], false);
  } catch (e) {
    if ($("home-devices-list")) $("home-devices-list").textContent = "Устройств пока нет";
    if ($("devices-list")) $("devices-list").textContent = "Устройств пока нет";
    if ($("home-device-limit")) $("home-device-limit").textContent = "0/∞";
    if ($("device-limit")) $("device-limit").textContent = "Лимит: 0/∞";
    setTextSkeleton(["home-device-limit", "device-limit"], false);
  }
}

function renderTransactions(items) {
  const host = $("tx-list");
  const moreBtn = $("btn-more-tx");
  if (!items.length) {
    host.textContent = "Транзакций пока нет";
    if (moreBtn) moreBtn.style.display = "none";
    return;
  }

  host.innerHTML = "";
  const shown = items.slice(0, state.txVisible);
  shown.forEach((t) => {
    const el = document.createElement("div");
    el.className = "item";
    const badge = t.paid ? '<span class="badge badge--ok">Оплачено</span>' : '<span class="badge badge--wait">Ожидает</span>';
    el.innerHTML = `
      <div class="item__head">
        <div class="item__title">${t.payment_system || "Операция"} — ${t.amount || 0} ₽</div>
        ${badge}
      </div>
      <div class="item__meta">${formatDate(t.created_at)}</div>
    `;
    host.appendChild(el);
  });

  if (moreBtn) {
    if (state.txVisible < items.length) {
      const next = Math.min(10, items.length - state.txVisible);
      moreBtn.textContent = `Показать еще ${next}`;
      moreBtn.style.display = "inline-flex";
    } else {
      moreBtn.style.display = "none";
    }
  }
}

async function loadTransactions() {
  try {
    const data = await api("/api/profile");
    state.transactions = data.transactions || [];
    state.txVisible = 10;
    renderTransactions(state.transactions);
  } catch (e) {
    $("tx-list").textContent = e.message;
  }
}

function renderWithdrawals(items) {
  const host = $("withdraw-list");
  const moreBtn = $("btn-more-withdraw");
  if (!host) return;

  if (!items.length) {
    host.textContent = "Заявок на вывод пока нет";
    if (moreBtn) moreBtn.style.display = "none";
    return;
  }

  host.innerHTML = "";
  const shown = items.slice(0, state.withdrawalsVisible);
  shown.forEach((w) => {
    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = `
      <div class="item__head">
        <div class="item__title">Заявка #${w.id} — ${w.amount} ₽</div>
        ${statusBadge(w.status)}
      </div>
      <div class="item__meta">${formatDate(w.created_at)}<br>Способ: ${w.method}</div>
    `;
    host.appendChild(el);
  });

  if (moreBtn) {
    if (state.withdrawalsVisible < items.length) {
      const next = Math.min(10, items.length - state.withdrawalsVisible);
      moreBtn.textContent = `Показать еще ${next}`;
      moreBtn.style.display = "inline-flex";
    } else {
      moreBtn.style.display = "none";
    }
  }
}

async function loadWithdrawals() {
  const host = $("withdraw-list");
  if (!host) return;
  try {
    const data = await api("/api/referral/withdrawals");
    state.withdrawals = data.items || [];
    state.withdrawalsVisible = 10;
    renderWithdrawals(state.withdrawals);
  } catch (e) {
    host.textContent = e.message;
  }
}

async function createWithdrawal() {
  const amount = Number(($("withdraw-amount")?.value || "").trim());
  const method = ($("withdraw-method")?.value || "").trim();
  const hint = $("withdraw-hint");

  if (!Number.isFinite(amount) || amount < MIN_WITHDRAW_AMOUNT) {
    const msg = `Минимальная сумма вывода: ${MIN_WITHDRAW_AMOUNT} ₽`;
    if (hint) hint.textContent = msg;
    return toast(msg);
  }

  if (method.length < 8) {
    const msg = "Укажите способ вывода и реквизиты подробнее";
    if (hint) hint.textContent = msg;
    return toast(msg);
  }

  haptic();
  try {
    const data = await api("/api/referral/withdraw", { amount: Math.floor(amount), method });
    if (hint) hint.textContent = data.message || "Заявка отправлена";
    toastSuccess(data.message || "Заявка на вывод создана");
    haptic("success");

    if ($("withdraw-amount")) $("withdraw-amount").value = "";
    if ($("withdraw-method")) $("withdraw-method").value = "";

    await Promise.all([loadWithdrawals(), loadProfile(), loadReferral()]);
  } catch (e) {
    if (hint) hint.textContent = e.message;
    toast(e.message);
    haptic("error");
  }
}
