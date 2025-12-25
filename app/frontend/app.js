const BACKEND_URL = window.location.origin;
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

function isTelegramWebApp() {
  const ua = navigator.userAgent || "";
  const hasTelegramObject = !!(tg && tg.initDataUnsafe && tg.initDataUnsafe.user);
  return ua.includes("Telegram") || hasTelegramObject;
}

const IN_TELEGRAM = isTelegramWebApp();
if (tg && typeof tg.expand === "function") tg.expand();

const initData = IN_TELEGRAM && tg ? tg.initData : null;
const initDataUnsafe = IN_TELEGRAM && tg ? tg.initDataUnsafe : null;

const appRootEl = document.getElementById("app-root");
const outsideStubEl = document.getElementById("outside-stub");
const toastEl = document.getElementById("message");
const stackEl = document.getElementById("stack");

const homeAvatarEl = document.getElementById("home-avatar");
const homeNameEl = document.getElementById("home-name");
const homeIdEl = document.getElementById("home-id");
const btnCopyId = document.getElementById("btn-copy-id");
const homeBalanceEl = document.getElementById("home-balance");

const subBadgeEl = document.getElementById("sub-badge");
const subEmojiEl = document.getElementById("sub-emoji");
const subTitleEl = document.getElementById("sub-title");
const subMetaEl = document.getElementById("sub-meta");
const subLinkWrapEl = document.getElementById("sub-link-wrap");
const subLinkEl = document.getElementById("sub-link");
const btnCopySub = document.getElementById("btn-copy-sub");
const btnOpenSub = document.getElementById("btn-open-sub");

const profileAvatarEl = document.getElementById("profile-avatar");
const profileNameEl = document.getElementById("profile-name");
const profileUsernameEl = document.getElementById("profile-username");
const profilePillEl = document.getElementById("profile-pill");

const promoInputEl = document.getElementById("promo-input");
const promoApplyBtn = document.getElementById("promo-apply");
const promoHintEl = document.getElementById("promo-hint");

const topupInputEl = document.getElementById("topup-input");
const topupBtn = document.getElementById("topup-btn");
const topupHintEl = document.getElementById("topup-hint");

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

const navItems = document.querySelectorAll(".nav-item");

const viewIds = ["home","profile","transactions","referral","setup","support","tariffs"];
const views = new Map(viewIds.map(id => [id, document.getElementById("view-" + id)]));

if (!IN_TELEGRAM) {
  if (appRootEl) appRootEl.style.display = "none";
  if (outsideStubEl) outsideStubEl.style.display = "flex";
} else {
  if (outsideStubEl) outsideStubEl.style.display = "none";
  if (appRootEl) appRootEl.style.display = "block";
}

function hapticTap() { try { tg?.HapticFeedback?.impactOccurred("light"); } catch {} }
function hapticSuccess() { try { tg?.HapticFeedback?.notificationOccurred("success"); } catch {} }
function hapticError() { try { tg?.HapticFeedback?.notificationOccurred("error"); } catch {} }

let toastTimer = null;
function toast(text, kind = "info") {
  if (!toastEl) return;
  if (toastTimer) clearTimeout(toastTimer);

  toastEl.classList.remove("info", "error", "visible");
  toastEl.textContent = text || "";
  toastEl.classList.add(kind === "error" ? "error" : "info", "visible");

  toastTimer = setTimeout(() => toastEl.classList.remove("visible"), 2800);
}

function friendlyErrorMessage(raw) {
  const s = String(raw || "").toLowerCase();

  if (s.includes("initdata is missing") || s.includes("invalid initdata")) {
    return "Откройте мини-приложение из Telegram-бота.";
  }
  if (s.includes("user not found")) {
    return "Пользователь не найден. Сначала зайдите в бота и зарегистрируйтесь.";
  }
  if (s.includes("not enough balance")) {
    return "Недостаточно средств. Пополните баланс и попробуйте снова.";
  }
  if (s.includes("no active subscription") || s.includes("no_subscription")) {
    return "Подписка не активна. Оформите её в разделе «Тарифы».";
  }
  if (s.includes("no_pending")) {
    return "Нет незавершённых платежей. Если вы оплатили только что — подождите 1–2 минуты и проверьте ещё раз.";
  }
  if (s.includes("platega")) {
    return "Платёжный сервис временно недоступен. Попробуйте чуть позже или напишите в поддержку.";
  }

  if (raw && String(raw).length > 140) return "Что-то пошло не так. Попробуйте ещё раз.";
  return raw || "Неизвестная ошибка";
}

async function apiRequest(path, body = {}) {
  if (!IN_TELEGRAM) throw new Error("Это приложение работает только внутри Telegram");

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
    toast(msg, "error");
    throw new Error(msg);
  }
  if (data.error) {
    const msg = friendlyErrorMessage(data.error);
    toast(msg, "error");
    throw new Error(msg);
  }
  return data;
}

let navStack = ["home"];
let currentView = "home";
let navLocked = false;

const ROOT_TABS = ["home", "tariffs", "profile"];

function cleanup(el){
  el.classList.remove("enter-from-right","enter-from-left","enter-to-center");
}

function setActiveTab(tab) {
  navItems.forEach((b) => b.classList.toggle("active", b.dataset.tab === tab));
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

async function showView(next, dir = "forward", push = true) {
  if (navLocked) return;
  const prev = currentView;
  if (prev === next) return;

  const prevEl = views.get(prev);
  const nextEl = views.get(next);
  if (!prevEl || !nextEl) return;

  navLocked = true;

  prevEl.classList.remove("view-active");
  cleanup(prevEl);

  cleanup(nextEl);
  nextEl.classList.add("view-active");
  nextEl.classList.add(dir === "back" ? "enter-from-left" : "enter-from-right");

  nextEl.offsetHeight;
  nextEl.classList.add("enter-to-center");

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
    e.preventDefault();
    e.stopPropagation();
    hapticTap();
    const target = btn.dataset.open;
    showView(target, "forward", true);
    onViewEnter(target);
  });
});

document.querySelectorAll("[data-back]").forEach(btn => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    hapticTap();
    goBack();
  });
});

navItems.forEach((btn) => {
  btn.addEventListener("click", (e) => {
    e.preventDefault();
    e.stopPropagation();
    hapticTap();

    const tab = btn.dataset.tab;
    navStack = [tab];
    showView(tab, "back", false);
    onViewEnter(tab);
    setActiveTab(tab);
  });
});

let touchStartX = 0;
let touchStartY = 0;
let touchActive = false;
let ignoreSwipe = false;

function isInteractiveTarget(target) {
  if (!target) return false;
  return !!target.closest?.("button, a, input, textarea, select, label");
}

stackEl?.addEventListener("touchstart", (e) => {
  const t = e.touches[0];
  touchStartX = t.clientX;
  touchStartY = t.clientY;
  touchActive = true;

  ignoreSwipe = isInteractiveTarget(e.target);
}, {passive:true});

stackEl?.addEventListener("touchmove", (e) => {
  if (!touchActive) return;
  const t = e.touches[0];
  const dx = t.clientX - touchStartX;
  const dy = t.clientY - touchStartY;
  if (Math.abs(dy) > Math.abs(dx)) ignoreSwipe = true;
}, {passive:true});

stackEl?.addEventListener("touchend", (e) => {
  if (!touchActive || navLocked) return;
  touchActive = false;

  if (ignoreSwipe) return;

  const t = e.changedTouches[0];
  const dx = t.clientX - touchStartX;
  const dy = t.clientY - touchStartY;

  if (Math.abs(dy) > 90) return;
  if (Math.abs(dx) < 70) return;

  const inNested = navStack.length > 1;

  if (inNested) {
    if (dx > 0) {
      hapticTap();
      goBack();
    }
    return;
  }

  if (!ROOT_TABS.includes(currentView)) return;

  const idx = ROOT_TABS.indexOf(currentView);
  if (dx < 0) {
    const next = ROOT_TABS[Math.min(ROOT_TABS.length - 1, idx + 1)];
    if (next !== currentView) {
      hapticTap();
      navStack = [next];
      showView(next, "forward", false);
      onViewEnter(next);
      setActiveTab(next);
    }
  } else {
    const prev = ROOT_TABS[Math.max(0, idx - 1)];
    if (prev !== currentView) {
      hapticTap();
      navStack = [prev];
      showView(prev, "back", false);
      onViewEnter(prev);
      setActiveTab(prev);
    }
  }
}, {passive:true});

let TG_ID = null;

function initUserUI() {
  if (!IN_TELEGRAM || !initDataUnsafe?.user) return;

  const u = initDataUnsafe.user;
  TG_ID = u.id;

  const name =
    [u.first_name, u.last_name].filter(Boolean).join(" ") ||
    (u.username ? "@" + u.username : `ID: ${u.id}`);

  const photo = u.photo_url ? u.photo_url : "https://t.me/i/userpic/320/0.png";

  if (homeAvatarEl) homeAvatarEl.src = photo;
  if (homeNameEl) homeNameEl.textContent = name;
  if (homeIdEl) homeIdEl.textContent = `ID: ${u.id}`;

  if (profileAvatarEl) profileAvatarEl.src = photo;
  if (profileNameEl) profileNameEl.textContent = name;
  if (profileUsernameEl) profileUsernameEl.textContent = u.username ? "@" + u.username : `ID: ${u.id}`;
}

btnCopyId?.addEventListener("click", async (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (!TG_ID) return;
  try {
    await navigator.clipboard.writeText(String(TG_ID));
    toast("ID скопирован", "info");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать", "error");
    hapticError();
  }
});

let lastSubUrl = null;

function setStatusPill(active) {
  if (!subBadgeEl) return;
  subBadgeEl.classList.remove("active","inactive");
  subBadgeEl.classList.add(active ? "active" : "inactive");
}

async function loadProfileAndBalance() {
  try {
    const data = await apiRequest("/mini/profile");
    const bal = data.user?.balance ?? 0;
    if (homeBalanceEl) homeBalanceEl.textContent = `${bal} ₽`;
    if (profilePillEl) profilePillEl.textContent = `${bal} ₽`;
    return data;
  } catch {
    return null;
  }
}

async function loadStatusCard() {
  try {
    const data = await apiRequest("/mini/status");

    if (!data.has_subscription) {
      if (subBadgeEl) subBadgeEl.textContent = "Неактивна";
      setStatusPill(false);

      if (subEmojiEl) subEmojiEl.textContent = "🥲";
      if (subTitleEl) subTitleEl.textContent = "Подписка неактивна";
      if (subMetaEl) subMetaEl.textContent = "Оформите подписку в разделе «Тарифы».";

      lastSubUrl = null;
      if (subLinkWrapEl) subLinkWrapEl.style.display = "none";

      if (statusTextEl) statusTextEl.textContent = "Нет активной подписки.";
      return;
    }

    if (subBadgeEl) subBadgeEl.textContent = "Активна";
    setStatusPill(true);

    if (subEmojiEl) subEmojiEl.textContent = "✨";

    const planName = data.plan?.name ? data.plan.name : "Подписка";
    if (subTitleEl) subTitleEl.textContent = planName;

    const untilIso = data.subscription?.current_period_end || null;
    const until = untilIso ? new Date(untilIso) : null;

    if (subMetaEl) subMetaEl.textContent = `Действует до: ${until ? until.toLocaleString() : "—"}`;

    const url =
      data.subscription_url ||
      (data.subscription_token ? `https://lunetpn.ru/sub/${data.subscription_token}` : null);

    lastSubUrl = url;

    if (url) {
      subLinkEl.textContent = url;
      subLinkWrapEl.style.display = "block";
    } else {
      subLinkWrapEl.style.display = "none";
    }

    if (statusTextEl) {
      const untilTxt = until ? until.toLocaleString() : "—";
      statusTextEl.textContent = `Тариф: ${planName}\nПодписка до: ${untilTxt}`;
    }
  } catch {
    if (subBadgeEl) subBadgeEl.textContent = "Ошибка";
    setStatusPill(false);
    if (subEmojiEl) subEmojiEl.textContent = "🌧️";
    if (subTitleEl) subTitleEl.textContent = "Ошибка";
    if (subMetaEl) subMetaEl.textContent = "Не удалось загрузить статус.";
    if (subLinkWrapEl) subLinkWrapEl.style.display = "none";
    if (statusTextEl) statusTextEl.textContent = "Не удалось загрузить статус.";
  }
}

btnCopySub?.addEventListener("click", async (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (!lastSubUrl) return toast("Ссылка для подключения пока недоступна.", "error");
  try {
    await navigator.clipboard.writeText(lastSubUrl);
    toast("Ссылка скопирована", "info");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать ссылку.", "error");
    hapticError();
  }
});

btnOpenSub?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (!lastSubUrl) return toast("Ссылка для подключения пока недоступна.", "error");
  if (tg?.openLink) tg.openLink(lastSubUrl);
  else window.open(lastSubUrl, "_blank");
});

async function applyPromocode() {
  const code = (promoInputEl?.value || "").trim();
  if (!code) {
    toast("Введите промокод.", "error");
    hapticError();
    return;
  }

  promoApplyBtn.disabled = true;
  if (promoHintEl) promoHintEl.textContent = "Проверяю промокод…";
  hapticTap();

  try {
    const data = await apiRequest("/mini/promocode/apply", { code });
    if (data.ok) {
      const added = data.amount_added ?? data.amount ?? 0;
      const balance = data.balance ?? null;

      toast(`Промокод применён. Начислено +${added} ₽`, "info");
      if (promoHintEl) promoHintEl.textContent = `Начислено: +${added} ₽`;

      if (balance !== null) {
        if (homeBalanceEl) homeBalanceEl.textContent = `${balance} ₽`;
        if (profilePillEl) profilePillEl.textContent = `${balance} ₽`;
      } else {
        await loadProfileAndBalance();
      }

      hapticSuccess();
    }
  } catch {
    if (promoHintEl) promoHintEl.textContent = "Не удалось применить промокод.";
    hapticError();
  } finally {
    promoApplyBtn.disabled = false;
  }
}

promoApplyBtn?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  applyPromocode();
});
promoInputEl?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") applyPromocode();
});

async function createTopup() {
  const raw = (topupInputEl?.value || "").trim();
  const amount = Number(raw);

  if (!Number.isFinite(amount) || amount <= 0) {
    toast("Введите корректную сумму пополнения.", "error");
    if (topupHintEl) topupHintEl.textContent = "Например: 100";
    hapticError();
    return;
  }

  topupBtn.disabled = true;
  if (topupHintEl) topupHintEl.textContent = "Создаю ссылку на оплату…";
  hapticTap();

  try {
    const data = await apiRequest("/mini/balance/topup", { amount });

    if (!data.ok || !data.payment_url) {
      toast("Не удалось создать платёж. Попробуйте ещё раз.", "error");
      if (topupHintEl) topupHintEl.textContent = "";
      hapticError();
      return;
    }

    const url = data.payment_url;

    toast("Открыл страницу оплаты. После оплаты нажмите «Проверить платежи».", "info");
    if (topupHintEl) topupHintEl.textContent = "После оплаты: «Транзакции» → «Проверить платежи».";

    if (tg?.openLink) tg.openLink(url);
    else window.open(url, "_blank");

    hapticSuccess();
  } catch {
    if (topupHintEl) topupHintEl.textContent = "Не удалось открыть оплату.";
    hapticError();
  } finally {
    topupBtn.disabled = false;
  }
}

topupBtn?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  createTopup();
});
topupInputEl?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") createTopup();
});

async function loadTransactions() {
  if (!txListEl) return;
  txListEl.textContent = "Загрузка…";

  try {
    const data = await apiRequest("/mini/profile");
    const txs = data.transactions || [];

    if (!txs.length) {
      txListEl.textContent = "Транзакций пока нет.";
      return;
    }

    txListEl.innerHTML = "";
    txs.forEach((t) => {
      const created = t.created_at ? new Date(t.created_at) : null;

      const row = document.createElement("div");
      row.className = "tx-row";
      row.innerHTML = `
        <div class="tx-left">
          <div class="tx-title">${(t.payment_system || "Операция")}</div>
          <div class="tx-meta">${created ? created.toLocaleString() : ""}${t.paid ? " • оплачено" : " • ожидает оплаты"}</div>
        </div>
        <div class="tx-amount">${t.paid ? "+" : ""}${t.amount} ₽</div>
      `;
      txListEl.appendChild(row);
    });
  } catch {
    txListEl.textContent = "Не удалось загрузить транзакции.";
  }
}

async function checkPayments() {
  if (btnCheckPayments) btnCheckPayments.disabled = true;
  if (checkHintEl) checkHintEl.textContent = "Проверяю платежи…";
  hapticTap();

  try {
    const data = await apiRequest("/mini/balance/check");

    if (!data.ok && data.reason === "no_pending") {
      toast("Нет незавершённых платежей. Если вы оплатили только что — подождите 1–2 минуты и проверьте ещё раз.", "info");
      if (checkHintEl) checkHintEl.textContent = "Ожидающих платежей нет.";
      hapticSuccess();
      return;
    }

    const tx = data.transaction || null;

    if (tx && tx.paid) {
      toast(`Платёж подтверждён ✅ Баланс обновлён.`, "info");
      if (checkHintEl) checkHintEl.textContent = "Платёж подтверждён. Баланс обновлён.";
      hapticSuccess();

      await loadProfileAndBalance();
      await loadTransactions();
      return;
    }

    if (tx && !tx.paid) {
      toast("Платёж найден, но ещё не подтверждён. Попробуйте проверить снова через 1–2 минуты.", "info");
      if (checkHintEl) checkHintEl.textContent = `Статус: ${tx.status_raw || "ожидает подтверждения"}`;
      hapticTap();
      await loadTransactions();
      return;
    }

    toast("Не удалось определить статус платежа. Попробуйте позже.", "error");
    if (checkHintEl) checkHintEl.textContent = "";
    hapticError();
  } catch (e) {
    if (checkHintEl) checkHintEl.textContent = "Не удалось проверить платежи.";
    hapticError();
  } finally {
    if (btnCheckPayments) btnCheckPayments.disabled = false;
  }
}

btnCheckPayments?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  checkPayments();
});

btnRefreshTx?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  loadTransactions();
});

async function loadPlans() {
  if (!plansListEl) return;
  plansListEl.textContent = "Загружаю…";

  try {
    const data = await apiRequest("/mini/plans");
    if (!data.ok) {
      if (plansCardEl) plansCardEl.style.display = "none";
      return;
    }
    renderPlans(data.plans || []);
  } catch {
    if (plansCardEl) plansCardEl.style.display = "none";
  }
}

function renderPlans(plans) {
  if (!plansCardEl || !plansListEl) return;

  if (!plans || !plans.length) {
    plansCardEl.style.display = "none";
    return;
  }

  plansCardEl.style.display = "block";
  plansListEl.innerHTML = "";

  plans.forEach((p) => {
    const item = document.createElement("div");
    item.style.padding = "12px";
    item.style.borderRadius = "18px";
    item.style.border = "1px solid rgba(148,163,184,0.10)";
    item.style.background = "rgba(0,0,0,0.14)";
    item.style.marginBottom = "10px";

    item.innerHTML = `
      <div style="display:flex;justify-content:space-between;align-items:center;gap:10px;">
        <div style="min-width:0;">
          <div style="font-weight:1000;font-size:14px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">${p.name}</div>
          <div style="font-size:12px;color:rgba(232,235,242,0.62);">Срок: ${p.period_days} дней</div>
        </div>
        <div style="display:flex;gap:8px;align-items:center;">
          <div class="pill" style="border-color:rgba(148,163,184,0.10);">${p.price} ₽</div>
          <button class="btn accent small" type="button">Подключить</button>
        </div>
      </div>
    `;

    const btn = item.querySelector("button");
    btn.addEventListener("click", () => buyPlan(p.id, btn));
    plansListEl.appendChild(item);
  });
}

async function buyPlan(planId, btn) {
  btn.disabled = true;
  toast("Оформляю подписку…", "info");
  hapticTap();
  try {
    const data = await apiRequest("/mini/subscription/buy", { plan_id: planId });
    if (data.ok) {
      toast("Подписка оформлена ✅", "info");
      hapticSuccess();
      await loadStatusCard();
      await loadPlans();
    } else {
      toast("Не удалось оформить подписку. Попробуйте позже.", "error");
      hapticError();
    }
  } catch {
    hapticError();
  } finally {
    btn.disabled = false;
  }
}

let lastRefUrl = null;
function initReferralLink() {
  if (!TG_ID) return;
  lastRefUrl = `https://t.me/LunetVpnBot?start=ref_${TG_ID}`;
  if (refLinkEl) refLinkEl.textContent = lastRefUrl;
}

btnCopyRef?.addEventListener("click", async (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (!lastRefUrl) return toast("Реф-ссылка недоступна.", "error");
  try {
    await navigator.clipboard.writeText(lastRefUrl);
    toast("Реф-ссылка скопирована", "info");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать.", "error");
    hapticError();
  }
});

btnOpenRef?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (!lastRefUrl) return toast("Реф-ссылка недоступна.", "error");
  if (tg?.openTelegramLink) tg.openTelegramLink(lastRefUrl);
  else window.open(lastRefUrl, "_blank");
});

const SETUP_URL = "https://telegra.ph/Lunet-VPN---instrukciya-12-18";
if (setupLinkEl) setupLinkEl.textContent = SETUP_URL;

btnCopySetup?.addEventListener("click", async (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  try {
    await navigator.clipboard.writeText(SETUP_URL);
    toast("Ссылка скопирована", "info");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать.", "error");
    hapticError();
  }
});

btnOpenSetup?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (tg?.openLink) tg.openLink(SETUP_URL);
  else window.open(SETUP_URL, "_blank");
});

const SUPPORT_TG = "https://t.me/LunetVPNSupportBot";
const SUPPORT_MAIL = "support@lunet.ru";

supportTgEl?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (tg?.openTelegramLink) tg.openTelegramLink(SUPPORT_TG);
  else window.open(SUPPORT_TG, "_blank");
});

supportMailEl?.addEventListener("click", async (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  try {
    await navigator.clipboard.writeText(SUPPORT_MAIL);
    toast("Email скопирован", "info");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать.", "error");
    hapticError();
  }
});

btnOpenSupportTg?.addEventListener("click", (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  if (tg?.openTelegramLink) tg.openTelegramLink(SUPPORT_TG);
  else window.open(SUPPORT_TG, "_blank");
});

btnCopySupportMail?.addEventListener("click", async (e) => {
  e.preventDefault();
  e.stopPropagation();
  hapticTap();
  try {
    await navigator.clipboard.writeText(SUPPORT_MAIL);
    toast("Email скопирован", "info");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать.", "error");
    hapticError();
  }
});

(function injectTxStyle(){
  const style = document.createElement("style");
  style.textContent = `
    .tx-row{
      display:flex; justify-content:space-between; gap:12px;
      padding: 12px 4px;
      border-bottom: 1px solid rgba(148,163,184,0.10);
    }
    .tx-left{ min-width:0; }
    .tx-title{ font-weight: 950; }
    .tx-meta{ font-size: 12px; color: rgba(232,235,242,0.58); margin-top: 2px; }
    .tx-amount{ font-weight: 1000; opacity:.92; }
  `;
  document.head.appendChild(style);
})();

async function onViewEnter(view) {
  if (view === "referral") initReferralLink();
  if (view === "transactions") {
    if (checkHintEl) checkHintEl.textContent = "Совет: после оплаты нажмите «Проверить платежи».";
    await loadTransactions();
  }
  if (view === "tariffs") { await loadStatusCard(); await loadPlans(); }
  if (view === "profile") await loadProfileAndBalance();
}

if (IN_TELEGRAM) {
  initUserUI();
  initReferralLink();

  currentView = "home";
  navStack = ["home"];
  navLocked = false;
  setActiveTab("home");

  (async () => {
    await loadStatusCard();
    await loadProfileAndBalance();
  })();
}
