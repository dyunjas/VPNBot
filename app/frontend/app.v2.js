const BACKEND_URL = window.__API_BASE_URL || window.location.origin;
const tg = window.Telegram?.WebApp ?? null;
const queryInitData = new URLSearchParams(window.location.search || "").get("initData");
const IN_TELEGRAM = Boolean(tg?.initData || tg?.initDataUnsafe?.user || (navigator.userAgent || "").includes("Telegram"));
const APP_MODE = window.__APP_MODE || (window.location.pathname.startsWith("/cabinet") ? "cabinet" : "miniapp");
const IS_CABINET_PATH = APP_MODE === "cabinet";
const IS_MINIAPP_PATH = !IS_CABINET_PATH;
const CABINET_TOKEN_KEY = "cabinet_access_token";
function getCabinetToken() {
  return localStorage.getItem(CABINET_TOKEN_KEY) || "";
}
const HAS_AUTH_INITDATA = Boolean(tg?.initData || queryInitData);
const CAN_BOOT = HAS_AUTH_INITDATA || (IS_CABINET_PATH && Boolean(getCabinetToken()));

const appRoot = document.getElementById("app-root");
const outsideStub = document.getElementById("outside-stub");
const bannedStub = document.getElementById("banned-stub");
const alertsEl = document.getElementById("alerts");
const bodyEl = document.body;
if (bodyEl) {
  bodyEl.classList.toggle("is-cabinet", IS_CABINET_PATH);
  bodyEl.classList.toggle("is-miniapp", IS_MINIAPP_PATH);
  if (IS_CABINET_PATH) {
    requestAnimationFrame(() => bodyEl.classList.add("menu-ready"));
  }
}
document.title = IS_CABINET_PATH ? "Lunet кабинет" : "Lunet";

let loaderEl = null;
let loaderTextEl = null;
if (IS_MINIAPP_PATH) {
  loaderEl = document.createElement("div");
  loaderEl.id = "app-loader";
  loaderEl.className = "app-loader";
  loaderEl.innerHTML = `<div class="loader-card"><div class="loader-ring"></div><div id="loader-text" class="loader-text">Загружаем данные...</div></div>`;
  document.body.appendChild(loaderEl);
  loaderTextEl = loaderEl.querySelector("#loader-text");
}

const MIN_WITHDRAW_AMOUNT = 500;
["copy","cut","contextmenu","selectstart","dragstart"].forEach((evt) => {
  document.addEventListener(evt, (e) => {
    e.preventDefault();
  }, { passive: false });
});

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setLoader(visible, text = "Загружаем данные...") {
  if (!IS_MINIAPP_PATH || !loaderEl) return;
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

if (!CAN_BOOT) {
  if (appRoot) appRoot.style.display = "none";
  if (bannedStub) bannedStub.style.display = "none";
  if (outsideStub) outsideStub.style.display = "grid";
  if (IS_CABINET_PATH) window.location.replace("/cabinet/login");
  setLoader(false);
} else {
  tg?.ready?.();
  tg?.expand?.();
  applySafeInsets();
  tg?.onEvent?.("viewportChanged", applySafeInsets);
}

const state = {
  initData: tg?.initData || queryInitData || null,
  userId: null,
  subscriptionUrl: null,
  referralUrl: null,
  topupMethod: "card",
  transactions: [],
  txVisible: 10,
  withdrawals: [],
  withdrawalsVisible: 10,
};

function buildCabinetUrl() {
  const url = new URL("https://app.lunetpn.ru/cabinet");
  if (state.initData) {
    url.searchParams.set("initData", state.initData);
  }
  const activeTab = document.querySelector(".tab.tab--active")?.dataset.tab;
  if (activeTab) {
    url.searchParams.set("view", activeTab);
  }
  return url.toString();
}
const FALLBACK_AVATAR = "/miniapp/assets/no-avatar.png";

const $ = (id) => document.getElementById(id);

function applyCanonicalLegalLinks() {
  const terms = $("footer-terms-link");
  const privacy = $("footer-privacy-link");
  const offer = $("footer-offer-link");
  if (terms) terms.href = "https://lunetpn.ru/terms/";
  if (privacy) privacy.href = "https://lunetpn.ru/terms/privacy/";
  if (offer) offer.href = "https://lunetpn.ru/terms/offer/";
}
applyCanonicalLegalLinks();

function toast(text, kind = "error") {
  if (!alertsEl) return;
  const el = document.createElement("div");
  el.className = `alert ${kind === "success" ? "alert-success" : "alert-error"}`;
  el.innerHTML = `<div class="alert__msg"></div><button class="alert__close" type="button" aria-label="Закрыть">×</button>`;
  el.querySelector(".alert__msg").textContent = String(text || "Событие");
  const close = () => {
    el.classList.add("hide");
    setTimeout(() => el.remove(), 180);
  };
  el.querySelector(".alert__close").addEventListener("click", close);
  alertsEl.appendChild(el);
  setTimeout(close, 4200);
}

function toastSuccess(text) {
  toast(text, "success");
}

function setButtonBusy(btn, busy, busyText = "Обработка...") {
  if (!btn) return;
  if (busy) {
    btn.dataset.oldText = btn.textContent;
    btn.textContent = busyText;
    btn.disabled = true;
    return;
  }
  btn.textContent = btn.dataset.oldText || btn.textContent;
  btn.disabled = false;
}

async function flashButtonDone(btn, baseText, doneText = "Обновлено") {
  if (!btn) return;
  btn.classList.add("btn--done");
  btn.textContent = `✓ ${doneText}`;
  await sleep(1100);
  btn.classList.remove("btn--done");
  btn.textContent = baseText;
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
  if (s.includes("payment required") || s === "http 402") return "Недостаточно средств для покупки подписки";
  if (s.includes("invalid initdata") || s.includes("initdata is missing")) return "Мини приложение доступно только в Telegram";
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
  if (
    s.includes("clientconnectordnserror")
    || s.includes("getaddrinfo failed")
    || s.includes("api.telegram.org")
    || s.includes("не удалось подключиться к telegram")
  ) {
    return "Не удалось подключиться к Telegram. Попробуйте позже.";
  }

  return raw || "Произошла ошибка";
}

function normalizeErrorDetail(detail) {
  if (Array.isArray(detail)) {
    const parts = detail
      .map((item) => {
        if (typeof item === "string") return item;
        if (item && typeof item === "object") {
          return item.msg || item.message || item.detail || JSON.stringify(item);
        }
        return String(item || "");
      })
      .filter(Boolean);
    return parts.join("; ");
  }

  if (detail && typeof detail === "object") {
    return detail.msg || detail.message || detail.detail || JSON.stringify(detail);
  }

  return String(detail || "");
}

function getInitialViewFromUrl() {
  const params = new URLSearchParams(window.location.search || "");
  const view = (params.get("view") || "").trim().toLowerCase();
  if (view) return view;
  const hash = (window.location.hash || "").replace(/^#/, "").trim().toLowerCase();
  return hash || "";
}

function escapeHtml(value) {
  return String(value || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

async function api(path, body = {}) {
  const useCabinet = IS_CABINET_PATH && !HAS_AUTH_INITDATA;
  const targetPath = useCabinet ? `/cabinet-api${path.replace(/^\/mini/, "")}` : path;
  const headers = { "Content-Type": "application/json" };
  const payload = useCabinet ? body : { initData: state.initData, ...body };
  const cabinetToken = getCabinetToken();
  if (useCabinet && cabinetToken) headers.Authorization = `Bearer ${cabinetToken}`;
  let res = await fetch(`${BACKEND_URL}${targetPath}`, {
    method: "POST",
    headers,
    credentials: useCabinet ? "include" : "same-origin",
    body: JSON.stringify(payload),
  });

  if (useCabinet && res.status === 401) {
    const refreshRes = await fetch(`${BACKEND_URL}/cabinet-api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refreshRes.ok) {
      const refreshData = await refreshRes.json().catch(() => ({}));
      const nextToken = String(refreshData.access_token || "");
      if (nextToken) {
        localStorage.setItem(CABINET_TOKEN_KEY, nextToken);
        headers.Authorization = `Bearer ${nextToken}`;
        res = await fetch(`${BACKEND_URL}${targetPath}`, {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify(payload),
        });
      }
    }
  }

  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }

  if (!res.ok) {
    const rawDetail = normalizeErrorDetail(data.detail || data.error || `HTTP ${res.status}`);
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
  const current = document.querySelector(".view.view--active");
  const next = $(`view-${view}`);
  if (!next || next === current) return;

  if (current) {
    current.classList.add("view-leave");
    setTimeout(() => {
      current.classList.remove("view--active", "view-leave");
    }, 240);
  }

  next.classList.add("view-enter");
  next.classList.add("view--active");
  setTimeout(() => next.classList.remove("view-enter"), 360);

  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("tab--active", tab.dataset.tab === view));
  document.querySelectorAll(".side-link[data-tab]").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === view));

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

function toNonNegativeInt(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.trunc(n));
}

function formatDevicesCounter(sub, remnawave) {
  const limit = toNonNegativeInt(sub?.devices_limit ?? remnawave?.hwidDeviceLimit);
  const usedFromSub = sub?.devices_used;
  const leftFromSub = sub?.devices_left;
  let used = 0;

  if (usedFromSub !== undefined && usedFromSub !== null) {
    used = toNonNegativeInt(usedFromSub);
  } else if (leftFromSub !== undefined && leftFromSub !== null && limit > 0) {
    used = Math.max(limit - toNonNegativeInt(leftFromSub), 0);
  }

  return {
    used,
    limit,
    text: limit > 0 ? `${used}/${limit}` : `${used}/∞`,
  };
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
  const photo = tgUser?.photo_url || FALLBACK_AVATAR;

  state.userId = user.tg_id;

  $("home-avatar").src = photo;
  $("home-name").textContent = name;
  $("home-id").textContent = `ID: ${user.tg_id || "-"}`;
  $("home-id-copy")?.setAttribute("data-id", String(user.tg_id || ""));
  $("home-balance").textContent = `${user.balance || 0} ₽`;

  $("ref-balance").textContent = `${ref.balance || 0} ₽`;
  $("ref-invited").textContent = String(ref.invited_count || 0);
}

async function loadStatus() {
  const data = await api("/mini/status");
  if (!data.has_subscription) {
    $("sub-title").textContent = "Подписка неактивна";
    $("sub-meta").textContent = "Оформите подписку в разделе «Тарифы».\nТрафик: Безлимит";
    $("sub-link-wrap").style.display = "none";
    state.subscriptionUrl = null;
    return;
  }

  const sub = data.subscription || {};
  const daysLeft = calcDaysLeft(sub.current_period_end);

  $("sub-title").textContent = `Осталось дней: ${daysLeft}`;
  const limitBytes = Number(data?.remnawave?.trafficLimitBytes || 0);
  const usedBytes = Number(data?.remnawave?.usedTrafficBytes || 0);
  const gb = (b) => Math.max(0, b / (1024 ** 3)).toFixed(1);
  const limitText = limitBytes > 0 ? `${gb(limitBytes)} GB` : "Безлимит";
  const usedText = limitBytes > 0 ? `${gb(usedBytes)} / ${limitText}` : "Безлимит";
  $("sub-meta").textContent = `Действует до: ${formatDate(sub.current_period_end)}\nТрафик: ${usedText}`;

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
      <div class="item__meta">${plan.period_days} дней | 3 устройства | Трафик: Безлимит</div>
      <div class="row">
        <div class="balance">${plan.price} ₽</div>
        <button class="btn">Купить</button>
      </div>
    `;

    el.querySelector("button").addEventListener("click", async () => {
      haptic();
      try {
        await api("/mini/subscription/buy", { plan_id: plan.id });
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
        toastSuccess("Устройство удалено");
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
    const devicesCounter = formatDevicesCounter(sub, statusData.remnawave || {});
    $("device-limit").textContent = `Лимит: ${devicesCounter.text}`;
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
      moreBtn.textContent = `Показать еще ${next}`;
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

async function applyPromocode() {
  const code = ($("promo-input")?.value || "").trim();
  if (!code) return toast("Введите промокод");

  haptic();
  try {
    const data = await api("/mini/promocode/apply", { code });
    const hint = $("promo-hint");
    if (hint) hint.textContent = `Начислено: +${data.amount_added || 0} ₽`;
    toastSuccess("Промокод применен");
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
  const method = state.topupMethod || document.querySelector(".pay-method--active")?.dataset.method || "card";
  if (method === "crypto") return { method: "crypto", asset: "USDT" };
  if (method === "pally") return { method: "pally" };
  return { method: "platega", platega_type: method };
}

function initTopupMethodPicker() {
  const buttons = Array.from(document.querySelectorAll("#topup-methods .pay-method"));
  if (!buttons.length) return;

  const setActive = (method) => {
    state.topupMethod = method || "card";
    buttons.forEach((btn) => {
      btn.classList.toggle("pay-method--active", btn.dataset.method === state.topupMethod);
    });
  };

  const current = buttons.find((btn) => btn.classList.contains("pay-method--active"))?.dataset.method || "card";
  setActive(current);

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      haptic();
      setActive(btn.dataset.method);
    });
  });
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
    toastSuccess("Ссылка на оплату открыта");
    haptic("success");
  } catch (e) {
    if (hint) hint.textContent = e.message;
    toast(e.message);
    haptic("error");
  }
}

async function buyTraffic() {
  const input = $("traffic-gb-input");
  const hint = $("traffic-hint");
  const btn = $("btn-buy-traffic");
  const gb = Number((input?.value || "").trim());

  if (!Number.isFinite(gb) || gb <= 0) {
    const msg = "Введите количество ГБ больше 0";
    if (hint) hint.textContent = msg;
    return toast(msg);
  }

  setButtonBusy(btn, true, "Покупка...");
  haptic();
  try {
    const data = await api("/mini/subscription/traffic/buy", { gb: Math.floor(gb) });
    if (input) input.value = "";
    const msg = `Добавлено ${data.gb_added} ГБ, списано ${data.charged} ₽`;
    if (hint) hint.textContent = msg;
    toastSuccess(msg);
    haptic("success");
    await Promise.all([loadStatus(), loadProfile()]);
  } catch (e) {
    if (hint) hint.textContent = e.message;
    toast(e.message);
    haptic("error");
  } finally {
    setButtonBusy(btn, false);
  }
}

async function checkPayments() {
  haptic();
  try {
    const data = await api("/mini/balance/check", getTopupPayload());

    if (!data.ok && data.reason === "no_pending") {
      toast(`Ожидающих платежей нет (проверено: ${data.checked || 0})`);
      return;
    }

    if (data.confirmed) {
      toastSuccess(`Платеж подтвержден (проверено: ${data.checked || 1})`);
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

function initEvents() {
  initTopupMethodPicker();

  document.querySelectorAll(".tab").forEach((tab) => {
    tab.addEventListener("click", () => {
      haptic();
      switchView(tab.dataset.tab);
    });
  });
  document.querySelectorAll(".side-link[data-tab]").forEach((tab) => {
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
  $("btn-buy-traffic")?.addEventListener("click", buyTraffic);
  $("topup-pay")?.addEventListener("click", createTopup);
  $("btn-check-payments")?.addEventListener("click", checkPayments);
  $("btn-refresh-tx")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    const baseText = btn?.textContent || "Обновить";
    setButtonBusy(btn, true, "Обновляем...");
    haptic();
    try {
      await loadTransactions();
      haptic("success");
      await flashButtonDone(btn, baseText);
    } catch {
      toast("Не удалось обновить транзакции");
      haptic("error");
      setButtonBusy(btn, false);
    } finally {
      if (btn && !btn.classList.contains("btn--done")) {
        setButtonBusy(btn, false);
      }
    }
  });
  $("btn-more-tx")?.addEventListener("click", () => {
    state.txVisible += 10;
    renderTransactions(state.transactions);
  });
  $("btn-more-withdraw")?.addEventListener("click", () => {
    state.withdrawalsVisible += 10;
    renderWithdrawals(state.withdrawals);
  });
  $("btn-withdraw-create")?.addEventListener("click", createWithdrawal);
  $("btn-open-support")?.addEventListener("click", () => {
    const supportUrl = "https://t.me/LunetVPNSupport";
    tg?.openTelegramLink?.(supportUrl);
    if (!tg?.openTelegramLink) window.open(supportUrl, "_blank");
  });
  $("footer-support-link")?.addEventListener("click", () => {
    $("btn-open-support")?.click();
  });
  $("home-id-copy")?.addEventListener("click", async () => {
    const rawId = $("home-id-copy")?.getAttribute("data-id") || "";
    if (!rawId) {
      toast("ID пользователя недоступен");
      return;
    }
    try {
      await navigator.clipboard.writeText(rawId);
      toastSuccess("ID скопирован");
    } catch {
      toast("Не удалось скопировать ID");
    }
  });
  const closeMobileMenu = () => {
    if (!IS_CABINET_PATH) return;
    document.body.classList.remove("menu-open");
  };
  $("mobile-menu-toggle")?.addEventListener("click", () => {
    if (!IS_CABINET_PATH) return;
    document.body.classList.toggle("menu-open");
  });
  $("sidebar-close")?.addEventListener("click", closeMobileMenu);
  $("mobile-menu-backdrop")?.addEventListener("click", closeMobileMenu);
  document.querySelectorAll(".side-link[data-tab]").forEach((btn) => {
    btn.addEventListener("click", closeMobileMenu);
  });
  $("btn-open-web")?.addEventListener("click", () => {
    const cabinetUrl = buildCabinetUrl();
    tg?.openLink?.(cabinetUrl);
    if (!tg?.openLink) window.open(cabinetUrl, "_blank");
  });
  $("btn-open-telegram")?.addEventListener("click", () => {
    const botUrl = "https://t.me/LunetVPNBot?startapp=cabinet";
    tg?.openTelegramLink?.(botUrl);
    if (!tg?.openTelegramLink) window.open(botUrl, "_blank");
  });
  $("btn-cabinet-logout")?.addEventListener("click", async () => {
    if (!IS_CABINET_PATH) return;
    try {
      await fetch(`${BACKEND_URL}/cabinet-api/auth/logout`, { method: "POST", credentials: "include" });
    } catch {}
    localStorage.removeItem(CABINET_TOKEN_KEY);
    window.location.replace("/cabinet/login");
  });

  $("btn-copy-sub")?.addEventListener("click", async () => {
    if (!state.subscriptionUrl) return toast("Ссылка недоступна");
    await navigator.clipboard.writeText(state.subscriptionUrl);
    toastSuccess("Ссылка скопирована");
  });

  $("btn-open-sub")?.addEventListener("click", () => {
    if (!state.subscriptionUrl) return toast("Ссылка недоступна");
    tg?.openLink?.(state.subscriptionUrl);
    if (!tg?.openLink) window.open(state.subscriptionUrl, "_blank");
  });

  $("btn-copy-ref")?.addEventListener("click", async () => {
    if (!state.referralUrl) return toast("Ссылка недоступна");
    await navigator.clipboard.writeText(state.referralUrl);
    toastSuccess("Реферальная ссылка скопирована");
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

    const initialView = getInitialViewFromUrl();
    const allowedViews = new Set(["home", "plans", "devices", "profile", "referral"]);
    switchView(allowedViews.has(initialView) ? initialView : "home");
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

if (CAN_BOOT) bootstrap();

