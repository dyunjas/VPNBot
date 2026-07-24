async function applyPromocode() {
  const code = ($("promo-input")?.value || "").trim();
  if (!code) return toast("Введите промокод");

  haptic();
  try {
    const data = await api("/api/promocode/apply", { code });
    const hint = $("promo-hint");
    if (hint && !IS_MINIAPP_PATH) hint.textContent = `Начислено: +${data.amount_added || 0} ₽`;
    toastSuccess("Промокод применен");
    haptic("success");
    await loadProfile();
  } catch (e) {
    const hint = $("promo-hint");
    if (hint && !IS_MINIAPP_PATH) hint.textContent = e.message;
    toast(e.message);
    haptic("error");
  }
}

function getTopupPayload() {
  const method =
    state.topupMethod || document.querySelector(".pay-method--active")?.dataset.method || "card";
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

  const current =
    buttons.find((btn) => btn.classList.contains("pay-method--active"))?.dataset.method || "card";
  setActive(current);

  buttons.forEach((btn) => {
    btn.addEventListener("click", () => {
      haptic();
      setActive(btn.dataset.method);
    });
  });
}

let topupRefreshTimer = null;

function scheduleTopupRefresh() {
  if (topupRefreshTimer) window.clearInterval(topupRefreshTimer);
  let attempts = 0;
  const refresh = async () => {
    attempts += 1;
    try {
      await Promise.all([loadProfile(), loadTransactions()]);
    } catch {}
    if (attempts >= 12 && topupRefreshTimer) {
      window.clearInterval(topupRefreshTimer);
      topupRefreshTimer = null;
    }
  };
  window.setTimeout(refresh, 4000);
  topupRefreshTimer = window.setInterval(refresh, 10000);
}

async function createTopup() {
  const amount = Number(($("topup-input")?.value || "").trim());
  const hint = $("topup-hint");

  if (!Number.isFinite(amount) || amount <= 0) {
    const msg = "Введите корректную сумму";
    if (hint && !IS_MINIAPP_PATH) hint.textContent = msg;
    return toast(msg);
  }

  haptic();
  try {
    const data = await api("/api/balance/topup", {
      amount: Math.floor(amount),
      ...getTopupPayload(),
    });

    if (!data.payment_url) throw new Error("Ссылка на оплату не получена");

    tg?.openLink?.(data.payment_url);
    if (!tg?.openLink) window.open(data.payment_url, "_blank");

    if (hint && !IS_MINIAPP_PATH) {
      hint.textContent = "После оплаты баланс обновится автоматически. Обычно это занимает до 1-2 минут.";
    }
    scheduleTopupRefresh();
    toastSuccess("Ссылка на оплату открыта");
    haptic("success");
  } catch (e) {
    if (hint && !IS_MINIAPP_PATH) hint.textContent = e.message;
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
    if (hint && !IS_MINIAPP_PATH) hint.textContent = msg;
    return toast(msg);
  }

  setButtonBusy(btn, true, "Покупка...");
  haptic();
  try {
    const data = await api("/api/subscription/traffic/buy", { gb: Math.floor(gb) });
    if (input) input.value = "";
    const msg = `Добавлено ${data.gb_added} ГБ, списано ${data.charged} ₽`;
    if (hint && !IS_MINIAPP_PATH) hint.textContent = msg;
    toastSuccess(msg);
    haptic("success");
    await Promise.all([loadStatus(), loadProfile()]);
  } catch (e) {
    if (hint && !IS_MINIAPP_PATH) hint.textContent = e.message;
    toast(e.message);
    haptic("error");
  } finally {
    setButtonBusy(btn, false);
  }
}

function closeAppPopups(except = null) {
  document.querySelectorAll(".app-popup.is-open").forEach((popup) => {
    if (popup === except) return;
    popup.classList.remove("is-open");
    popup.querySelector(".app-popup__trigger")?.setAttribute("aria-expanded", "false");
  });
}

function initAppPopups() {
  document.querySelectorAll(".app-popup").forEach((popup) => {
    if (popup.dataset.popupInit === "1") return;
    popup.dataset.popupInit = "1";

    const trigger = popup.querySelector(".app-popup__trigger");
    if (!trigger) return;
    trigger.setAttribute("aria-expanded", "false");
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = popup.classList.contains("is-open");
      closeAppPopups(popup);
      popup.classList.toggle("is-open", !isOpen);
      trigger.setAttribute("aria-expanded", !isOpen ? "true" : "false");
      haptic();
    });
  });

  document.querySelectorAll("[data-cabinet-only]").forEach((el) => {
    el.hidden = !IS_CABINET_PATH;
  });
}

function focusAfterViewSwitch(id) {
  window.setTimeout(() => {
    const el = $(id);
    if (!el) return;
    el.focus?.({ preventScroll: true });
    el.scrollIntoView?.({ behavior: "smooth", block: "center" });
  }, 80);
}

async function handlePopupAction(action) {
  closeAppPopups();
  haptic();

  if (action === "topup") {
    switchView("profile");
    focusAfterViewSwitch("topup-input");
    return;
  }

  if (action === "copy-sub") {
    $("btn-copy-sub")?.click();
    return;
  }

  if (action === "referral") {
    switchView("referral");
    await loadReferral().catch(() => {});
    $("btn-copy-ref")?.click();
    return;
  }

  if (action === "support") {
    $("btn-open-support")?.click();
    return;
  }

  if (action === "logout") {
    $("btn-cabinet-logout")?.click();
  }
}

function initEvents() {
  initAppPopups();
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
  document.querySelectorAll("[data-popup-action]").forEach((btn) => {
    btn.addEventListener("click", () => {
      handlePopupAction(btn.dataset.popupAction);
    });
  });

  document.addEventListener("click", (event) => {
    if (!event.target.closest(".app-popup")) closeAppPopups();
  });
  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape") closeAppPopups();
  });

  $("promo-apply")?.addEventListener("click", applyPromocode);
  $("btn-quick-connect")?.addEventListener("click", async () => {
    haptic();
    if (!state.subscriptionUrl) {
      toast("Ссылка недоступна");
      return;
    }
    tg?.openLink?.(state.subscriptionUrl);
    if (!tg?.openLink) window.open(state.subscriptionUrl, "_blank");
  });
  $("btn-buy-traffic")?.addEventListener("click", buyTraffic);
  $("topup-pay")?.addEventListener("click", createTopup);
  $("btn-refresh-tx")?.addEventListener("click", async (e) => {
    const btn = e.currentTarget;
    setButtonBusy(btn, true, null);
    haptic();
    try {
      await loadTransactions();
      haptic("success");
      setButtonBusy(btn, false);
    } catch {
      toast("Не удалось обновить транзакции");
      haptic("error");
      setButtonBusy(btn, false);
    } finally {
      setButtonBusy(btn, false);
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
  $("btn-ref-transfer")?.addEventListener("click", transferReferralBalance);
  $("btn-open-support")?.addEventListener("click", () => {
    const supportUrl = "https://t.me/LunetVPNSupport";
    tg?.openTelegramLink?.(supportUrl);
    if (!tg?.openTelegramLink) window.open(supportUrl, "_blank");
  });
  document.querySelectorAll(".js-open-support").forEach((btn) => {
    btn.addEventListener("click", () => $("btn-open-support")?.click());
  });
  document.querySelectorAll(".js-cabinet-logout").forEach((btn) => {
    btn.addEventListener("click", () => $("btn-cabinet-logout")?.click());
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
  $("btn-cabinet-logout")?.addEventListener("click", async () => {
    if (!IS_CABINET_PATH) return;
    try {
      await fetch(`${BACKEND_URL}/api/auth/logout`, { method: "POST", credentials: "include" });
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
