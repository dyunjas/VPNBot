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

    if (typeof tg?.requestFullscreen === "function") {
      tg.requestFullscreen();
    }
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

// ====== DOM refs ======
const appRootEl = document.getElementById("app-root");
const outsideStubEl = document.getElementById("outside-stub");
const toastEl = document.getElementById("message");
const stackEl = document.getElementById("stack");

function applyTelegramTopInset() {
  try {
    const top =
      tg?.contentSafeAreaInset?.top ??
      tg?.safeAreaInset?.top ??
      18;
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
function toast(text, kind = "info") {
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
    toast(msg, "error");
    if (String(detail || "").toLowerCase().includes("banned")) showBannedScreen();
    throw new Error(msg);
  }

  if (data.error) {
    const msg = friendlyErrorMessage(data.error);
    toast(msg, "error");
    if (String(data.error || "").toLowerCase().includes("banned")) showBannedScreen();
    throw new Error(msg);
  }

  return data;
}

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

  const photo = u.photo_url ? u.photo_url : "https://t.me/i/userpic/320/0.png";

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

async function loadStatusCard() {
  try {
    const data = await apiRequest("/mini/status");

    if (!data.has_subscription) {
      if (subTitleEl) subTitleEl.textContent = "Подписка неактивна";
      if (subMetaEl) subMetaEl.textContent = "Оформите подписку в разделе «Тарифы».";
      lastSubUrl = null;
      if (subLinkWrapEl) subLinkWrapEl.style.display = "none";
      if (statusTextEl) statusTextEl.textContent = "Нет активной подписки.";
      return;
    }

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
    if (subTitleEl) subTitleEl.textContent = "Ошибка";
    if (subMetaEl) subMetaEl.textContent = "Не удалось загрузить статус.";
    if (subLinkWrapEl) subLinkWrapEl.style.display = "none";
    if (statusTextEl) statusTextEl.textContent = "Не удалось загрузить статус.";
  }
}

btnCopySub?.addEventListener("click", async (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (!lastSubUrl) return toast("Ссылка пока недоступна");
  try {
    await navigator.clipboard.writeText(lastSubUrl);
    toast("Ссылка скопирована");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать ссылку");
    hapticError();
  }
});

btnOpenSub?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (!lastSubUrl) return toast("Ссылка пока недоступна");
  if (tg?.openLink) tg.openLink(lastSubUrl);
  else window.open(lastSubUrl, "_blank");
});

async function applyPromocode() {
  const code = (promoInputEl?.value || "").trim();
  if (!code) {
    toast("Введите промокод");
    hapticError();
    return;
  }

  promoApplyBtn.disabled = true;
  if (promoHintEl) promoHintEl.textContent = "Проверяю…";
  hapticTap();

  try {
    const data = await apiRequest("/mini/promocode/apply", { code });
    if (data.ok) {
      const added = data.amount_added ?? 0;
      const balance = data.balance ?? null;

      toast(`Начислено +${added} ₽`);
      if (promoHintEl) promoHintEl.textContent = `Начислено: +${added} ₽`;

      if (balance !== null) {
        if (homeBalanceEl) homeBalanceEl.textContent = `${balance} ₽`;
      } else {
        await loadProfileAndBalance();
      }

      hapticSuccess();
    }
  } catch {
    if (promoHintEl) promoHintEl.textContent = "Не удалось применить";
    hapticError();
  } finally {
    promoApplyBtn.disabled = false;
  }
}

promoApplyBtn?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  applyPromocode();
});
promoInputEl?.addEventListener("keydown", (e) => {
  if (e.key === "Enter") applyPromocode();
});

let selectedPay = { method: "platega", platega_type: "card" };

function setPayActive(btn){
  [pmCardBtn, pmSbpBtn, pmCryptoBtn].forEach(b => b?.classList.remove("seg__btn--active"));
  btn?.classList.add("seg__btn--active");
}

pmCardBtn?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  selectedPay = { method: "platega", platega_type: "card" };
  setPayActive(pmCardBtn);
  if (topupMethodHintEl) topupMethodHintEl.textContent = "Выбрано: Карта";
});

pmSbpBtn?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  selectedPay = { method: "platega", platega_type: "sbp" };
  setPayActive(pmSbpBtn);
  if (topupMethodHintEl) topupMethodHintEl.textContent = "Выбрано: СБП";
});

pmCryptoBtn?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  selectedPay = { method: "crypto", asset: "USDT" };
  setPayActive(pmCryptoBtn);
  if (topupMethodHintEl) topupMethodHintEl.textContent = "Выбрано: Crypto (USDT)";
});

async function createTopup() {
  const raw = (topupInputEl?.value || "").trim();
  const amount = Number(raw);

  if (!Number.isFinite(amount) || amount <= 0) {
    toast("Введите корректную сумму");
    if (topupHintEl) topupHintEl.textContent = "Например: 100";
    hapticError();
    return;
  }

  topupPayBtn.disabled = true;
  if (topupHintEl) topupHintEl.textContent = "Создаю оплату…";
  hapticTap();

  try {
    const payload = { amount: Math.floor(amount), ...selectedPay };
    const data = await apiRequest("/mini/balance/topup", payload);

    if (!data.ok || !data.payment_url) {
      toast("Не удалось создать платёж");
      if (topupHintEl) topupHintEl.textContent = "";
      hapticError();
      return;
    }

    const url = data.payment_url;

    toast("Открыл страницу оплаты");
    if (topupHintEl) topupHintEl.textContent = "После оплаты: Транзакции → Проверить платежи.";

    if (tg?.openLink) tg.openLink(url);
    else window.open(url, "_blank");

    hapticSuccess();
  } catch {
    if (topupHintEl) topupHintEl.textContent = "Не удалось открыть оплату";
    hapticError();
  } finally {
    topupPayBtn.disabled = false;
  }
}

topupPayBtn?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  createTopup();
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
      row.className = "tx";
      row.innerHTML = `
        <div class="tx__left">
          <div class="tx__title">${(t.payment_system || "Операция")}</div>
          <div class="tx__meta">${created ? created.toLocaleString() : ""}${t.paid ? " • оплачено" : " • ожидает оплаты"}</div>
        </div>
        <div class="tx__amt">${t.paid ? "+" : ""}${t.amount} ₽</div>
      `;
      txListEl.appendChild(row);
    });
  } catch {
    txListEl.textContent = "Не удалось загрузить транзакции.";
  }
}

async function checkPayments() {
  if (btnCheckPayments) btnCheckPayments.disabled = true;
  if (checkHintEl) checkHintEl.textContent = "Проверяю…";
  hapticTap();

  try {
    const data = await apiRequest("/mini/balance/check");

    if (!data.ok && data.reason === "no_pending") {
      toast("Ожидающих платежей нет");
      if (checkHintEl) checkHintEl.textContent = "Ожидающих платежей нет.";
      hapticSuccess();
      return;
    }

    const tx = data.transaction || null;

    if (tx && tx.paid) {
      toast("Платёж подтверждён ✅");
      if (checkHintEl) checkHintEl.textContent = "Платёж подтверждён. Баланс обновлён.";
      hapticSuccess();

      await loadProfileAndBalance();
      await loadTransactions();
      return;
    }

    if (tx && !tx.paid) {
      toast("Платёж найден, но ещё не подтверждён");
      if (checkHintEl) checkHintEl.textContent = `Статус: ${tx.status_raw || "ожидает подтверждения"}`;
      await loadTransactions();
      return;
    }

    toast("Не удалось определить статус платежа");
    if (checkHintEl) checkHintEl.textContent = "";
    hapticError();
  } catch {
    if (checkHintEl) checkHintEl.textContent = "Не удалось проверить платежи.";
    hapticError();
  } finally {
    if (btnCheckPayments) btnCheckPayments.disabled = false;
  }
}

btnCheckPayments?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  checkPayments();
});

btnRefreshTx?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
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
    item.className = "plan";
    item.innerHTML = `
      <div style="min-width:0;">
        <div class="plan__name">${p.name}</div>
        <div class="plan__meta">Срок: ${p.period_days} дней</div>
      </div>
      <div class="plan__right">
        <div class="pill">${p.price} ₽</div>
        <button class="btn btn--accent btn--small" type="button">Подключить</button>
      </div>
    `;

    const btn = item.querySelector("button");
    btn.addEventListener("click", () => buyPlan(p.id, btn));
    plansListEl.appendChild(item);
  });
}

async function buyPlan(planId, btn) {
  btn.disabled = true;
  toast("Оформляю подписку…");
  hapticTap();
  try {
    const data = await apiRequest("/mini/subscription/buy", { plan_id: planId });
    if (data.ok) {
      toast("Подписка оформлена ✅");
      hapticSuccess();
      await loadStatusCard();
      await loadPlans();
      await loadProfileAndBalance();
    } else {
      toast("Не удалось оформить подписку");
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
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (!lastRefUrl) return toast("Реф-ссылка недоступна");
  try {
    await navigator.clipboard.writeText(lastRefUrl);
    toast("Реф-ссылка скопирована");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать");
    hapticError();
  }
});

btnOpenRef?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (!lastRefUrl) return toast("Реф-ссылка недоступна");
  if (tg?.openTelegramLink) tg.openTelegramLink(lastRefUrl);
  else window.open(lastRefUrl, "_blank");
});

const SETUP_URL = "https://telegra.ph/Lunet-VPN---instrukciya-12-18";
if (setupLinkEl) setupLinkEl.textContent = SETUP_URL;

btnCopySetup?.addEventListener("click", async (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  try {
    await navigator.clipboard.writeText(SETUP_URL);
    toast("Ссылка скопирована");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать");
    hapticError();
  }
});

btnOpenSetup?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (tg?.openLink) tg.openLink(SETUP_URL);
  else window.open(SETUP_URL, "_blank");
});

const SUPPORT_TG = "https://t.me/LunetVPNSupportBot";
const SUPPORT_MAIL = "support@lunet.ru";

supportTgEl?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (tg?.openTelegramLink) tg.openTelegramLink(SUPPORT_TG);
  else window.open(SUPPORT_TG, "_blank");
});

supportMailEl?.addEventListener("click", async (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  try {
    await navigator.clipboard.writeText(SUPPORT_MAIL);
    toast("Email скопирован");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать");
    hapticError();
  }
});

btnOpenSupportTg?.addEventListener("click", (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  if (tg?.openTelegramLink) tg.openTelegramLink(SUPPORT_TG);
  else window.open(SUPPORT_TG, "_blank");
});

btnCopySupportMail?.addEventListener("click", async (e) => {
  e.preventDefault(); e.stopPropagation();
  hapticTap();
  try {
    await navigator.clipboard.writeText(SUPPORT_MAIL);
    toast("Email скопирован");
    hapticSuccess();
  } catch {
    toast("Не удалось скопировать");
    hapticError();
  }
});

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
