async function loadPlans() {
  if (!plansListEl) return;
  plansListEl.textContent = "Загружаю…";

  try {
    const data = await apiRequest("/api/plans");
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
    const data = await apiRequest("/api/subscription/buy", { plan_id: planId });
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
