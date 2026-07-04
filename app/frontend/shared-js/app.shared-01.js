const BACKEND_URL = window.__API_BASE_URL || window.location.origin;
const tg = window.Telegram?.WebApp ?? null;
const queryInitData = new URLSearchParams(window.location.search || "").get("initData");
const IN_TELEGRAM = Boolean(
  tg?.initData || tg?.initDataUnsafe?.user || (navigator.userAgent || "").includes("Telegram"),
);
const APP_MODE = window.__SURFACE || "cabinet";
const IS_CABINET_PATH = APP_MODE === "cabinet";
const IS_MINIAPP_PATH = APP_MODE === "miniapp";
const CABINET_TOKEN_KEY = "cabinet_access_token";

function getCabinetToken() {
  return localStorage.getItem(CABINET_TOKEN_KEY) || "";
}

const HAS_AUTH_INITDATA = Boolean(tg?.initData || queryInitData);
const CAN_BOOT = HAS_AUTH_INITDATA || (IS_CABINET_PATH && Boolean(getCabinetToken()));

const appRoot = document.getElementById("app-root");
const outsideStub = document.getElementById("outside-stub");
const bannedStub = document.getElementById("banned-stub");
const unavailableStub = document.getElementById("unavailable-stub");
const alertsEl = document.getElementById("alerts");
const unavailableTitleEl = unavailableStub?.querySelector(".outside__title") ?? null;
const unavailableTextEl = unavailableStub?.querySelector("p") ?? null;
const bodyEl = document.body;

if (bodyEl) {
  bodyEl.classList.toggle("is-cabinet", IS_CABINET_PATH);
  bodyEl.classList.toggle("is-miniapp", IS_MINIAPP_PATH);
  bodyEl.classList.add("app-booting");
  if (IS_CABINET_PATH) {
    requestAnimationFrame(() => bodyEl.classList.add("menu-ready"));
  }
}

document.title = IS_CABINET_PATH ? "Lunet Кабинет" : "Lunet";

let loaderEl = null;
let loaderTextEl = null;
if (IS_MINIAPP_PATH) {
  loaderEl = document.createElement("div");
  loaderEl.id = "app-loader";
  loaderEl.className = "app-loader";
  loaderEl.innerHTML =
    '<div class="loader-card"><div class="loader-ring"></div><div id="loader-text" class="loader-text">Загружаем данные...</div></div>';
  document.body.appendChild(loaderEl);
  loaderTextEl = loaderEl.querySelector("#loader-text");
}

const MIN_WITHDRAW_AMOUNT = 500;

["copy", "cut", "contextmenu", "selectstart", "dragstart"].forEach((evt) => {
  document.addEventListener(
    evt,
    (e) => {
      e.preventDefault();
    },
    { passive: false },
  );
});

if (IS_MINIAPP_PATH) {
  document.addEventListener(
    "gesturestart",
    (e) => {
      e.preventDefault();
    },
    { passive: false },
  );
  document.addEventListener(
    "gesturechange",
    (e) => {
      e.preventDefault();
    },
    { passive: false },
  );
  document.addEventListener(
    "gestureend",
    (e) => {
      e.preventDefault();
    },
    { passive: false },
  );
  document.addEventListener(
    "touchmove",
    (e) => {
      if (e.touches && e.touches.length > 1) {
        e.preventDefault();
      }
    },
    { passive: false },
  );
}

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

function setLoader(visible, text = "Загружаем данные...") {
  if (!IS_MINIAPP_PATH || !loaderEl) return;
  if (loaderTextEl) loaderTextEl.textContent = text;
  loaderEl.classList.toggle("app-loader--hidden", !visible);
}

function revealApp() {
  if (!bodyEl) return;
  requestAnimationFrame(() => {
    bodyEl.classList.add("app-ready");
    bodyEl.classList.remove("app-booting");
  });
}

function applySafeInsets() {
  if (!IN_TELEGRAM) return;
  const safeTop = Math.max(0, tg?.contentSafeAreaInset?.top ?? tg?.safeAreaInset?.top ?? 0);
  document.documentElement.style.setProperty("--tg-safe-top", `${safeTop}px`);
}

function syncUnavailableCopy() {
  if (unavailableTitleEl) {
    unavailableTitleEl.textContent = "Сервер не доступен";
  }
  if (unavailableTextEl) {
    unavailableTextEl.textContent = "Идут технические работы. Попробуйте зайти позже.";
  }
}

syncUnavailableCopy();

function showBannedScreen() {
  if (appRoot) appRoot.style.display = "none";
  if (outsideStub) outsideStub.style.display = "none";
  if (bannedStub) bannedStub.style.display = "grid";
  if (unavailableStub) unavailableStub.style.display = "none";
  setLoader(false);
}

function showUnavailableScreen() {
  syncUnavailableCopy();
  if (appRoot) appRoot.style.display = "none";
  if (outsideStub) outsideStub.style.display = "none";
  if (bannedStub) bannedStub.style.display = "none";
  if (unavailableStub) unavailableStub.style.display = "grid";
  setLoader(false);
}

if (!CAN_BOOT) {
  if (appRoot) appRoot.style.display = "none";
  if (bannedStub) bannedStub.style.display = "none";
  if (unavailableStub) unavailableStub.style.display = "none";
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
  lastTopupMethod: null,
  lastTopupProviderId: null,
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
  const title = kind === "success" ? "Готово" : "Ошибка";
  const icon = kind === "success" ? "✓" : "!";
  el.innerHTML = `
    <div class="alert__icon" aria-hidden="true">${icon}</div>
    <div class="alert__body">
      <div class="alert__title"></div>
      <div class="alert__msg"></div>
    </div>
    <button class="alert__close" type="button" aria-label="Закрыть">×</button>
  `;
  el.querySelector(".alert__title").textContent = title;
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
    btn.classList.add("loading");
    btn.classList.toggle("btn--spinner-only", busyText === null);
    if (busyText !== null) {
      btn.textContent = busyText;
    }
    btn.disabled = true;
    return;
  }
  btn.classList.remove("loading", "btn--spinner-only");
  btn.textContent = btn.dataset.oldText || btn.textContent;
  btn.disabled = false;
}

async function flashButtonDone(btn, baseText, doneText = "Обновлено") {
  if (!btn) return;
  btn.classList.remove("loading", "btn--spinner-only");
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
  if (s.includes("http 500") || s.includes("internal server error")) {
    return "Сервер не доступен. Идут технические работы.";
  }
  if (s.includes("banned")) return "Доступ к кабинету ограничен.";
  if (s.includes("payment required") || s === "http 402") {
    return "Недостаточно средств для покупки подписки.";
  }
  if (s.includes("invalid initdata") || s.includes("initdata is missing")) {
    return "Сессия истекла. Откройте кабинет заново.";
  }
  if (s.includes("user not found")) return "Пользователь не найден. Сначала зайдите в бота.";
  if (s.includes("not enough referral balance")) return "Недостаточно реферального баланса.";
  if (s.includes("not enough balance")) return "Недостаточно средств.";
  if (s.includes("subscription not found") || s.includes("active subscription not found")) {
    return "Активная подписка не найдена.";
  }
  if (s.includes("transaction not approved")) return "Платеж еще не подтвержден.";
  if (s.includes("device not found")) return "Устройство не найдено.";
  if (s.includes("device limit")) return "Достигнут лимит устройств.";
  if (s.includes("renewed within 3 days") || s.includes("tooearlytorenew")) {
    return "Продление доступно только за 3 дня до окончания текущей подписки.";
  }
  if (s.includes("минимальная сумма вывода")) return String(raw);
  if (s.includes("укажите способ вывода")) return String(raw);
  if (
    s.includes("clientconnectordnserror") ||
    s.includes("getaddrinfo failed") ||
    s.includes("api.telegram.org") ||
    s.includes("failed to fetch") ||
    s.includes("networkerror") ||
    s.includes("load failed")
  ) {
    return "Не удалось подключиться к серверу. Попробуйте позже.";
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
