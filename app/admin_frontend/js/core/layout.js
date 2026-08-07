async function ensureAuthOrRedirect() {
  const ok = await hasAdminSession();
  if (!ok) {
    window.location.replace("/admin/login");
    return false;
  }
  return true;
}

function statusBadge(status) {
  const s = String(status || "").toLowerCase();
  const dict = {
    active: "\u0410\u043a\u0442\u0438\u0432\u043d\u0430",
    expired: "\u0418\u0441\u0442\u0435\u043a\u043b\u0430",
    canceled: "\u041e\u0442\u043c\u0435\u043d\u0435\u043d\u0430",
    past_due: "\u041f\u0440\u043e\u0441\u0440\u043e\u0447\u0435\u043d\u0430",
    paid: "\u041e\u043f\u043b\u0430\u0447\u0435\u043d\u043e",
    unpaid: "\u041d\u0435 \u043e\u043f\u043b\u0430\u0447\u0435\u043d\u043e",
    yes: "\u0414\u0430",
    no: "\u041d\u0435\u0442",
    ok: "\u041e\u043a",
    ban: "\u0417\u0430\u0431\u0430\u043d\u0435\u043d",
    offline: "\u041e\u0444\u0444\u043b\u0430\u0439\u043d",
    pending: "\u041d\u0430 \u043f\u0440\u043e\u0432\u0435\u0440\u043a\u0435",
    approved: "\u041f\u043e\u0434\u0442\u0432\u0435\u0440\u0436\u0434\u0435\u043d\u0430",
    rejected: "\u041e\u0442\u043a\u043b\u043e\u043d\u0435\u043d\u0430",
    disabled: "\u041e\u0442\u043a\u043b\u044e\u0447\u0435\u043d\u0430",
  };

  const label = dict[s] || String(status || "\u2014");

  if (["active", "yes", "paid", "ok", "approved"].includes(s)) {
    return `<span class="badge ok">${label}</span>`;
  }
  if (["expired", "canceled", "unpaid", "ban", "offline", "rejected"].includes(s)) {
    return `<span class="badge danger">${label}</span>`;
  }
  return `<span class="badge warn">${label}</span>`;
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function safeText(v) {
  if (v === null || v === undefined || v === "") return "—";
  if (typeof v === "object") return "объект";
  return escapeHtml(v);
}

const TABLER_ICON_PATHS = {
  check: '<path d="M5 12l5 5l10 -10" />',
  x: '<path d="M18 6l-12 12" /><path d="M6 6l12 12" />',
  edit: '<path d="M4 20h4l10.5 -10.5a2.828 2.828 0 1 0 -4 -4l-10.5 10.5v4" /><path d="M13.5 6.5l4 4" />',
  trash: '<path d="M4 7h16" /><path d="M10 11v6" /><path d="M14 11v6" /><path d="M5 7l1 12a2 2 0 0 0 2 2h8a2 2 0 0 0 2 -2l1 -12" /><path d="M9 7v-3h6v3" />',
  download: '<path d="M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2" /><path d="M7 11l5 5l5 -5" /><path d="M12 4v12" />',
  copy: '<path d="M8 8m0 2a2 2 0 0 1 2 -2h8a2 2 0 0 1 2 2v8a2 2 0 0 1 -2 2h-8a2 2 0 0 1 -2 -2z" /><path d="M16 8v-2a2 2 0 0 0 -2 -2h-8a2 2 0 0 0 -2 2v8a2 2 0 0 0 2 2h2" />',
  eye: '<path d="M10 12a2 2 0 1 0 4 0a2 2 0 0 0 -4 0" /><path d="M21 12c-2.4 4 -5.4 6 -9 6c-3.6 0 -6.6 -2 -9 -6c2.4 -4 5.4 -6 9 -6c3.6 0 6.6 2 9 6" />',
  eyeOff: '<path d="M10.585 10.587a2 2 0 0 0 2.829 2.828" /><path d="M16.681 16.673a8.717 8.717 0 0 1 -4.681 1.327c-3.6 0 -6.6 -2 -9 -6c1.272 -2.12 2.712 -3.678 4.32 -4.674" /><path d="M10.18 6.18a8.737 8.737 0 0 1 1.82 -.18c3.6 0 6.6 2 9 6a13.69 13.69 0 0 1 -1.475 2.207" /><path d="M3 3l18 18" />',
  arrowUp: '<path d="M12 5l0 14" /><path d="M18 11l-6 -6" /><path d="M6 11l6 -6" />',
  arrowDown: '<path d="M12 5l0 14" /><path d="M18 13l-6 6" /><path d="M6 13l6 6" />',
  plus: '<path d="M12 5l0 14" /><path d="M5 12l14 0" />',
  save: '<path d="M6 4h10l4 4v10a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2" /><path d="M12 14m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0" /><path d="M14 4l0 4l-6 0l0 -4" />',
  external: '<path d="M12 6h-6a2 2 0 0 0 -2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2 -2v-6" /><path d="M11 13l9 -9" /><path d="M15 4h5v5" />',
  info: '<path d="M12 9h.01" /><path d="M11 12h1v4h1" /><path d="M12 3a9 9 0 1 0 0 18a9 9 0 0 0 0 -18" />',
  dots: '<path d="M5 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" /><path d="M12 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" /><path d="M19 12m-1 0a1 1 0 1 0 2 0a1 1 0 1 0 -2 0" />',
  sun: '<path d="M12 12m-4 0a4 4 0 1 0 8 0a4 4 0 1 0 -8 0" /><path d="M3 12h1" /><path d="M20 12h1" /><path d="M12 3v1" /><path d="M12 20v1" /><path d="M5.6 5.6l.7 .7" /><path d="M17.7 17.7l.7 .7" /><path d="M18.4 5.6l-.7 .7" /><path d="M6.3 17.7l-.7 .7" />',
  moon: '<path d="M12 3c.132 0 .263 .003 .393 .01a7.5 7.5 0 0 0 7.92 10.865a9 9 0 1 1 -8.313 -10.875z" />',
  user: '<path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0" /><path d="M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2" />',
  userCog: '<path d="M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0" /><path d="M6 21v-2a4 4 0 0 1 4 -4h2.5" /><path d="M19.001 19m-2 0a2 2 0 1 0 4 0a2 2 0 1 0 -4 0" /><path d="M19.001 15.5v1.5" /><path d="M19.001 21v1.5" /><path d="M22.032 17.25l-1.299 .75" /><path d="M17.27 20l-1.3 .75" /><path d="M15.97 17.25l1.3 .75" /><path d="M20.733 20l1.3 .75" />',
  users: '<path d="M9 7a4 4 0 1 0 0 8a4 4 0 0 0 0 -8" /><path d="M3 21v-2a4 4 0 0 1 4 -4h4" /><path d="M16 11a3 3 0 1 0 0 -6" /><path d="M21 21v-2a4 4 0 0 0 -3 -3.85" />',
  calendarStats: '<path d="M4 7a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v11a2 2 0 0 1 -2 2h-12a2 2 0 0 1 -2 -2z" /><path d="M16 3v4" /><path d="M8 3v4" /><path d="M4 11h16" /><path d="M8 16h2l2 -3l2 5l2 -4h2" />',
  receipt: '<path d="M5 21v-16a2 2 0 0 1 2 -2h10a2 2 0 0 1 2 2v16l-3 -2l-2 2l-2 -2l-2 2l-2 -2z" /><path d="M9 7h6" /><path d="M9 11h6" /><path d="M9 15h4" />',
  creditCard: '<path d="M3 8a3 3 0 0 1 3 -3h12a3 3 0 0 1 3 3v8a3 3 0 0 1 -3 3h-12a3 3 0 0 1 -3 -3z" /><path d="M3 10h18" /><path d="M7 15h.01" /><path d="M11 15h2" />',
  wallet: '<path d="M17 8v-2a2 2 0 0 0 -2 -2h-10a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2 -2v-2" /><path d="M16 12h4v4h-4a2 2 0 0 1 0 -4" />',
  ticket: '<path d="M15 5l0 2" /><path d="M15 11l0 2" /><path d="M15 17l0 2" /><path d="M5 5h14a2 2 0 0 1 2 2v3a2 2 0 0 0 0 4v3a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-3a2 2 0 0 0 0 -4v-3a2 2 0 0 1 2 -2" />',
  link: '<path d="M9 15l6 -6" /><path d="M11 6l.5 -.5a3.5 3.5 0 0 1 5 5l-.5 .5" /><path d="M13 18l-.5 .5a3.5 3.5 0 0 1 -5 -5l.5 -.5" />',
  speakerphone: '<path d="M18 8a3 3 0 0 1 0 6" /><path d="M10 8v11a1 1 0 0 1 -1 1h-1a1 1 0 0 1 -1 -1v-5" /><path d="M12 8l5 -3v12l-5 -3h-7a2 2 0 0 1 -2 -2v-2a2 2 0 0 1 2 -2h7" />',
  fileText: '<path d="M14 3v4a1 1 0 0 0 1 1h4" /><path d="M17 21h-10a2 2 0 0 1 -2 -2v-14a2 2 0 0 1 2 -2h7l5 5v11a2 2 0 0 1 -2 2z" /><path d="M9 9h1" /><path d="M9 13h6" /><path d="M9 17h6" />',
  shield: '<path d="M12 3l7 4v5c0 5 -3.5 7.5 -7 9c-3.5 -1.5 -7 -4 -7 -9v-5z" /><path d="M9 12l2 2l4 -4" />',
  logout: '<path d="M14 8v-2a2 2 0 0 0 -2 -2h-5a2 2 0 0 0 -2 2v12a2 2 0 0 0 2 2h5a2 2 0 0 0 2 -2v-2" /><path d="M9 12h12" /><path d="M18 9l3 3l-3 3" />',
};

function tablerIcon(name, className = "") {
  const key = String(name || "").replace(/-([a-z])/g, (_, letter) => letter.toUpperCase());
  const paths = TABLER_ICON_PATHS[key] || TABLER_ICON_PATHS.info;
  return `<svg class="tabler-icon ${className || ""}" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" aria-hidden="true" focusable="false" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">${paths}</svg>`;
}

function inferActionIcon(label, className = "") {
  const text = String(label || "").toLowerCase();
  const cls = String(className || "").toLowerCase();
  if (cls.includes("danger") || text.includes("удал") || text.includes("отклон") || text.includes("выключ")) return "trash";
  if (cls.includes("success") || text.includes("подтверд") || text.includes("включ")) return "check";
  if (text.includes("измен") || text.includes("редакт")) return "edit";
  if (text.includes("сохран")) return "save";
  if (text.includes("скач")) return "download";
  if (text.includes("копир")) return "copy";
  if (text.includes("откры")) return "external";
  if (text.includes("детал")) return "eye";
  if (text.includes("скры")) return "eyeOff";
  if (text.includes("выше") || text.includes("поднять")) return "arrowUp";
  if (text.includes("ниже") || text.includes("опустить")) return "arrowDown";
  if (text.includes("трафик") || text.includes("+")) return "plus";
  return "dots";
}

function inferContextIcon(title = "") {
  const text = String(title || "").toLowerCase();
  if (text.includes("подпис") || text.includes("РїРѕРґРїРёСЃ")) return "calendarStats";
  if (text.includes("тариф") || text.includes("С‚Р°СЂРёС„")) return "receipt";
  if (text.includes("транзак") || text.includes("плат") || text.includes("С‚СЂР°РЅР·Р°Рє") || text.includes("РїР»Р°С‚")) return "creditCard";
  if (text.includes("вывод") || text.includes("РІС‹РІРѕРґ")) return "wallet";
  if (text.includes("рефера") || text.includes("РµС„РµСЂР")) return "users";
  if (text.includes("парт") || text.includes("ссыл") || text.includes("РїР°СЂС‚") || text.includes("СЃСЃС‹Р»")) return "link";
  if (text.includes("промо") || text.includes("РїСЂРѕРјРѕ")) return "ticket";
  if (text.includes("рассыл") || text.includes("СЂР°СЃСЃС‹Р»")) return "speakerphone";
  if (text.includes("лог") || text.includes("файл") || text.includes("Р»РѕРі") || text.includes("С„Р°Р№Р»")) return "fileText";
  if (text.includes("польз") || text.includes("user") || text.includes("РїРѕР»СЊР·")) return "user";
  if (text.includes("статус") || text.includes("бан") || text.includes("СЃС‚Р°С‚") || text.includes("Р±Р°РЅ")) return "shield";
  return "fileText";
}

function formatDateTime(value) {
  if (!value) return "—";
  const dt = new Date(value);
  if (Number.isNaN(dt.getTime())) return String(value);
  return dt.toLocaleString("ru-RU");
}

function bindEnterSubmit(inputIds, buttonId) {
  const btn = q(buttonId);
  if (!btn) return;
  inputIds.forEach((id) => {
    const el = q(id);
    if (!el) return;
    el.addEventListener("keydown", (e) => {
      if (e.key === "Enter") {
        e.preventDefault();
        btn.click();
      }
    });
  });
}

function closeAllFancySelects() {
  document.querySelectorAll(".fancy-select.open").forEach((el) => el.classList.remove("open"));
}

function closeAllPopupMenus(except = null) {
  document.querySelectorAll(".popup-menu.open").forEach((menu) => {
    if (menu === except) return;
    menu.classList.remove("open");
    const trigger = menu.querySelector(".popup-menu__trigger");
    if (trigger) trigger.setAttribute("aria-expanded", "false");
  });
}

function initPopupMenus(root = document) {
  const scope = root instanceof HTMLElement || root instanceof Document ? root : document;
  scope.querySelectorAll(".popup-menu").forEach((menu) => {
    if (menu.dataset.popupInit === "1") return;
    menu.dataset.popupInit = "1";
    const trigger = menu.querySelector(".popup-menu__trigger");
    if (!trigger) return;

    trigger.setAttribute("aria-expanded", "false");
    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = menu.classList.contains("open");
      closeAllPopupMenus(menu);
      menu.classList.toggle("open", !isOpen);
      trigger.setAttribute("aria-expanded", !isOpen ? "true" : "false");
    });
  });
}

function initFancySelects(root = document) {
  const scope = root instanceof HTMLElement || root instanceof Document ? root : document;
  scope.querySelectorAll("select").forEach((select) => {
    if (select.dataset.fancyInit === "1") return;
    select.dataset.fancyInit = "1";
    select.classList.add("native-select-hidden");

    const wrap = document.createElement("div");
    wrap.className = "fancy-select";
    if (select.classList.contains("top-select")) wrap.classList.add("fancy-select-top");

    const trigger = document.createElement("button");
    trigger.type = "button";
    trigger.className = "fancy-select-trigger";

    const label = document.createElement("span");
    label.className = "fancy-select-label";

    const chevron = document.createElement("span");
    chevron.className = "fancy-select-chevron";
    chevron.innerHTML = "<svg viewBox='0 0 20 20' aria-hidden='true'><path d='M5 7.5L10 12.5L15 7.5' /></svg>";

    const list = document.createElement("div");
    list.className = "fancy-select-list";

    const syncLabel = () => {
      const opt = select.options[select.selectedIndex];
      label.textContent = opt ? opt.textContent : "";
    };

    Array.from(select.options).forEach((opt) => {
      const item = document.createElement("button");
      item.type = "button";
      item.className = "fancy-select-item";
      item.textContent = opt.textContent || "";
      item.dataset.value = opt.value;
      if (opt.disabled) item.disabled = true;
      item.addEventListener("click", () => {
        if (item.disabled) return;
        select.value = item.dataset.value || "";
        select.dispatchEvent(new Event("change", { bubbles: true }));
        syncLabel();
        closeAllFancySelects();
      });
      list.appendChild(item);
    });

    select.addEventListener("change", syncLabel);
    syncLabel();

    trigger.append(label, chevron);
    trigger.addEventListener("click", (e) => {
      e.stopPropagation();
      const isOpen = wrap.classList.contains("open");
      closeAllFancySelects();
      if (!isOpen) wrap.classList.add("open");
    });

    wrap.append(trigger, list);
    select.insertAdjacentElement("afterend", wrap);
  });
}

document.addEventListener("click", (e) => {
  if (!e.target.closest(".fancy-select")) closeAllFancySelects();
  if (!e.target.closest(".popup-menu")) closeAllPopupMenus();
});

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") {
    closeAllFancySelects();
    closeAllPopupMenus();
  }
});

const ADMIN_MENU = [
  { key: "dashboard", href: "/admin/dashboard", label: "Обзор", icon: "overview" },
  { key: "maintenance", href: "/admin/maintenance", label: "Техработы", icon: "settings" },
  { key: "diagnostics", href: "/admin/diagnostics", label: "Диагностика", icon: "diagnostics" },
  { key: "admins", href: "/admin/admins", label: "Администраторы", icon: "users" },
  { key: "legal", href: "/admin/legal", label: "Документы", icon: "logs" },
  { key: "users", href: "/admin/users", label: "Пользователи", icon: "users" },
  { key: "subscriptions", href: "/admin/subscriptions", label: "Подписки", icon: "subs" },
  { key: "plans", href: "/admin/plans", label: "Тарифы", icon: "plans" },
  { key: "transactions", href: "/admin/transactions", label: "Транзакции", icon: "tx" },
  { key: "withdrawals", href: "/admin/withdrawals", label: "Заявки на вывод", icon: "wd" },
  { key: "referrals", href: "/admin/referrals", label: "Реферальная система", icon: "ref" },
  { key: "partners", href: "/admin/partners", label: "Партнерка", icon: "partner" },
  { key: "promocodes", href: "/admin/promocodes", label: "Промокоды", icon: "promo" },
  { key: "broadcast", href: "/admin/broadcast", label: "Рассылки", icon: "mail" },
  { key: "logs", href: "/admin/logs", label: "Логи", icon: "logs" },
];
const SUPPORT_MENU_KEYS = new Set(["users", "subscriptions", "transactions", "referrals"]);
const ADMIN_MENU_GROUPS = [
  { label: "", keys: ["dashboard", "maintenance", "diagnostics", "admins", "legal"] },
  { label: "Управление", keys: ["users", "subscriptions", "plans", "transactions", "withdrawals"] },
  { label: "Продвижение", keys: ["referrals", "partners", "promocodes", "broadcast"] },
  { label: "Система", keys: ["logs"] },
];

const DESKTOP_SIDEBAR_STORAGE_KEY = "adminDesktopSidebarCollapsed";
const ADMIN_THEME_STORAGE_KEY = "adminTheme";

function menuIcon(kind) {
  const map = {
    overview: "<path d='M3 7a2 2 0 0 1 2 -2h14a2 2 0 0 1 2 2v10a2 2 0 0 1 -2 2h-14a2 2 0 0 1 -2 -2v-10'/><path d='M6 8h.01'/><path d='M9 8h.01'/>",
    users: "<path d='M8 7a4 4 0 1 0 8 0a4 4 0 0 0 -8 0'/><path d='M6 21v-2a4 4 0 0 1 4 -4h4a4 4 0 0 1 4 4v2'/>",
    subs: "<path d='M12 21h-6a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v4.5'/><path d='M16 3v4'/><path d='M8 3v4'/><path d='M4 11h16'/><path d='M17 17a2 2 0 1 0 4 0a2 2 0 1 0 -4 0'/><path d='M22 22a2 2 0 0 0 -2 -2h-2a2 2 0 0 0 -2 2'/>",
    plans: "<path d='M3 19a9 9 0 0 1 9 0a9 9 0 0 1 9 0'/><path d='M3 6a9 9 0 0 1 9 0a9 9 0 0 1 9 0'/><path d='M3 6l0 13'/><path d='M12 6l0 13'/><path d='M21 6l0 13'/>",
    tx: "<path d='M13 21h-7a2 2 0 0 1 -2 -2v-12a2 2 0 0 1 2 -2h12a2 2 0 0 1 2 2v3'/><path d='M16 3v4'/><path d='M8 3v4'/><path d='M4 11h12.5'/><path d='M21 15h-2.5a1.5 1.5 0 0 0 0 3h1a1.5 1.5 0 0 1 0 3h-2.5'/><path d='M19 21v1m0 -8v1'/>",
    wd: "<path d='M12 19h-6a3 3 0 0 1 -3 -3v-8a3 3 0 0 1 3 -3h12a3 3 0 0 1 3 3v4.5'/><path d='M3 10h18'/><path d='M16 19h6'/><path d='M19 16l3 3l-3 3'/><path d='M7.005 15h.005'/><path d='M11 15h2'/>",
    ref: "<circle cx='7.5' cy='8.5' r='2'/><circle cx='16.5' cy='8.5' r='2'/><circle cx='12' cy='15.5' r='2.2'/><path d='M9 9.5l2 4M15 9.5l-2 4'/>",
    partner: "<path d='M9 7h6a3 3 0 0 1 0 6H9a3 3 0 0 1 0-6Z'/><path d='M7 12h10a3 3 0 0 1 0 6H7a3 3 0 0 1 0-6Z'/>",
    promo: "<path d='M7 8.5h10a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2Z'/><path d='M12 8.5v7'/><path d='M9.1 11.4h.01M14.9 12.6h.01'/>",
    mail: "<rect x='4.5' y='6.5' width='15' height='11' rx='2'/><path d='M5.5 8l6.5 4.8L18.5 8'/>",
    settings: "<circle cx='12' cy='12' r='3'/><path d='M19 12a7 7 0 0 0-.1-1l2-1.4l-2-3.4l-2.4.9a7 7 0 0 0-1.7-1l-.4-2.5h-4.8l-.4 2.5a7 7 0 0 0-1.7 1l-2.4-.9l-2 3.4l2 1.4a7 7 0 0 0 0 2l-2 1.4l2 3.4l2.4-.9a7 7 0 0 0 1.7 1l.4 2.5h4.8l.4-2.5a7 7 0 0 0 1.7-1l2.4.9l2-3.4l-2-1.4a7 7 0 0 0 .1-1z'/>",
    diagnostics: "<path d='M4 19h16'/><path d='M5 5v10h4v-6h4v4h6v2'/><path d='M15 5h4v4'/><path d='M19 5l-7 7'/>",
    logs: "<path d='M7 5.5h8l3 3V18a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 18V7A1.5 1.5 0 0 1 7.5 5.5Z'/><path d='M15 5.5V9h3'/><path d='M9 12h6M9 15h6'/>",
  };
  const icon = map[kind] || map.overview;
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${icon}</svg>`;
}

function getAdminRole() {
  return window.ADMIN_SESSION?.role || "superadmin";
}

function getVisibleAdminMenu() {
  if (getAdminRole() === "support") {
    return ADMIN_MENU.filter((item) => SUPPORT_MENU_KEYS.has(item.key));
  }
  return ADMIN_MENU;
}

function canAccessAdminPage(activeKey) {
  return getAdminRole() !== "support" || SUPPORT_MENU_KEYS.has(activeKey);
}

function renderMenu(activeKey) {
  const visible = getVisibleAdminMenu();
  const visibleByKey = new Map(visible.map((item) => [item.key, item]));
  const groupedKeys = new Set();

  const groupedHtml = ADMIN_MENU_GROUPS.map((group) => {
    const links = group.keys
      .map((key) => {
        const item = visibleByKey.get(key);
        if (!item) return "";
        groupedKeys.add(key);
        return `
          <a href="${item.href}" data-menu-key="${item.key}" class="${activeKey === item.key ? "active" : ""}">
            <span class="menu-ico">${menuIcon(item.icon)}</span>
            <span class="menu-label">${item.label}</span>
          </a>
        `;
      })
      .join("");
    if (!links) return "";
    const title = group.label ? `<div class="menu-section-title">${group.label}</div>` : "";
    return `<div class="menu-section">${title}${links}</div>`;
  }).join("");

  const rest = visible
    .filter((item) => !groupedKeys.has(item.key))
    .map((item) => `
      <a href="${item.href}" data-menu-key="${item.key}" class="${activeKey === item.key ? "active" : ""}">
        <span class="menu-ico">${menuIcon(item.icon)}</span>
        <span class="menu-label">${item.label}</span>
      </a>
    `)
    .join("");

  return rest ? `${groupedHtml}<div class="menu-section"><div class="menu-section-title">Другое</div>${rest}</div>` : groupedHtml;
}

function renderQuickNav() {
  return `
    <option value="">Быстрый переход</option>
    ${getVisibleAdminMenu().filter((m) => m.key !== "dashboard").map((m) => `<option value="${m.href}">${m.label}</option>`).join("")}
  `;
}

function renderShell({ activeKey, title, subtitle = "", contentHtml = "" }) {
  if (!canAccessAdminPage(activeKey)) {
    window.location.replace("/admin/users");
    return;
  }
  document.body.innerHTML = `
    <button id="mobile_nav_overlay" class="mobile-nav-overlay" type="button" aria-label="Закрыть меню"></button>

    <div class="app tailadmin-shell">
      <aside class="sidebar tailadmin-sidebar">
        <nav class="menu">${renderMenu(activeKey)}</nav>

        <div class="sidebar-footer">
          <button id="logout" class="btn-logout">${tablerIcon("logout", "btn-logout__icon")}<span>Выход</span></button>
        </div>
      </aside>

      <main class="main tailadmin-main">
        <header class="topbar tailadmin-header">
          <div class="topbar-left">
            <button id="mobile_nav_toggle" class="mobile-nav-toggle" type="button" aria-label="Открыть меню">
              <span></span><span></span><span></span>
            </button>
            <button id="desktop_topbar_toggle" class="desktop-topbar-toggle" type="button" aria-label="Свернуть меню" title="Свернуть меню">
              <span></span><span></span><span></span>
            </button>
            <div class="topbar-title">Админ-панель</div>
          </div>
          <div class="topbar-right">
            <button id="theme_toggle" class="theme-toggle" type="button" aria-label="Темная тема" title="Переключить тему">
              ${tablerIcon("sun", "theme-toggle__icon theme-toggle__icon--sun")}
              ${tablerIcon("moon", "theme-toggle__icon theme-toggle__icon--moon")}
            </button>
          </div>
        </header>

        <section class="page-shell tailadmin-content">
          <div class="page-header-card tailadmin-page-heading">
            <div>
              <div class="crumbs">Главная / ${title}</div>
              <div class="page-title">${title}</div>
              <div class="page-sub">${subtitle}</div>
            </div>
          </div>

          <section id="content">${contentHtml}</section>
        </section>
      </main>
    </div>
  `;

  const logoutAdmin = async () => {
    try {
      await fetch(`${API_BASE}/api/admin/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {}
    window.location.replace("/admin/login");
  };

  q("logout").addEventListener("click", logoutAdmin);

  const applyTheme = (theme) => {
    const isDark = theme === "dark";
    document.body.classList.toggle("dark", isDark);
    document.documentElement.dataset.adminTheme = isDark ? "dark" : "light";
    const themeToggle = q("theme_toggle");
    if (themeToggle) {
      themeToggle.classList.toggle("is-dark", isDark);
      themeToggle.setAttribute("aria-label", isDark ? "Светлая тема" : "Темная тема");
      themeToggle.setAttribute("title", isDark ? "Включить светлую тему" : "Включить темную тему");
    }
  };

  let savedTheme = "light";
  try {
    savedTheme = window.localStorage.getItem(ADMIN_THEME_STORAGE_KEY) || "light";
  } catch {}
  applyTheme(savedTheme === "dark" ? "dark" : "light");

  const applyDesktopSidebarState = (collapsed) => {
    document.body.classList.toggle("desktop-sidebar-collapsed", collapsed);
    const desktopToggles = [q("desktop_topbar_toggle")].filter(Boolean);
    desktopToggles.forEach((toggle) => {
      toggle.setAttribute("aria-label", collapsed ? "Развернуть меню" : "Свернуть меню");
      toggle.setAttribute("title", collapsed ? "Развернуть меню" : "Свернуть меню");
    });
  };

  const setDesktopSidebarCollapsed = (collapsed) => {
    applyDesktopSidebarState(collapsed);
    try {
      window.localStorage.setItem(DESKTOP_SIDEBAR_STORAGE_KEY, collapsed ? "1" : "0");
    } catch {}
  };

  const toggleDesktopSidebar = () => {
    if (window.innerWidth <= 980) return;
    setDesktopSidebarCollapsed(!document.body.classList.contains("desktop-sidebar-collapsed"));
  };

  let desktopCollapsed = false;
  try {
    desktopCollapsed = window.localStorage.getItem(DESKTOP_SIDEBAR_STORAGE_KEY) === "1";
  } catch {}
  applyDesktopSidebarState(desktopCollapsed);

  const openMobileNav = () => document.body.classList.add("mobile-nav-open");
  const closeMobileNav = () => document.body.classList.remove("mobile-nav-open");

  const navToggle = q("mobile_nav_toggle");
  const navOverlay = q("mobile_nav_overlay");
  const desktopTopbarToggle = q("desktop_topbar_toggle");
  const themeToggle = q("theme_toggle");

  if (navToggle) {
    navToggle.addEventListener("click", () => {
      if (document.body.classList.contains("mobile-nav-open")) closeMobileNav();
      else openMobileNav();
    });
  }
  if (desktopTopbarToggle) {
    desktopTopbarToggle.addEventListener("click", toggleDesktopSidebar);
  }
  if (themeToggle) {
    themeToggle.addEventListener("click", () => {
      const nextTheme = document.body.classList.contains("dark") ? "light" : "dark";
      applyTheme(nextTheme);
      try {
        window.localStorage.setItem(ADMIN_THEME_STORAGE_KEY, nextTheme);
      } catch {}
    });
  }
  if (navOverlay) navOverlay.addEventListener("click", closeMobileNav);

  window.addEventListener("resize", () => {
    if (window.innerWidth > 980) {
      closeMobileNav();
      let collapsed = false;
      try {
        collapsed = window.localStorage.getItem(DESKTOP_SIDEBAR_STORAGE_KEY) === "1";
      } catch {}
      applyDesktopSidebarState(collapsed);
      return;
    }
    document.body.classList.remove("desktop-sidebar-collapsed");
  });

  const menuEl = document.querySelector(".menu");
  if (menuEl) {
    menuEl.addEventListener("click", (e) => {
      const link = e.target.closest("a");
      if (!link) return;
      menuEl.querySelectorAll("a").forEach((el) => el.classList.remove("active-tap"));
      link.classList.add("active-tap");
      closeMobileNav();
    });
  }

  initFancySelects(document);
  initPopupMenus(document);
}

async function renderSessionInfo() {
  return;
}

function renderPager(meta, prevBtn, nextBtn, label) {
  label.textContent = `Страница ${meta.page} из ${meta.pages}`;
  prevBtn.disabled = meta.page <= 1;
  nextBtn.disabled = meta.page >= meta.pages;
}

function sortableTh(label, key, activeKey, direction = "asc", extraClass = "") {
  const active = key === activeKey;
  const dir = String(direction || "asc").toLowerCase() === "desc" ? "desc" : "asc";
  return `
    <th class="${extraClass}">
      <button class="sort-th ${active ? "is-active" : ""}" data-sort-key="${key}" data-sort-dir="${active ? dir : ""}" type="button">
        <span>${safeText(label)}</span>
        <span class="sort-th__icon" aria-hidden="true"></span>
      </button>
    </th>
  `;
}

function bindSortableTable(root, state, onChange) {
  const scope = root instanceof HTMLElement || root instanceof Document ? root : document;
  scope.querySelectorAll(".sort-th[data-sort-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      const key = button.dataset.sortKey || "";
      if (!key) return;
      const currentKey = state.sortBy;
      const currentDir = String(state.sortDir || "asc").toLowerCase() === "desc" ? "desc" : "asc";
      state.sortBy = key;
      state.sortDir = currentKey === key && currentDir === "asc" ? "desc" : "asc";
      state.page = 1;
      await onChange(button);
    });
  });
}

function setTableRefreshing(tableOrTbody, refreshing) {
  const tableWrap = tableOrTbody?.closest?.(".table-wrap") || null;
  tableWrap?.classList.toggle("table-wrap--refreshing", Boolean(refreshing));
}

function closeAllRowActionMenus(except = null) {
  document.querySelectorAll(".row-action-menu.open").forEach((menu) => {
    if (menu === except) return;
    menu.classList.remove("open");
    menu.closest("td")?.classList.remove("table-actions-cell--open");
    menu.querySelector(".row-action-menu__trigger")?.setAttribute("aria-expanded", "false");
  });
}

function initRowActionMenus(root = document) {
  const scope = root instanceof HTMLElement || root instanceof Document ? root : document;
  scope.querySelectorAll(".row-action-menu").forEach((menu) => {
    if (menu.dataset.rowMenuInit === "1") return;
    menu.dataset.rowMenuInit = "1";
    const trigger = menu.querySelector(".row-action-menu__trigger");
    if (!trigger) return;
    trigger.setAttribute("aria-expanded", "false");
    trigger.addEventListener("click", (event) => {
      event.stopPropagation();
      const isOpen = menu.classList.contains("open");
      closeAllRowActionMenus(menu);
      menu.classList.toggle("open", !isOpen);
      menu.closest("td")?.classList.toggle("table-actions-cell--open", !isOpen);
      trigger.setAttribute("aria-expanded", !isOpen ? "true" : "false");
    });
  });
}

function mountRowActionMenu(cell, ariaLabel = "Действия") {
  if (!cell) return null;
  cell.classList.add("table-actions-cell");
  cell.innerHTML = `
    <div class="row-action-menu">
      <button class="row-action-menu__trigger" type="button" aria-label="${safeText(ariaLabel)}" aria-haspopup="menu">
        <span></span><span></span><span></span>
      </button>
      <div class="row-action-menu__panel" role="menu"></div>
    </div>
  `;
  initRowActionMenus(cell);
  return cell.querySelector(".row-action-menu__panel");
}

function createRowActionButton(label, className, onClick) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `row-action-menu__item ${className || ""}`.trim();
  button.setAttribute("role", "menuitem");
  button.innerHTML = `${tablerIcon(inferActionIcon(label, className), "row-action-menu__icon")}<span>${safeText(label)}</span>`;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    closeAllRowActionMenus();
    onClick(event, button);
  });
  return button;
}

function closeRowContextMenu() {
  document.querySelector(".row-context-layer")?.remove();
  document.querySelectorAll("tr.row-context-active").forEach((row) => row.classList.remove("row-context-active"));
  document.body.classList.remove("row-context-open");
}

function createRowContextButton(label, className, onClick, keepOpen = false) {
  const button = document.createElement("button");
  button.type = "button";
  button.className = `row-action-menu__item ${className || ""}`.trim();
  button.setAttribute("role", "menuitem");
  button.innerHTML = `${tablerIcon(inferActionIcon(label, className), "row-action-menu__icon")}<span>${safeText(label)}</span>`;
  button.addEventListener("click", (event) => {
    event.stopPropagation();
    if (!keepOpen) closeRowContextMenu();
    onClick(event, button);
  });
  return button;
}

function showRowContextMenu(anchor, items = [], options = {}) {
  if (!anchor) return null;
  closeRowContextMenu();
  closeAllRowActionMenus();

  const layer = document.createElement("div");
  layer.className = "row-context-layer";

  const menu = document.createElement("div");
  menu.className = `row-context-menu ${options.className || ""}`.trim();
  menu.setAttribute("role", "menu");
  menu.addEventListener("click", (event) => event.stopPropagation());

  if (options.title) {
    const title = document.createElement("div");
    title.className = "row-context-menu__title";
    title.innerHTML = `
      <div class="row-context-menu__title-main">
        ${tablerIcon(options.icon || inferContextIcon(options.title), "row-context-menu__title-icon")}<span>${safeText(options.title)}</span>
      </div>
      <button class="row-context-menu__close" type="button" aria-label="Закрыть окно">&times;</button>
    `;
    title.querySelector(".row-context-menu__close")?.addEventListener("click", closeRowContextMenu);
    menu.appendChild(title);
  }

  if (Array.isArray(options.meta) && options.meta.length) {
    const meta = document.createElement("div");
    meta.className = "row-context-menu__meta";
    options.meta.forEach((item) => {
      const cell = document.createElement("div");
      const label = document.createElement("span");
      const value = document.createElement("b");
      label.textContent = item.label;
      if (item.html) {
        value.innerHTML = item.html;
      } else {
        value.textContent = item.value ?? "—";
      }
      cell.append(label, value);
      meta.appendChild(cell);
    });
    menu.appendChild(meta);
  }

  const body = document.createElement("div");
  body.className = "row-context-menu__body";
  if (typeof options.render === "function") {
    options.render(body, closeRowContextMenu);
  } else {
    items.forEach((item) => {
      body.appendChild(createRowContextButton(item.label, item.className, item.onClick, Boolean(item.keepOpen)));
    });
  }
  menu.appendChild(body);

  layer.appendChild(menu);
  document.body.appendChild(layer);
  anchor.classList.add("row-context-active");
  document.body.classList.add("row-context-open");

  requestAnimationFrame(() => layer.classList.add("open"));
  return menu;
}

document.addEventListener("click", (event) => {
  if (!event.target.closest(".row-action-menu")) closeAllRowActionMenus();
  if (event.target.closest(".row-context-layer") && !event.target.closest(".row-context-menu")) closeRowContextMenu();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "Escape") {
    closeAllRowActionMenus();
    closeRowContextMenu();
  }
});
