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
    <button id="mobile_nav_overlay" class="mobile-nav-overlay" type="button" aria-label="Закрыть меню"></button>

    <div class="app">
      <aside class="sidebar">
        <div class="sidebar-head">
          <div class="sidebar-kicker">Internal Tool</div>
          <div class="sidebar-title">Админ-панель</div>
        </div>

        <nav class="menu">${renderMenu(activeKey)}</nav>

        <div class="sidebar-footer">
          <button id="logout" class="btn-logout">Выход</button>
        </div>
      </aside>

      <main class="main">
        <header class="topbar">
          <div class="topbar-left">
            <button id="mobile_nav_toggle" class="mobile-nav-toggle" type="button" aria-label="Открыть меню">
              <span></span><span></span><span></span>
            </button>
            <div class="topbar-title">Админ-панель</div>
          </div>
        </header>

        <section class="page-shell">
          <div class="page-header-card">
            <div>
              <div class="crumbs">Главная / ${title}</div>
              <div class="page-title">${title}</div>
              <div class="page-sub">${subtitle}</div>
            </div>
            <select id="quick_nav" class="top-select">${renderQuickNav()}</select>
          </div>

          <section id="content">${contentHtml}</section>

          <footer class="page-footer">Админ-панель · Все права защищены</footer>
        </section>
      </main>
    </div>
  `;

  q("logout").addEventListener("click", async () => {
    try {
      await fetch(`${API_BASE}/api/admin/auth/logout`, {
        method: "POST",
        credentials: "include",
      });
    } catch {}
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
  label.textContent = `Страница ${meta.page} из ${meta.pages}`;
  prevBtn.disabled = meta.page <= 1;
  nextBtn.disabled = meta.page >= meta.pages;
}
