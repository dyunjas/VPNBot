async function applyPromocode() {
  const code = ($("promo-input")?.value || "").trim();
  if (!code) return toast("Введите промокод");

  haptic();
  try {
    const data = await api("/api/promocode/apply", { code });
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
    const data = await api("/api/balance/topup", {
      amount: Math.floor(amount),
      ...getTopupPayload(),
    });

    if (!data.payment_url) throw new Error("Ссылка на оплату не получена");

    tg?.openLink?.(data.payment_url);
    if (!tg?.openLink) window.open(data.payment_url, "_blank");

    if (hint) {
      hint.textContent = "После оплаты нажмите «Проверить платежи». Проверим 3 последних платежа.";
    }
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
    const data = await api("/api/subscription/traffic/buy", { gb: Math.floor(gb) });
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
    const data = await api("/api/balance/check", {});

    if (!data.ok && data.reason === "no_pending") {
      toast(`Ожидающих платежей нет (проверено: ${data.checked || 0})`);
      return;
    }

    if (data.confirmed) {
      toastSuccess(`Платеж подтвержден (проверено: ${data.checked || 1})`);
      haptic("success");
    } else {
      toast(
        friendlyErrorMessage(
          data.message || `Платеж еще не подтвержден (проверено: ${data.checked || 1})`,
        ),
      );
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
  $("btn-check-payments")?.addEventListener("click", checkPayments);
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
