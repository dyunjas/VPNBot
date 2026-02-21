// ====== ✅ DAYS LEFT (NEW) ======
function daysLeftFromIso(untilIso) {
  if (!untilIso) return null;
  const end = new Date(untilIso);
  if (Number.isNaN(end.getTime())) return null;

  const now = new Date();
  const ms = end.getTime() - now.getTime();
  if (ms <= 0) return 0;

  return Math.ceil(ms / (24 * 60 * 60 * 1000));
}

function formatDaysLeft(n) {
  if (n === null) return "—";
  if (n <= 0) return "0 дней";

  const mod10 = n % 10;
  const mod100 = n % 100;
  let word = "дней";
  if (mod10 === 1 && mod100 !== 11) word = "день";
  else if (mod10 >= 2 && mod10 <= 4 && !(mod100 >= 12 && mod100 <= 14)) word = "дня";
  return `${n} ${word}`;
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

    const untilIso = data.subscription?.current_period_end || null;
    const left = daysLeftFromIso(untilIso);
    const until = untilIso ? new Date(untilIso) : null;
    const untilTxt = until ? until.toLocaleString() : "—";


    if (subTitleEl) subTitleEl.textContent = "Подписка активна";
    if (subMetaEl) subMetaEl.textContent = `Осталось: ${formatDaysLeft(left)}\nДействует до: ${untilTxt}`;

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
      statusTextEl.textContent = `Подписка активна\nОсталось: ${formatDaysLeft(left)}\nДо: ${untilTxt}`;
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

// ====== REFERRAL LINK ======
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
