const BACKEND_URL = window.location.origin;
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

function isTelegramWebApp() {
  const ua = navigator.userAgent || "";
  const hasTelegramObject = !!(tg && tg.initDataUnsafe && tg.initDataUnsafe.user);
  return ua.includes("Telegram") || hasTelegramObject;
}

const IN_TELEGRAM = isTelegramWebApp();

function requestFullScreenIfPossible() {
  try {
    if (tg?.expand) tg.expand();
    if (typeof tg?.requestFullscreen === "function") tg.requestFullscreen();
  } catch {}
}

if (IN_TELEGRAM && tg) {
  try {
    if (typeof tg.ready === "function") tg.ready();
    if (typeof tg.setHeaderColor === "function") tg.setHeaderColor("#0b1020");
    if (typeof tg.setBackgroundColor === "function") tg.setBackgroundColor("#0b1020");

    requestFullScreenIfPossible();
    setTimeout(requestFullScreenIfPossible, 150);
    setTimeout(requestFullScreenIfPossible, 600);

    if (typeof tg.onEvent === "function") {
      tg.onEvent("viewportChanged", () => requestFullScreenIfPossible());
    }
  } catch {}
}

const initData = IN_TELEGRAM && tg ? tg.initData : null;
const initDataUnsafe = IN_TELEGRAM && tg ? tg.initDataUnsafe : null;
const FALLBACK_AVATAR =
  "data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 96 96'%3E%3Cdefs%3E%3ClinearGradient id='g' x1='0' y1='0' x2='1' y2='1'%3E%3Cstop stop-color='%23dce9ff'/%3E%3Cstop offset='1' stop-color='%23c7dbfa'/%3E%3C/linearGradient%3E%3C/defs%3E%3Crect width='96' height='96' rx='48' fill='url(%23g)'/%3E%3Ccircle cx='48' cy='38' r='18' fill='%23556f97'/%3E%3Cpath d='M20 84c4-16 16-24 28-24s24 8 28 24' fill='%23556f97'/%3E%3C/svg%3E";

// ====== DOM refs ======
const appRootEl = document.getElementById("app-root");
const outsideStubEl = document.getElementById("outside-stub");
const toastEl = document.getElementById("message");

function applyTelegramTopInset() {
  try {
    const top = tg?.contentSafeAreaInset?.top ?? tg?.safeAreaInset?.top ?? 18;
    document.documentElement.style.setProperty("--tgTopPad", `${Math.max(12, top)}px`);
  } catch {
    document.documentElement.style.setProperty("--tgTopPad", `18px`);
  }
}

if (!IN_TELEGRAM) {
  if (appRootEl) appRootEl.style.display = "none";
  if (outsideStubEl) outsideStubEl.style.display = "grid";
} else {
  if (outsideStubEl) outsideStubEl.style.display = "none";
  if (appRootEl) appRootEl.style.display = "block";
  applyTelegramTopInset();
}

function hapticTap() { try { tg?.HapticFeedback?.impactOccurred("light"); } catch {} }
function hapticSuccess() { try { tg?.HapticFeedback?.notificationOccurred("success"); } catch {} }
function hapticError() { try { tg?.HapticFeedback?.notificationOccurred("error"); } catch {} }

let toastTimer = null;
function toast(text) {
  if (!toastEl) return;
  if (toastTimer) clearTimeout(toastTimer);
  toastEl.classList.remove("toast--show");
  toastEl.textContent = text || "";
  toastEl.classList.add("toast--show");
  toastTimer = setTimeout(() => toastEl.classList.remove("toast--show"), 2800);
}

let bannedLocked = false;
function showBannedScreen() {
  bannedLocked = true;
  try { tg?.HapticFeedback?.notificationOccurred("error"); } catch {}
  if (appRootEl) appRootEl.style.display = "none";
  if (outsideStubEl) {
    outsideStubEl.style.display = "grid";
    outsideStubEl.innerHTML = `
      <div class="outside__card">
        <div class="outside__icon">🚫</div>
        <div class="outside__title">Вы забанены</div>
        <div class="outside__text">
          Доступ к мини-приложению ограничен.<br/>
          Если вы считаете, что это ошибка — напишите в поддержку.
        </div>
      </div>
    `;
  }
}

function friendlyErrorMessage(raw) {
  const s = String(raw || "").toLowerCase();
  if (s.includes("banned")) return "🚫 Вы забанены";
  if (s.includes("initdata is missing") || s.includes("invalid initdata")) return "Откройте мини-приложение из Telegram-бота.";
  if (s.includes("user not found")) return "Пользователь не найден. Сначала зайдите в бота и зарегистрируйтесь.";
  if (s.includes("not enough balance")) return "Недостаточно средств. Пополните баланс и попробуйте снова.";
  if (s.includes("no active subscription") || s.includes("no_subscription")) return "Подписка не активна. Оформите её в разделе «Тарифы».";
  if (s.includes("no_pending")) return "Нет незавершённых платежей. Если вы оплатили только что — подождите 1–2 минуты и проверьте ещё раз.";
  if (s.includes("platega")) return "Платёжный сервис временно недоступен. Попробуйте чуть позже или напишите в поддержку.";
  if (raw && String(raw).length > 140) return "Что-то пошло не так. Попробуйте ещё раз.";
  return raw || "Неизвестная ошибка";
}

async function apiRequest(path, body = {}) {
  if (!IN_TELEGRAM) throw new Error("Это приложение работает только внутри Telegram");
  if (bannedLocked) throw new Error("🚫 Вы забанены");

  const payload = { initData: initData || null, ...body };

  const res = await fetch(BACKEND_URL + path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }

  if (!res.ok) {
    const detail = data.detail || data.error || text || `HTTP ${res.status}`;
    const msg = friendlyErrorMessage(detail);
    toast(msg);
    if (String(detail || "").toLowerCase().includes("banned")) showBannedScreen();
    throw new Error(msg);
  }

  if (data.error) {
    const msg = friendlyErrorMessage(data.error);
    toast(msg);
    if (String(data.error || "").toLowerCase().includes("banned")) showBannedScreen();
    throw new Error(msg);
  }

  return data;
}

// ====== DOM ======
const homeAvatarEl = document.getElementById("home-avatar");
const homeNameEl = document.getElementById("home-name");
const homeIdEl = document.getElementById("home-id");
const btnCopyId = document.getElementById("btn-copy-id");
const homeBalanceEl = document.getElementById("home-balance");

const subTitleEl = document.getElementById("sub-title");
const subMetaEl = document.getElementById("sub-meta");
const subLinkWrapEl = document.getElementById("sub-link-wrap");
const subLinkEl = document.getElementById("sub-link");
const btnCopySub = document.getElementById("btn-copy-sub");
const btnOpenSub = document.getElementById("btn-open-sub");

const profileAvatarEl = document.getElementById("profile-avatar");
const profileNameEl = document.getElementById("profile-name");
const profileUsernameEl = document.getElementById("profile-username");

const promoInputEl = document.getElementById("promo-input");
const promoApplyBtn = document.getElementById("promo-apply");
const promoHintEl = document.getElementById("promo-hint");

const topupInputEl = document.getElementById("topup-input");
const topupPayBtn = document.getElementById("topup-pay");
const topupHintEl = document.getElementById("topup-hint");
const topupMethodHintEl = document.getElementById("topup-method-hint");

const pmCardBtn = document.getElementById("pm-card");
const pmSbpBtn = document.getElementById("pm-sbp");
const pmCryptoBtn = document.getElementById("pm-crypto");

const txListEl = document.getElementById("tx-list");
const btnCheckPayments = document.getElementById("btn-check-payments");
const btnRefreshTx = document.getElementById("btn-refresh-tx");
const checkHintEl = document.getElementById("check-hint");

const statusTextEl = document.getElementById("status-text");
const plansCardEl = document.getElementById("plans-card");
const plansListEl = document.getElementById("plans-list");

const refLinkEl = document.getElementById("ref-link");
const btnCopyRef = document.getElementById("btn-copy-ref");
const btnOpenRef = document.getElementById("btn-open-ref");

const setupLinkEl = document.getElementById("setup-link");
const btnCopySetup = document.getElementById("btn-copy-setup");
const btnOpenSetup = document.getElementById("btn-open-setup");

const supportTgEl = document.getElementById("support-tg");
const supportMailEl = document.getElementById("support-mail");
const btnOpenSupportTg = document.getElementById("btn-open-support-tg");
const btnCopySupportMail = document.getElementById("btn-copy-support-mail");

const navItems = document.querySelectorAll(".tab");
const viewIds = ["home","profile","transactions","referral","setup","support","tariffs"];
const views = new Map(viewIds.map(id => [id, document.getElementById("view-" + id)]));

function cleanup(el){
  el.classList.remove("view--enter-r","view--enter-l","view--to-center");
}

function waitTransition(el, fallbackMs = 520) {
  return new Promise((resolve) => {
    let done = false;
    const finish = () => {
      if (done) return;
      done = true;
      el.removeEventListener("transitionend", onEnd);
      resolve();
    };
    const onEnd = () => finish();
    el.addEventListener("transitionend", onEnd, { once: true });
    setTimeout(finish, fallbackMs);
  });
}

const ROOT_TABS = ["home", "tariffs", "profile"];
let navStack = ["home"];
let currentView = "home";
let navLocked = false;

function setActiveTab(tab) {
  navItems.forEach((b) => b.classList.toggle("tab--active", b.dataset.tab === tab));
}

async function showView(next, dir = "forward", push = true) {
  if (navLocked) return;
  const prev = currentView;
  if (prev === next) return;

  const prevEl = views.get(prev);
  const nextEl = views.get(next);
  if (!prevEl || !nextEl) return;

  navLocked = true;

  prevEl.classList.remove("view--active");
  cleanup(prevEl);

  cleanup(nextEl);
  nextEl.classList.add("view--active");
  nextEl.classList.add(dir === "back" ? "view--enter-l" : "view--enter-r");

  nextEl.offsetHeight;
  nextEl.classList.add("view--to-center");

  await waitTransition(nextEl);

  cleanup(nextEl);
  currentView = next;
  if (push) navStack.push(next);

  if (ROOT_TABS.includes(next)) setActiveTab(next);
  navLocked = false;
}

function goBack() {
  if (navStack.length <= 1) return;
  if (navLocked) navLocked = false;

  navStack.pop();
  const prev = navStack[navStack.length - 1];
  showView(prev, "back", false);
  onViewEnter(prev);
}

document.querySelectorAll("[data-open]").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.preventDefault(); e.stopPropagation();
    hapticTap();
    const target = btn.dataset.open;
    showView(target, "forward", true);
    onViewEnter(target);
  });
});

document.querySelectorAll("[data-back]").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.preventDefault(); e.stopPropagation();
    hapticTap();
    goBack();
  });
});

navItems.forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.preventDefault(); e.stopPropagation();
    hapticTap();

    const tab = btn.dataset.tab;
    navStack = [tab];
    showView(tab, "back", false);
    onViewEnter(tab);
    setActiveTab(tab);
  });
});

let TG_ID = null;

function initUserUI() {
  if (!IN_TELEGRAM || !initDataUnsafe?.user) return;

  const u = initDataUnsafe.user;
  TG_ID = u.id;

  const name =
    [u.first_name, u.last_name].filter(Boolean).join(" ") ||
    (u.username ? "@" + u.username : `ID: ${u.id}`);

  const photo = u.photo_url ? u.photo_url : FALLBACK_AVATAR;

  if (homeAvatarEl) homeAvatarEl.src = photo;
  if (homeNameEl) homeNameEl.textContent = name;
  if (homeIdEl) homeIdEl.textContent = `ID: ${u.id}`;

  if (profileAvatarEl) profileAvatarEl.src = photo;
  if (profileNameEl) profileNameEl.textContent = name;
  if (profileUsernameEl) profileUsernameEl.textContent = u.username ? "@" + u.username : `ID: ${u.id}`;
}

btnCopyId?.addEventListener("click", async (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (!TG_ID) return;
  try {
    await navigator.clipboard.writeText(String(TG_ID));
    toast("ID скопирован");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать");
    hapticError();
  }
});

let lastSubUrl = null;

async function loadProfileAndBalance() {
  try {
    const data = await apiRequest("/mini/profile");
    const bal = data.user?.balance ?? 0;
    if (homeBalanceEl) homeBalanceEl.textContent = `${bal} ₽`;
    return data;
  } catch {
    return null;
  }
}
