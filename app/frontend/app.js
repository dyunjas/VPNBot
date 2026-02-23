const BACKEND_URL = window.location.origin;
const tg = window.Telegram?.WebApp ?? null;
const IN_TELEGRAM = Boolean(tg?.initDataUnsafe?.user || (navigator.userAgent || "").includes("Telegram"));

const appRoot = document.getElementById("app-root");
const outsideStub = document.getElementById("outside-stub");
const bannedStub = document.getElementById("banned-stub");
const toastEl = document.getElementById("message");
const loaderEl = document.getElementById("app-loader");
const loaderTextEl = document.getElementById("loader-text");

const MIN_WITHDRAW_AMOUNT = 500;

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setLoader(visible, text = "Загружаем данные...") {
  if (!loaderEl) return;
  if (loaderTextEl) loaderTextEl.textContent = text;
  loaderEl.classList.toggle("app-loader--hidden", !visible);
}

function applySafeInsets() {
  if (!IN_TELEGRAM) return;
  const safeTop = Math.max(0, tg?.contentSafeAreaInset?.top ?? tg?.safeAreaInset?.top ?? 0);
  document.documentElement.style.setProperty("--tg-safe-top", `${safeTop}px`);
}

function showBannedScreen() {
  if (appRoot) appRoot.style.display = "none";
  if (outsideStub) outsideStub.style.display = "none";
  if (bannedStub) bannedStub.style.display = "grid";
  setLoader(false);
}

if (!IN_TELEGRAM) {
  if (appRoot) appRoot.style.display = "none";
  if (bannedStub) bannedStub.style.display = "none";
  if (outsideStub) outsideStub.style.display = "grid";
  setLoader(false);
} else {
  tg?.ready?.();
  tg?.expand?.();
  applySafeInsets();
  tg?.onEvent?.("viewportChanged", applySafeInsets);
}

const state = {
  initData: tg?.initData ?? null,
  userId: null,
  subscriptionUrl: null,
  referralUrl: null,
  transactions: [],
  txVisible: 10,
  withdrawals: [],
  withdrawalsVisible: 10,
};

const $ = (id) => document.getElementById(id);

function toast(text) {
  if (!toastEl) return;
  toastEl.textContent = text;
  toastEl.classList.add("toast--show");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => toastEl.classList.remove("toast--show"), 2800);
}

function haptic(kind = "light") {
  try {
    if (kind === "success") tg?.HapticFeedback?.notificationOccurred("success");
    else if (kind === "error") tg?.HapticFeedback?.notificationOccurred("error");
    else tg?.HapticFeedback?.impactOccurred("light");
  } catch {}
}

function friendlyErrorMessage(raw) {
  const s = String(raw || "").toLowerCase();

  if (s.includes("banned")) return "Доступ к мини-приложению ограничен";
  if (s.includes("invalid initdata") || s.includes("initdata is missing")) return "Откройте приложение через Telegram-бота";
  if (s.includes("user not found")) return "Пользователь не найден. Сначала зайдите в бота";
  if (s.includes("not enough referral balance")) return "Недостаточно реферального баланса";
  if (s.includes("not enough balance")) return "Недостаточно средств";
  if (s.includes("subscription not found") || s.includes("active subscription not found")) return "Активная подписка не найдена";
  if (s.includes("device not found")) return "Устройство не найдено";
  if (s.includes("device limit")) return "Достигнут лимит устройств";
  if (s.includes("renewed within 3 days") || s.includes("tooearlytorenew")) {
    return "Продление доступно только за 3 дня до окончания текущей подписки";
  }
  if (s.includes("минимальная сумма вывода")) return String(raw);
  if (s.includes("укажите способ вывода")) return String(raw);

  return raw || "Произошла ошибка";
}

async function api(path, body = {}) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ initData: state.initData, ...body }),
  });

  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }

  if (!res.ok) {
    const rawDetail = data.detail || data.error || `HTTP ${res.status}`;
    const rawStr = String(rawDetail || "").toLowerCase();
    if (res.status === 403 && rawStr.includes("banned")) {
      const err = new Error("BANNED");
      err.code = "BANNED";
      throw err;
    }
    throw new Error(friendlyErrorMessage(rawDetail));
  }
  return data;
}

function switchView(view) {
  document.querySelectorAll(".view").forEach((el) => el.classList.remove("view--active"));
  $(`view-${view}`)?.classList.add("view--active");
  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("tab--active", tab.dataset.tab === view));

  if (view === "plans") loadPlans();
  if (view === "devices") loadDevices();
  if (view === "profile") loadTransactions();
  if (view === "referral") {
    loadReferral();
    loadWithdrawals();
  }
}

function formatDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "-" : d.toLocaleString("ru-RU");
}

function calcDaysLeft(endIso) {
  if (!endIso) return 0;
  const end = new Date(endIso);
  if (Number.isNaN(end.getTime())) return 0;
  const msLeft = end.getTime() - Date.now();
  if (msLeft <= 0) return 0;
  return Math.ceil(msLeft / (24 * 60 * 60 * 1000));
}

function statusBadge(status) {
  const s = String(status || "").toLowerCase();
  if (s === "approved") return '<span class="badge badge--ok">Подтвержден</span>';
  if (s === "rejected") return '<span class="badge badge--bad">Отклонен</span>';
  if (s === "pending") return '<span class="badge badge--wait">Ожидает</span>';
  return '<span class="badge">Неизвестно</span>';
}

async function loadProfile() {
  const data = await api("/mini/profile");
  const user = data.user || {};
  const ref = data.referral || {};
  const tgUser = tg?.initDataUnsafe?.user;

  const name = [tgUser?.first_name, tgUser?.last_name].filter(Boolean).join(" ") || user.username || "Пользователь";
  const photo = tgUser?.photo_url || "https://t.me/i/userpic/320/0.png";

  state.userId = user.tg_id;

  $("home-avatar").src = photo;
  $("home-name").textContent = name;
  $("home-id").textContent = `ID: ${user.tg_id || "-"}`;
  $("home-balance").textContent = `${user.balance || 0} ₽`;

  $("ref-balance").textContent = `${ref.balance || 0} ₽`;
  $("ref-invited").textContent = String(ref.invited_count || 0);
}

async function loadStatus() {
  const data = await api("/mini/status");
  if (!data.has_subscription) {
    $("sub-title").textContent = "Подписка неактивна";
    $("sub-meta").textContent = "Оформите подписку в разделе «Тарифы».\nТрафик: Безлимит";
    $("stat-keys").textContent = "0";
    $("stat-devices").textContent = "0/0";
    $("sub-link-wrap").style.display = "none";
    state.subscriptionUrl = null;
    return;
  }

  const plan = data.plan || {};
  const sub = data.subscription || {};
  const usedDevices = Math.max((sub.devices_limit || 0) - (sub.devices_left || 0), 0);
  const daysLeft = calcDaysLeft(sub.current_period_end);

  $("sub-title").textContent = `Осталось дней: ${daysLeft}`;
  $("sub-meta").textContent = `Действует до: ${formatDate(sub.current_period_end)}\nТрафик: Безлимит`;
  $("stat-keys").textContent = String(data.active_keys || 0);
  $("stat-devices").textContent = `${usedDevices}/${sub.devices_limit || 0}`;

  state.subscriptionUrl = data.subscription_url || null;
  $("sub-link-wrap").style.display = state.subscriptionUrl ? "flex" : "none";
}

async function loadReferral() {
  const data = await api("/mini/referral/info");
  state.referralUrl = data.referral_url || null;
  $("ref-link").textContent = state.referralUrl || "Ссылка недоступна";

  const r = data.referral || {};
  $("ref-extra").textContent = `Процент: ${r.percent || 0}% | Приглашено: ${r.invited_count || 0} | Баланс: ${r.balance || 0} ₽`;
}

function renderPlans(plans) {
  const host = $("plans-list");
  if (!plans.length) {
    host.textContent = "Тарифов пока нет";
    return;
  }

  host.innerHTML = "";
  plans.forEach((plan) => {
    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = `
      <div class="item__title">${plan.name}</div>
      <div class="item__meta">${plan.period_days} дней | ${plan.device_limit || 0} устройств | Трафик: Безлимит</div>
      <div class="row">
        <div class="balance">${plan.price} ₽</div>
        <button class="btn">Купить</button>
      </div>
    `;

    el.querySelector("button").addEventListener("click", async () => {
      haptic();
      try {
        await api("/mini/subscription/buy", { plan_id: plan.id });
        toast("Подписка успешно оформлена");
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
    const data = await api("/mini/plans");
    renderPlans(data.plans || []);
  } catch (e) {
    $("plans-list").textContent = e.message;
  }
}

function renderDevices(items) {
  const host = $("devices-list");
  if (!items.length) {
    host.textContent = "Устройств пока нет";
    return;
  }

  host.innerHTML = "";
  items.forEach((d) => {
    const title = d.device_model || d.hwid || `Устройство #${d.id}`;
    const os = [d.device_os, d.os_version].filter(Boolean).join(" ");
    const seen = formatDate(d.last_seen_at);

    const el = document.createElement("div");
    el.className = "item";
    el.innerHTML = `
      <div class="item__title">${title}</div>
      <div class="item__meta">${os || "ОС не определена"}<br>Последняя активность: ${seen}</div>
      <button class="btn btn--danger" type="button">Удалить</button>
    `;

    el.querySelector("button").addEventListener("click", async () => {
      haptic();
      if (!confirm("Удалить это устройство?")) return;
      try {
        await api("/mini/device/delete", { device_id: d.id });
        toast("Устройство удалено");
        haptic("success");
        await Promise.all([loadDevices(), loadStatus()]);
      } catch (e) {
        toast(e.message);
        haptic("error");
      }
    });

    host.appendChild(el);
  });
}

async function loadDevices() {
  try {
    const [devicesData, statusData] = await Promise.all([
      api("/mini/devices"),
      api("/mini/status"),
    ]);

    const sub = statusData.subscription || {};
    const used = Math.max((sub.devices_limit || 0) - (sub.devices_left || 0), 0);
    $("device-limit").textContent = `Лимит: ${used}/${sub.devices_limit || 0}`;
    renderDevices(devicesData.items || []);
  } catch (e) {
    $("devices-list").textContent = e.message;
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
      moreBtn.textContent = `Загрузить еще +${next}`;
      moreBtn.style.display = "inline-flex";
    } else {
      moreBtn.style.display = "none";
    }
  }
}

async function loadTransactions() {
  try {
    const data = await api("/mini/profile");
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
      moreBtn.textContent = `Загрузить еще +${next}`;
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
    const data = await api("/mini/referral/withdrawals");
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
    const data = await api("/mini/referral/withdraw", { amount: Math.floor(amount), method });
    if (hint) hint.textContent = data.message || "Заявка отправлена";
    toast(data.message || "Заявка на вывод создана");
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

async function applyPromocode() {
  const code = ($("promo-input")?.value || "").trim();
  if (!code) return toast("Введите промокод");

  haptic();
  try {
    const data = await api("/mini/promocode/apply", { code });
    const hint = $("promo-hint");
    if (hint) hint.textContent = `Начислено: +${data.amount_added || 0} ₽`;
    toast("Промокод применен");
    haptic("success");
    await loadProfile();
  } catch (e) {
    const hint = $("promo-hint");
    if (hint) hint.textContent = e.message;
    toast(e.message);
    haptic("error");
  }
}

function getTopupPayload() {
  const method = $("topup-method")?.value || "card";
  if (method === "crypto") return { method: "crypto", asset: "USDT" };
  return { method: "platega", platega_type: method };
}

async function createTopup() {
  const amount = Number(($("topup-input")?.value || "").trim());
  const hint = $("topup-hint");

  if (!Number.isFinite(amount) || amount <= 0) {
    const msg = "Введите корректную сумму";
    if (hint) hint.textContent = msg;
    return toast(msg);
  }

  haptic();
  try {
    const data = await api("/mini/balance/topup", {
      amount: Math.floor(amount),
      ...getTopupPayload(),
    });

    if (!data.payment_url) throw new Error("Ссылка на оплату не получена");

    tg?.openLink?.(data.payment_url);
    if (!tg?.openLink) window.open(data.payment_url, "_blank");

    if (hint) hint.textContent = "После оплаты нажмите «Проверить платежи».";
    toast("Ссылка на оплату открыта");
    haptic("success");
  } catch (e) {
    if (hint) hint.textContent = e.message;
    toast(e.message);
    haptic("error");
  }
}

async function checkPayments() {
  haptic();
  try {
    const data = await api("/mini/balance/check");

    if (!data.ok && data.reason === "no_pending") {
      toast(`Ожидающих платежей нет (проверено: ${data.checked || 0})`);
      return;
    }

    if (data.confirmed) {
      toast(`Платеж подтвержден (проверено: ${data.checked || 1})`);
      haptic("success");
    } else {
      toast(data.message || `Платеж еще не подтвержден (проверено: ${data.checked || 1})`);
    }

    await Promise.all([loadProfile(), loadTransactions()]);
  } catch (e) {
    toast(e.message);
    haptic("error");
  }
}

async function reissueKeys() {
  haptic();
  try {
    const data = await api("/mini/subscription/reissue");
    state.subscriptionUrl = data.subscription_url || state.subscriptionUrl;
    toast("Ключи перевыпущены");
    haptic("success");
    await Promise.all([loadStatus(), loadDevices()]);
  } catch (e) {
    toast(e.message);
    haptic("error");
  }
}

function initEvents() {
  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      haptic();
      switchView(tab.dataset.tab);
    });
  });

  document.querySelectorAll("[data-open]").forEach((btn) => {
    btn.addEventListener("click", () => {
      haptic();
      switchView(btn.dataset.open);
    });
  });

  $("promo-apply")?.addEventListener("click", applyPromocode);
  $("topup-pay")?.addEventListener("click", createTopup);
  $("btn-check-payments")?.addEventListener("click", checkPayments);
  $("btn-refresh-tx")?.addEventListener("click", loadTransactions);
  $("btn-more-tx")?.addEventListener("click", () => {
    state.txVisible += 10;
    renderTransactions(state.transactions);
  });
  $("btn-more-withdraw")?.addEventListener("click", () => {
    state.withdrawalsVisible += 10;
    renderWithdrawals(state.withdrawals);
  });
  $("btn-reissue")?.addEventListener("click", reissueKeys);
  $("btn-withdraw-create")?.addEventListener("click", createWithdrawal);

  $("btn-copy-sub")?.addEventListener("click", async () => {
    if (!state.subscriptionUrl) return toast("Ссылка недоступна");
    await navigator.clipboard.writeText(state.subscriptionUrl);
    toast("Ссылка скопирована");
  });

  $("btn-open-sub")?.addEventListener("click", () => {
    if (!state.subscriptionUrl) return toast("Ссылка недоступна");
    tg?.openLink?.(state.subscriptionUrl);
    if (!tg?.openLink) window.open(state.subscriptionUrl, "_blank");
  });

  $("btn-copy-ref")?.addEventListener("click", async () => {
    if (!state.referralUrl) return toast("Ссылка недоступна");
    await navigator.clipboard.writeText(state.referralUrl);
    toast("Реферальная ссылка скопирована");
  });

  $("btn-open-ref")?.addEventListener("click", () => {
    if (!state.referralUrl) return toast("Ссылка недоступна");
    tg?.openTelegramLink?.(state.referralUrl);
    if (!tg?.openTelegramLink) window.open(state.referralUrl, "_blank");
  });
}

async function bootstrap() {
  try {
    setLoader(true, "Загружаем данные...");
    initEvents();

    await Promise.all([
      loadProfile(),
      loadStatus(),
      loadReferral(),
      loadTransactions(),
      loadWithdrawals(),
      sleep(1500),
    ]);

    switchView("home");
    setLoader(false);
  } catch (e) {
    if (e?.code === "BANNED" || String(e?.message || "").toLowerCase().includes("banned")) {
      showBannedScreen();
      return;
    }
    setLoader(false);
    toast(e.message || "Ошибка загрузки");
  }
}

if (IN_TELEGRAM) bootstrap();

