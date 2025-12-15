const BACKEND_URL = window.location.origin;

// --- детект Telegram WebApp ---
const tg = window.Telegram && window.Telegram.WebApp ? window.Telegram.WebApp : null;

function isTelegramWebApp() {
  const ua = navigator.userAgent || "";
  const hasTelegramObject = !!(tg && tg.initDataUnsafe && tg.initDataUnsafe.user);
  return ua.includes("Telegram") || hasTelegramObject;
}

const IN_TELEGRAM = isTelegramWebApp();

if (tg && typeof tg.expand === "function") {
  tg.expand();
}

const initData = IN_TELEGRAM && tg ? tg.initData : null;
const initDataUnsafe = IN_TELEGRAM && tg ? tg.initDataUnsafe : null;

// DOM
const appRootEl = document.getElementById("app-root");
const outsideStubEl = document.getElementById("outside-stub");

const userInfoEl = document.getElementById("user-info");
const statusTextEl = document.getElementById("status-text");
const serversListEl = document.getElementById("servers-list");
const keysListEl = document.getElementById("keys-list");
const plansCardEl = document.getElementById("plans-card");
const plansListEl = document.getElementById("plans-list");
const messageEl = document.getElementById("message");
const btnRefreshKeys = document.getElementById("btn-refresh-keys");

const profileAvatarEl = document.getElementById("profile-avatar");
const profileNameEl = document.getElementById("profile-name");
const profileUsernameEl = document.getElementById("profile-username");
const profileBalanceEl = document.getElementById("profile-balance");
const profileTxListEl = document.getElementById("profile-tx-list");
const btnTopup = document.getElementById("btn-topup");
const btnCheckPayment = document.getElementById("btn-check-payment");

// --- переключаем между приложением и заглушкой ---
if (!IN_TELEGRAM) {
  if (appRootEl) appRootEl.style.display = "none";
  if (outsideStubEl) outsideStubEl.style.display = "flex";
} else {
  if (outsideStubEl) outsideStubEl.style.display = "none";
  if (appRootEl) appRootEl.style.display = "block";
}

// --- заполняем шапку / профиль (если мы в телеге) ---
if (IN_TELEGRAM && initDataUnsafe && initDataUnsafe.user) {
  const u = initDataUnsafe.user;
  const name =
    [u.first_name, u.last_name].filter(Boolean).join(" ") ||
    (u.username ? "@" + u.username : `ID: ${u.id}`);
  if (userInfoEl) {
    userInfoEl.textContent = `Вы вошли как ${name}`;
  }
} else {
  if (userInfoEl) {
    userInfoEl.textContent = "Откройте это приложение через Telegram-бота LunetVPN.";
  }
}

if (profileNameEl && profileUsernameEl && profileAvatarEl) {
  if (IN_TELEGRAM && initDataUnsafe && initDataUnsafe.user) {
    const u = initDataUnsafe.user;
    const name =
      [u.first_name, u.last_name].filter(Boolean).join(" ") ||
      (u.username ? "@" + u.username : `ID: ${u.id}`);

    profileNameEl.textContent = name;
    profileUsernameEl.textContent = u.username ? "@" + u.username : `ID: ${u.id}`;
    if (u.photo_url) {
      profileAvatarEl.src = u.photo_url;
    } else {
      profileAvatarEl.src = "https://t.me/i/userpic/320/0.png";
    }
  } else {
    profileNameEl.textContent = "";
    profileUsernameEl.textContent = "";
    profileAvatarEl.src = "https://t.me/i/userpic/320/0.png";
  }
}

function setMessage(text, type = "ok", { html = false } = {}) {
  if (!messageEl) return;

  if (!text) {
    messageEl.textContent = "";
    messageEl.classList.remove("error", "ok", "visible");
    return;
  }

  messageEl.classList.remove("error", "ok");
  messageEl.classList.add(type === "error" ? "error" : "ok", "visible");

  if (html) {
    messageEl.innerHTML = text;
  } else {
    messageEl.textContent = text;
  }

  setTimeout(() => {
    messageEl.classList.remove("visible");
    messageEl.textContent = "";
    messageEl.classList.remove("error", "ok");
  }, 4000);
}

async function apiRequest(path, body = {}) {
  if (!IN_TELEGRAM) {
    throw new Error("Это приложение работает только внутри Telegram");
  }

  try {
    const payload = {
      initData: initData || null,
      ...body,
    };

    const res = await fetch(BACKEND_URL + path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });

    const text = await res.text();
    let data;
    try {
      data = text ? JSON.parse(text) : {};
    } catch {
      data = { raw: text };
    }

    if (!res.ok) {
      const detail = data.detail || data.error || text || `HTTP ${res.status}`;
      throw new Error(detail);
    }

    if (data.error) {
      throw new Error(data.error);
    }

    return data;
  } catch (e) {
    console.error(e);
    setMessage("Ошибка: " + e.message, "error");
    throw e;
  }
}

// ----- дальше всё как было, только используем apiRequest -----

async function loadStatus() {
  try {
    const data = await apiRequest("/mini/status");
    statusTextEl.textContent = data.statusText || "Статус не задан";
  } catch {
    statusTextEl.textContent = "Не удалось загрузить статус";
  }
}

async function loadServers() {
  serversListEl.textContent = "Загружаю список серверов...";
  try {
    const data = await apiRequest("/mini/servers");
    if (!data.ok && data.reason === "no_subscription") {
      serversListEl.innerHTML =
        "⚠️ У вас нет активной подписки.<br>Оформите её через бота или здесь.";
      return;
    }
    renderServers(data.servers || []);
  } catch {
    serversListEl.textContent = "Ошибка загрузки серверов";
  }
}

function renderServers(servers) {
  if (!servers || !servers.length) {
    serversListEl.textContent = "Серверы недоступны.";
    return;
  }

  serversListEl.innerHTML = "";
  servers.forEach((s) => {
    const item = document.createElement("div");
    item.className = "server-item";

    const header = document.createElement("div");
    header.className = "server-header";

    const title = document.createElement("div");
    title.className = "server-title";
    title.textContent = `${s.country} — ${s.public_host}`;

    const tag = document.createElement("div");
    tag.className = "tag";
    tag.textContent = "Доступен";

    header.appendChild(title);
    header.appendChild(tag);

    const note = document.createElement("div");
    note.className = "server-note";
    note.innerHTML = s.note || "";

    const btn = document.createElement("button");
    btn.textContent = "Создать ключ";
    btn.addEventListener("click", () => createKeyOnServer(s.id, btn));

    item.appendChild(header);
    item.appendChild(note);
    item.appendChild(btn);

    serversListEl.appendChild(item);
  });
}

async function createKeyOnServer(serverId, buttonEl) {
  if (buttonEl) buttonEl.disabled = true;
  setMessage("Создаю ключ...");
  try {
    await apiRequest("/mini/keys/create", { server_id: serverId });
    setMessage("Ключ создан");
    if (tg && tg.HapticFeedback) {
      tg.HapticFeedback.notificationOccurred("success");
    }
    await loadKeys();
    await loadStatus();
  } catch (e) {
    if (e.message.includes("key limit reached")) {
      setMessage(e.message, "error");
    } else if (e.message.includes("key on this server already exists")) {
      setMessage(
        "У вас уже есть ключ на этом сервере. Сначала удалите прежний.",
        "error"
      );
    }
    if (tg && tg.HapticFeedback) {
      tg.HapticFeedback.notificationOccurred("error");
    }
  } finally {
    if (buttonEl) buttonEl.disabled = false;
  }
}

async function loadKeys() {
  keysListEl.textContent = "Загружаю ключи...";
  try {
    const data = await apiRequest("/mini/keys/list");
    if (!data.ok) {
      keysListEl.textContent = "Ключи недоступны.";
      return;
    }
    renderKeys(data.keys || []);
  } catch {
    keysListEl.textContent = "Ошибка загрузки ключей";
  }
}

function renderKeys(keys) {
  if (!keys || !keys.length) {
    keysListEl.textContent = "У вас пока нет ключей.";
    return;
  }

  keysListEl.innerHTML = "";
  keys.forEach((k) => {
    const item = document.createElement("div");
    item.className = "key-item";

    const header = document.createElement("div");
    header.className = "key-header";

    const title = document.createElement("div");
    title.className = "key-title";
    title.textContent = `ID: ${k.uuid || k.id}`;

    const tag = document.createElement("div");
    tag.className = "tag";
    tag.textContent = k.server || "сервер";

    header.appendChild(title);
    header.appendChild(tag);

    const meta = document.createElement("div");
    meta.className = "key-meta";
    const created = k.created_at ? new Date(k.created_at) : null;
    const expires = k.expires_at ? new Date(k.expires_at) : null;
    meta.innerHTML =
      `Создан: ${created ? created.toLocaleString() : "—"}<br>` +
      `Истекает: ${expires ? expires.toLocaleString() : "∞"}`;

    const uri = document.createElement("div");
    uri.className = "key-uri";
    uri.textContent = k.uri;

    const buttons = document.createElement("div");
    buttons.className = "mini-buttons";

    const btnCopy = document.createElement("button");
    btnCopy.className = "secondary";
    btnCopy.textContent = "Скопировать";
    btnCopy.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(k.uri);
        setMessage("Ключ скопирован");
      } catch {
        setMessage("Не удалось скопировать ключ", "error");
      }
    });

    const btnDelete = document.createElement("button");
    btnDelete.textContent = "Удалить";
    btnDelete.addEventListener("click", async () => {
      if (!confirm("Удалить этот ключ?")) return;
      btnDelete.disabled = true;
      try {
        await apiRequest("/mini/keys/delete", { key_id: k.id });
        setMessage("Ключ удалён");
        await loadKeys();
        await loadStatus();
      } catch {
      } finally {
        btnDelete.disabled = false;
      }
    });

    buttons.appendChild(btnCopy);
    buttons.appendChild(btnDelete);

    item.appendChild(header);
    item.appendChild(meta);
    item.appendChild(uri);
    item.appendChild(buttons);

    keysListEl.appendChild(item);
  });
}

async function loadPlans() {
  plansListEl.textContent = "Загружаю тарифы...";
  try {
    const data = await apiRequest("/mini/plans");
    if (!data.ok) {
      plansCardEl.style.display = "none";
      return;
    }
    renderPlans(data.plans || []);
  } catch {
    plansCardEl.style.display = "none";
  }
}

function renderPlans(plans) {
  if (!plans || !plans.length) {
    plansCardEl.style.display = "none";
    return;
  }
  plansCardEl.style.display = "block";
  plansListEl.innerHTML = "";

  plans.forEach((p) => {
    const item = document.createElement("div");
    item.className = "plan-item";

    const header = document.createElement("div");
    header.className = "plan-header";

    const title = document.createElement("div");
    title.className = "plan-title";
    title.textContent = p.name;

    const tag = document.createElement("div");
    tag.className = "tag";
    tag.textContent = `${p.price} ₽ / ${p.period_days} дн.`;

    header.appendChild(title);
    header.appendChild(tag);

    const note = document.createElement("div");
    note.className = "plan-note";
    note.innerHTML = `Лимит ключей: ${p.key_limit}`;

    const btn = document.createElement("button");
    btn.textContent = "Подключить";
    btn.addEventListener("click", () => buyPlan(p.id, btn));

    item.appendChild(header);
    item.appendChild(note);
    item.appendChild(btn);

    plansListEl.appendChild(item);
  });
}

async function buyPlan(planId, btn) {
  if (btn) btn.disabled = true;
  setMessage("Оформляю подписку...");
  try {
    const data = await apiRequest("/mini/subscription/buy", { plan_id: planId });
    if (data.ok) {
      setMessage("Подписка оформлена");
      await loadStatus();
      await loadServers();
    } else {
      setMessage("Не удалось оформить подписку", "error");
    }
  } catch {
    if (tg && tg.HapticFeedback) tg.HapticFeedback.notificationOccurred("error");
  } finally {
    if (btn) btn.disabled = false;
  }
}

async function loadProfile() {
  try {
    const data = await apiRequest("/mini/profile");

    if (data.user && profileBalanceEl) {
      profileBalanceEl.textContent = data.user.balance ?? 0;
    }

    if (data.transactions && profileTxListEl) {
      renderTransactionsProfile(data.transactions);
    }
  } catch (e) {
    console.error(e);
    if (profileTxListEl) {
      profileTxListEl.textContent = "Не удалось загрузить историю транзакций";
    }
  }
}

function renderTransactionsProfile(txs) {
  if (!txs.length) {
    profileTxListEl.textContent = "У вас пока нет транзакций.";
    return;
  }

  profileTxListEl.innerHTML = "";
  txs.forEach((t) => {
    const item = document.createElement("div");
    item.className = "tx-item";

    const row = document.createElement("div");
    row.className = "tx-row";

    const title = document.createElement("div");
    title.textContent = t.payment_system || "Пополнение";

    const amount = document.createElement("div");
    amount.className = "tx-amount";
    const sign = t.paid ? "+" : "";
    amount.textContent = `${sign}${t.amount} ₽`;
    amount.classList.add(t.paid ? "plus" : "minus");

    row.appendChild(title);
    row.appendChild(amount);

    const meta = document.createElement("div");
    meta.className = "tx-meta";
    const created = t.created_at ? new Date(t.created_at) : null;
    const createdTxt = created ? created.toLocaleString() : "";
    meta.textContent = `${createdTxt} • ${t.order_id || ""} ${
      t.paid ? "• оплачено" : ""
    }`;

    item.appendChild(row);
    item.appendChild(meta);

    profileTxListEl.appendChild(item);
  });
}

if (btnTopup) {
  btnTopup.addEventListener("click", async () => {
    if (!IN_TELEGRAM) {
      setMessage("Пополнение доступно только из Telegram", "error");
      return;
    }

    let popup = null;
    if (!tg) {
      popup = window.open("", "_blank");
    }

    let amountStr = prompt("Введите сумму пополнения (в рублях):", "100");
    if (!amountStr) {
      if (popup) popup.close();
      return;
    }

    const amount = Number(amountStr);
    if (!Number.isFinite(amount) || amount <= 0) {
      if (popup) popup.close();
      setMessage("Неверная сумма", "error");
      return;
    }

    btnTopup.disabled = true;
    setMessage("Создаю платёж...");

    try {
      const data = await apiRequest("/mini/balance/topup", { amount: amount });

      if (!data.ok) {
        if (popup) popup.close();
        setMessage("Не удалось создать платёж", "error");
        return;
      }

      const url = data.payment_url;
      if (!url) {
        if (popup) popup.close();
        setMessage("Платёж создан, но нет URL", "error");
        return;
      }

      const linkHtml = `
        Счёт создан. Нажмите:
        <a href="${url}" target="_blank" rel="noopener noreferrer">Оплатить</a>
      `;
      setMessage(linkHtml, "ok", { html: true });

      if (tg && tg.openLink) {
        tg.openLink(url);
        if (popup) popup.close();
      } else if (popup) {
        popup.location.href = url;
      } else {
        window.open(url, "_blank");
      }
    } catch (e) {
      if (popup) popup.close();
    } finally {
      btnTopup.disabled = false;
    }
  });
}

if (btnCheckPayment) {
  btnCheckPayment.addEventListener("click", async () => {
    if (!IN_TELEGRAM) {
      setMessage("Проверка доступна только из Telegram", "error");
      return;
    }

    btnCheckPayment.disabled = true;
    setMessage("Проверяю статус платежа...");

    try {
      const data = await apiRequest("/mini/balance/check");

      if (!data.ok && data.reason === "no_pending") {
        setMessage("Нет незавершённых платежей", "error");
        return;
      }

      if (data.transaction && data.transaction.paid) {
        setMessage("Платёж успешно оплачен, баланс обновлён");
        await loadProfile();
      } else {
        setMessage(
          "Платёж пока не оплачен. Статус: " +
            (data.transaction?.status_raw || "неизвестен"),
          "error"
        );
      }
    } catch (e) {
    } finally {
      btnCheckPayment.disabled = false;
    }
  });
}

const pages = document.querySelectorAll(".page");
const tabButtons = document.querySelectorAll(".tab-button");

function showPage(name) {
  pages.forEach((page) => {
    page.classList.toggle("page-active", page.dataset.page === name);
  });
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.target === name);
  });
}

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => {
    const target = btn.dataset.target;
    showPage(target);

    if (!IN_TELEGRAM) return;

    if (target === "keys") {
      loadKeys();
    } else if (target === "servers") {
      loadServers();
    } else if (target === "profile") {
      loadProfile();
    } else if (target === "tariffs") {
      loadStatus();
      loadPlans();
    }
  });
});

if (IN_TELEGRAM) {
  showPage("tariffs");

  if (btnRefreshKeys) {
    btnRefreshKeys.addEventListener("click", loadKeys);
  }

  (async () => {
    await loadStatus();
    await loadServers();
    await loadKeys();
    await loadPlans();
    await loadProfile();
  })();
}
