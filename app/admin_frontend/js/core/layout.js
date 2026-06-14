function ensureAuthOrRedirect() {
  if (!getToken()) {
    window.location.replace("/admin/login");
  }
}

function statusBadge(status) {
  const s = String(status || "").toLowerCase();
  const dict = {
    active: "Активна",
    expired: "Истекла",
    canceled: "Отменена",
    past_due: "Просрочена",
    paid: "Оплачено",
    unpaid: "Не оплачено",
    yes: "Да",
    no: "Нет",
    ok: "Ок",
    ban: "Забанен",
    offline: "Оффлайн",
    pending: "На проверке",
    approved: "Подтверждена",
    rejected: "Отклонена",
    disabled: "Отключена",
  };

  const label = dict[s] || String(status || "—");

  if (["active", "yes", "paid", "ok", "approved"].includes(s)) return `<span class="badge ok">${label}</span>`;
  if (["expired", "canceled", "unpaid", "ban", "offline", "rejected"].includes(s)) return `<span class="badge danger">${label}</span>`;
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
});

const ADMIN_MENU = [
  { key: "dashboard", href: "/admin/dashboard", label: "Обзор", icon: "overview" },
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

function menuIcon(kind) {
  const map = {
    overview: "<path d='M4.5 6.5h6v6h-6z'/><path d='M13.5 6.5h6v3h-6z'/><path d='M13.5 12.5h6v6h-6z'/><path d='M4.5 14.5h6v4h-6z'/>",
    users: "<circle cx='12' cy='8.5' r='2.4'/><path d='M6 18c1.1-2.9 3.6-4.6 6-4.6s4.9 1.7 6 4.6'/><path d='M18.5 11.5c1.1 0 2 .8 2 1.8 0 1-.9 1.8-2 1.8'/>",
    subs: "<path d='M5.5 7.5h13v9h-13z'/><path d='M8 5.5v4M16 5.5v4M8 12h8M8 15h5'/>",
    plans: "<path d='M5.5 16.5h13'/><path d='M8 15V9.5M12 15V6.5M16 15v-3.5'/><path d='M6.5 8.5h2M10.5 7h2M14.5 10h2'/>",
    tx: "<path d='M6.5 8.5h11'/><path d='M6.5 8.5l2-2M6.5 8.5l2 2'/><path d='M17.5 15.5h-11'/><path d='M17.5 15.5l-2-2M17.5 15.5l-2 2'/>",
    wd: "<path d='M12 5.5v9'/><path d='M8.5 11.5L12 15l3.5-3.5'/><path d='M6.5 19.5h11'/>",
    ref: "<circle cx='7.5' cy='8.5' r='2'/><circle cx='16.5' cy='8.5' r='2'/><circle cx='12' cy='15.5' r='2.2'/><path d='M9 9.5l2 4M15 9.5l-2 4'/>",
    partner: "<path d='M9 7h6a3 3 0 0 1 0 6H9a3 3 0 0 1 0-6Z'/><path d='M7 12h10a3 3 0 0 1 0 6H7a3 3 0 0 1 0-6Z'/>",
    promo: "<path d='M7 8.5h10a2 2 0 0 1 2 2v3a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2Z'/><path d='M12 8.5v7'/><path d='M9.1 11.4h.01M14.9 12.6h.01'/>",
    mail: "<rect x='4.5' y='6.5' width='15' height='11' rx='2'/><path d='M5.5 8l6.5 4.8L18.5 8'/>",
    logs: "<path d='M7 5.5h8l3 3V18a1.5 1.5 0 0 1-1.5 1.5h-9A1.5 1.5 0 0 1 6 18V7a1.5 1.5 0 0 1 1.5-1.5Z'/><path d='M15 5.5V9h3'/><path d='M9 12h6M9 15h6'/>",
  };
  const icon = map[kind] || map.overview;
  return `<svg viewBox="0 0 24 24" aria-hidden="true">${icon}</svg>`;
}

function renderMenu(activeKey) {
  return ADMIN_MENU.map((item) => `
    <a href="${item.href}" data-menu-key="${item.key}" class="${activeKey === item.key ? "active" : ""}">
      <span class="menu-ico">${menuIcon(item.icon)}</span>
      <span class="menu-label">${item.label}</span>
    </a>
  `).join("");
}

function renderQuickNav() {
  return `
    <option value="">Быстрый переход</option>
    ${ADMIN_MENU.filter((m) => m.key !== "dashboard").map((m) => `<option value="${m.href}">${m.label}</option>`).join("")}
  `;
}

function renderShell({ activeKey, title, subtitle = "", contentHtml = "" }) {
  document.body.innerHTML = `
    <div class="app-bg"></div>
    <button id="mobile_nav_overlay" class="mobile-nav-overlay" type="button" aria-label="Закрыть меню"></button>

    <div class="app">
      <aside class="sidebar">
        <div class="sidebar-head">
          <img class="logo-image" src="/miniapp/assets/lunet-logo-sign.png?v=1" alt="Lunet" />
          <div class="sidebar-subtitle">Панель управления</div>
        </div>

        <nav class="menu">${renderMenu(activeKey)}</nav>

        <div class="sidebar-footer">
          <button id="logout" class="btn-danger">Выход</button>
        </div>
      </aside>

      <main class="main">
        <header class="topbar">
          <div>
            <div class="crumbs">Главная / Панель Lunet</div>
            <div class="page-title">${title}</div>
            <div class="page-sub">${subtitle}</div>
          </div>
          <div class="topbar-right">
            <button id="mobile_nav_toggle" class="mobile-nav-toggle" type="button" aria-label="Открыть меню">
              <span></span><span></span><span></span>
            </button>
            <select id="quick_nav" class="top-select">${renderQuickNav()}</select>
          </div>
        </header>

        <section id="content">${contentHtml}</section>
      </main>
    </div>
  `;

  q("logout").addEventListener("click", () => {
    clearToken();
    window.location.replace("/admin/login");
  });

  q("quick_nav").addEventListener("change", (e) => {
    const val = e.target.value;
    if (val) window.location.href = val;
  });

  const openMobileNav = () => document.body.classList.add("mobile-nav-open");
  const closeMobileNav = () => document.body.classList.remove("mobile-nav-open");

  const navToggle = q("mobile_nav_toggle");
  const navOverlay = q("mobile_nav_overlay");
  if (navToggle) {
    navToggle.addEventListener("click", () => {
      if (document.body.classList.contains("mobile-nav-open")) closeMobileNav();
      else openMobileNav();
    });
  }
  if (navOverlay) navOverlay.addEventListener("click", closeMobileNav);
  window.addEventListener("resize", () => {
    if (window.innerWidth > 980) closeMobileNav();
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
}

async function renderSessionInfo() {
  return;
}

function renderPager(meta, prevBtn, nextBtn, label) {
  label.textContent = `Страница ${meta.page}/${meta.pages}, всего ${meta.total}`;
  prevBtn.disabled = meta.page <= 1;
  nextBtn.disabled = meta.page >= meta.pages;
}








