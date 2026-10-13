import RefreshButton from "./RefreshButton.jsx";
import { NotFound } from "../../shared/NotFound.jsx";
import { LunetLoader, LunetSkeleton, useDialogFocus, ModalFrame as SharedModalFrame } from "../../shared/controls.jsx";
import { Notice, CabinetToast } from "../../shared/account/components.jsx";
import { LunetSelect } from "../../shared/Select.jsx";
import lunetLogo from "../../static/assets/lunet-logo.png";
import profileAvatar from "../../static/assets/profile.png";
import { SessionGate } from "../../shared/SessionGate.jsx";
import ServersPage from "./ServersPage.jsx";
import { Children, cloneElement, lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { fieldLabels, translateValue, translateError } from "./translations.js";
import { createRoot } from "react-dom/client";
import { Activity, BookOpen, ChevronDown, ChevronLeft, ChevronRight, CircleDollarSign, FileText, GripVertical, LayoutDashboard, LogOut, Menu, Percent, Megaphone, RefreshCw, Search, Server, Shield, Ticket, UserCog, Users, Wallet, X, ArrowUp, ArrowDown } from "lucide-react";
const ActivityChart = lazy(() => import("./ActivityChart.jsx").then(module => ({ default: module.ActivityChart })));
import "./base.css";
import "../../shared/controls.css";
import "./components.css";
import "./interactions.css";
import "../../shared/brand.css";
import "./theme.css";

document.documentElement.classList.remove("dark");
localStorage.removeItem("admin-theme");

if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/admin/sw.js", { scope: "/admin/" }).catch(() => {});
  });
}

const API_BASE = window.__ADMIN_API_BASE_URL || "";
function ModalFrame({ children, ...props }) {
  const parts = Children.toArray(children.props.children);
  const head = parts.find(part => part.props?.className === "dialog-head");
  const last = parts.at(-1);
  const footer = last?.props?.className === "dialog-actions" ? last : null;
  const content = parts.filter(part => part !== head && part !== footer);
  let body = <div className="dialog-body">{content}</div>;
  if (content.length === 1 && content[0].type === "form") {
    const form = content[0];
    const fields = Children.toArray(form.props.children);
    const actions = fields.at(-1)?.props?.className === "dialog-actions" ? fields.pop() : null;
    body = cloneElement(form, { className: `${form.props.className || ""} dialog-form-shell` }, <div className="dialog-body">{fields}</div>, actions);
  }
  return <SharedModalFrame {...props}>{cloneElement(children, {}, head, body, footer)}</SharedModalFrame>;
}
let adminCSRF = "";
let requestAdminReauthentication = async () => false;
const api = async (path, options = {}, retried = false) => {
  const method = (options.method || "GET").toUpperCase();
  const publicAuth = ["/auth/login", "/auth/verify-2fa"].includes(path);
  if (!publicAuth && !["GET", "HEAD", "OPTIONS"].includes(method) && !adminCSRF) {
    const me = await api("/auth/me"); adminCSRF = me.csrf_token || "";
  }
  const r = await fetch(`${API_BASE}/api/admin${path}`, {
    credentials: "include", ...options,
    headers: {...options.headers, ...(!publicAuth && adminCSRF ? {"X-Admin-CSRF": adminCSRF} : {})},
  });
  const data = await r.json().catch(() => ({}));
  if (r.status === 403 && data.detail?.code === "admin_reauthentication_required" && !retried) {
    if (await requestAdminReauthentication()) return api(path, options, true);
    throw new Error("Действие отменено");
  }
  if (r.status === 401 && !publicAuth && path !== "/auth/reauthenticate") {
    location.href = "/admin/login";
    throw Object.assign(new Error("Необходима авторизация"), { status:401 });
  }
  if (!r.ok) throw new Error(translateError(data.detail, r.status));
  if (data.csrf_token) adminCSRF = data.csrf_token;
  return data;
};
const downloadAdminFile = async (path, filename, retried = false) => {
  const response = await fetch(`${API_BASE}/api/admin${path}`, { credentials: "include" });
  if (response.status === 401) {
    location.href = "/admin/login";
    throw new Error("Необходима авторизация");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    if(response.status===403 && data.detail?.code==="admin_reauthentication_required" && !retried && await requestAdminReauthentication()) return downloadAdminFile(path,filename,true);
    throw new Error(translateError(data.detail, response.status));
  }
  const blob = await response.blob();
  const href = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = href;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(href);
};
const nav = [
  {
    group: "Обзор",
    items: [{ key: "dashboard", label: "Дашборд", icon: LayoutDashboard }],
  },
  {
    group: "Управление",
    items: [
      { key: "users", label: "Пользователи", icon: Users },
      { key: "subscriptions", label: "Подписки", icon: Ticket },
      { key: "plans", label: "Тарифы", icon: Wallet },
      { key: "transactions", label: "Транзакции", icon: CircleDollarSign },
      { key: "withdrawals", label: "Выводы", icon: Percent },
      { key: "referrals", label: "Рефералы", icon: Activity },
      { key: "promocodes", label: "Промокоды", icon: Ticket },
      { key: "partners", label: "Партнёры", icon: Users },
    ],
  },
  {
    group: "Система",
    items: [
      { key: "maintenance", label: "Обслуживание", icon: Server },
      { key: "servers", label: "Серверы", icon: Server },
      { key: "broadcast", label: "Рассылки", icon: Megaphone },
      { key: "legal", label: "Документы", icon: FileText },
      { key: "admins", label: "Администраторы", icon: UserCog },
      { key: "logs", label: "Логи", icon: BookOpen },
    ],
  },
];
const meta = Object.fromEntries(
  nav.flatMap((g) => g.items).map((x) => [x.key, x]),
);
const resourceConfig = {
  users: ["Пользователи", "/users"],
  subscriptions: ["Подписки", "/subscriptions"],
  plans: ["Тарифы", "/plans"],
  transactions: ["Транзакции", "/transactions"],
  withdrawals: ["Выводы", "/withdrawals"],
  referrals: ["Реферальная система", "/referrals"],
  promocodes: ["Промокоды", "/promocodes"],
  partners: ["Партнёры", "/partners"],
  admins: ["Администраторы", "/admins"],
  logs: ["Логи", "/logs"],
  diagnostics: ["Диагностика", "/diagnostics/errors?limit=80"],
  broadcast: ["Рассылки", "/broadcast/history?limit=20"],
  legal: ["Документы", "/legal"],
  maintenance: ["Обслуживание", "/system/maintenance"],
};

function Button({
  children,
  variant = "default",
  size = "default",
  className = "",
  loading = false,
  ...props
}) {
  return (
    <button
      type={props.type || "button"}
      className={`ui-button ui-button-${variant} ui-button-${size} ${className}`}
      {...props}
      disabled={loading || props.disabled}
      aria-busy={loading || undefined}
    >
      {loading && <LunetLoader />}
      {children}
    </button>
  );
}

function Spinner() {
  return <LunetLoader />;
}

function Card({ children, className = "" }) {
  return <section className={`ui-card ${className}`}>{children}</section>;
}
function Badge({ children, tone = "muted" }) {
  return <span className={`ui-badge ui-badge-${tone}`}>{children}</span>;
}
function Field({ label, ...props }) {
  return (
    <label className="ui-field">
      <span>{label}</span>
      <input {...props} />
    </label>
  );
}
function Dropdown({ value, onChange, options, ariaLabel }) {
  return <LunetSelect value={value} onChange={onChange} options={options} ariaLabel={ariaLabel} showCheck={false}/>;
}
function Icon({ icon: C, size = 16 }) {
  return C ? <C size={size} strokeWidth={1.8} /> : null;
}
function Shell({ page, children, initialAdmin, onNavigate }) {
  const sidebarRef = useRef(null);
  const userMenuRef = useRef(null);
  const [open, setOpen] = useState(false),
    [userMenu, setUserMenu] = useState(false),
    [notice, setNotice] = useState(""),
    [loggingOut, setLoggingOut] = useState(false);
  const admin = initialAdmin;
  const logoutLock = useRef(false);
  useDialogFocus(sidebarRef, open, () => setOpen(false));
  useEffect(() => {
    if (!userMenu) return;
    const outside = event => { if (!userMenuRef.current?.contains(event.target)) setUserMenu(false); };
    const escape = event => { if (event.key === "Escape") setUserMenu(false); };
    document.addEventListener("pointerdown", outside);
    document.addEventListener("keydown", escape);
    return () => { document.removeEventListener("pointerdown", outside); document.removeEventListener("keydown", escape); };
  }, [userMenu]);
  const adminName = admin?.username || admin?.login || admin?.email || "Администратор";
  const isSupport = admin?.role === "support";
  const supportMenuKeys = new Set(["users", "subscriptions", "transactions", "referrals"]);
  const visibleKeys = !admin
    ? supportMenuKeys
    : isSupport
      ? supportMenuKeys
      : null;
  const visibleNav = nav
    .map((group) => ({
      ...group,
      items: group.items.filter(
        (item) => !visibleKeys || visibleKeys.has(item.key),
      ),
    }))
    .filter((group) => group.items.length);
  const logout = async (all = false) => {
    if (logoutLock.current) return;
    logoutLock.current = true;
    setLoggingOut(true);
    setNotice("");
    try {
      await api(all ? "/auth/revoke-all" : "/auth/logout", { method: "POST" });
      location.href = "/admin/login";
    } catch {
      setNotice("Не удалось завершить сеанс. Проверьте подключение и попробуйте снова.");
    } finally {
      logoutLock.current = false;
      setLoggingOut(false);
    }
  };
  return (
    <div className="admin-shell">
      {notice && <CabinetToast message={notice} kind="error" onClose={()=>setNotice("")}/>}
      <aside ref={sidebarRef} role={open?"dialog":undefined} aria-modal={open||undefined} aria-label="Меню администратора" className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-brand">
          <span className="brand-mark logo-mark"><img src={lunetLogo} alt="" width="34" height="34" /></span>
          <b className="sidebar-brand-name">Lunet<span>VPS</span></b>
        </div>
        <nav>
          {visibleNav.map((group) => (
            <div className="nav-group" key={group.group}>
              <div className="nav-label">{group.group}</div>
              {group.items.map((item) => (
                <a
                  aria-current={page === item.key ? "page" : undefined}
                  className={page === item.key ? "active" : ""}
                  href={`/admin/${item.key}`}
                  onClick={event => {
                    if (event.button !== 0 || event.metaKey || event.ctrlKey || event.shiftKey || event.altKey) return;
                    event.preventDefault();
                    setOpen(false);
                    setUserMenu(false);
                    onNavigate(item.key);
                  }}
                  key={item.key}
                >
                  <Icon icon={item.icon} />
                  <span>{item.label}</span>
                </a>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-user">
          <span className="avatar"><img src={profileAvatar} alt="" width="36" height="36"/></span>
          <span className="sidebar-user-info" title={adminName}>
            <b>{adminName}</b>
            <small>Системный доступ</small>
          </span>
          <button type="button" className="icon-button sidebar-logout" onClick={()=>logout()} aria-label="Выйти" title="Выйти" disabled={loggingOut} aria-busy={loggingOut || undefined}>
            {loggingOut ? <LunetLoader/> : <LogOut size={18} />}
          </button>
        </div>
      </aside>
      {open && (
        <button
          className="menu-overlay"
          aria-label="Закрыть меню"
          onClick={() => setOpen(false)}
        />
      )}
      <div className="content">
        <header className="topbar">
          <Button
            variant="ghost"
            size="icon"
            className="mobile-menu"
            onClick={() => setOpen(!open)}
          >
            <Menu size={18} />
          </Button>
          <div>
            <span className="breadcrumb">Раздел / </span>
            <b>{meta[page]?.label || "Дашборд"}</b>
          </div>
          <div className="top-actions">
            <span className="online">
              <i />
              Система онлайн
            </span>
            <div className="user-menu-wrap" ref={userMenuRef}>
              <Button
                variant="ghost"
                className="user-menu-trigger"
                aria-expanded={userMenu}
                onClick={() => setUserMenu(!userMenu)}
              >
                <span className="avatar"><img src={profileAvatar} alt="" width="36" height="36"/></span>
                <span className="user-menu-name" title={adminName}>{adminName}</span>
                <ChevronDown size={14} />
              </Button>
              {userMenu && (
                <div className="user-menu" role="menu">
                  <div className="user-menu-caption">Системный доступ</div>
                  <button role="menuitem" onClick={()=>logout()} disabled={loggingOut}>
                    <LogOut size={15} /> Выйти
                  </button>
                  <button role="menuitem" onClick={()=>logout(true)} disabled={loggingOut}>
                    <Shield size={15} /> Выйти на всех устройствах
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="page lunet-view">
          {page !== "payments" && <div className="page-heading">
            <div>
              <h1>{meta[page]?.label || "Дашборд"}</h1>
              <p className="muted">
                {page === "dashboard"
                  ? "Обзор состояния сервиса и ключевых показателей"
                  : page === "servers" ? "Состояние и управление серверами" : "Управление разделом и данными системы"}
              </p>
            </div>
          </div>}
          {children}
        </main>
      </div>
    </div>
  );
}

function AdminValue({loading,children}) {
  return loading?<span className="admin-value-skeleton" role="status" aria-label="Загрузка значения"><span className="lunet-sr-only">Загрузка значения</span></span>:children;
}

function Dashboard() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [chartFrom, setChartFrom] = useState(""),
    [chartTo, setChartTo] = useState(""),
    [loading, setLoading] = useState(true);
  const requestSequence=useRef(0);
  const load = () => {
    const attempt=++requestSequence.current;
    setLoading(true);setError("");
    const params =
      chartFrom || chartTo
        ? `?chart_from=${chartFrom || chartTo}&chart_to=${chartTo || chartFrom}`
        : "";
    return api(`/stats${params}`)
      .then(value=>{if(attempt===requestSequence.current)setData(value)})
      .catch(e=>{if(attempt===requestSequence.current)setError(e.message)})
      .finally(()=>{if(attempt===requestSequence.current)setLoading(false)});
  };
  useEffect(() => {
    load();
  }, [chartFrom, chartTo]);
  const stats = data?.stats || {};
  const cards = [
    ["Пользователи", stats.total_users, Users],
    ["Активные подписки", stats.active_subscriptions, Ticket],
    ["Оплачено транзакций", stats.paid_transactions, CircleDollarSign],
    [
      "Выручка",
      stats.total_revenue != null ? `${Number(stats.total_revenue).toLocaleString("ru-RU")} ₽` : null,
      Wallet,
    ],
    ["Регистрации за сутки", stats.new_users_today, Users],
    ["Выручка за сутки", stats.today_revenue != null ? `${Number(stats.today_revenue).toLocaleString("ru-RU")} ₽` : null, Wallet],
    ["Истекают за 7 дней", stats.expiring_subscriptions, Ticket],
    ["Неоплаченные операции", stats.unpaid_transactions, CircleDollarSign],
    ["Заблокированы", stats.banned_users, Shield],
    ["Балансы пользователей", stats.total_balance != null ? `${Number(stats.total_balance).toLocaleString("ru-RU")} ₽` : null, Wallet],
  ];
  return (
    <div className="stack">
      <div className="stats-grid">
        {cards
          .map(([label, value, icon]) => (
            <Card className="stat-card" key={label}>
              <div className="stat-icon">
                <Icon icon={icon} size={18} />
              </div>
              <div>
                <span className="muted">{label}</span>
                <strong><AdminValue loading={loading}>{value ?? "Нет данных"}</AdminValue></strong>
              </div>
            </Card>
          ))}
      </div>
      <div className="dashboard-grid">
        <Card>
          <div className="chart-controls">
            <label>
              С{" "}
              <input
                type="date"
                value={chartFrom}
                onChange={(e) => setChartFrom(e.target.value)}
              />
            </label>
            <label>
              По{" "}
              <input
                type="date"
                value={chartTo}
                onChange={(e) => setChartTo(e.target.value)}
              />
            </label>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => {
                setChartFrom("");
                setChartTo("");
              }}
            >
              Сбросить
            </Button>
          </div>
          <CardHeader
            title="Сводка"
            action={
              <RefreshButton onClick={load} loading={loading}/>
            }
          />
          {error ? (
            <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>
          ) : !loading && data ? (
            <div className="chart-summary">
              <div>
                <strong>{Number(stats.month_revenue ?? 0).toLocaleString("ru-RU")} ₽</strong>
                <span className="muted">Выручка за текущий месяц</span>
              </div>
              <AdminChart stats={stats} />
            </div>
          ) : (
            <Empty text="Загрузка данных…" />
          )}
        </Card>
        <Card>
          <CardHeader title="Подписки и платежи" />
          <div className="health-list">
            <div className="health-row"><span>Доля пользователей с подпиской</span><b><AdminValue loading={loading}>{data && stats.subscribed_users != null ? `${stats.total_users ? Math.round(stats.subscribed_users / stats.total_users * 100) : 0}%` : "Нет данных"}</AdminValue></b></div>
            <div className="health-row"><span>Средняя оплаченная операция</span><b><AdminValue loading={loading}>{data ? `${stats.paid_transactions ? Math.round(stats.total_revenue / stats.paid_transactions).toLocaleString("ru-RU") : 0} ₽` : "Нет данных"}</AdminValue></b></div>
            <div className="health-row"><span>Выручка за месяц</span><b><AdminValue loading={loading}>{data ? `${Number(stats.month_revenue || 0).toLocaleString("ru-RU")} ₽` : "Нет данных"}</AdminValue></b></div>
          </div>
        </Card>
      </div>
    </div>
  );
}
function CardHeader({ title, action }) {
  return (
    <div className="card-header">
      <div>
        <h2>{title}</h2>
      </div>
      {action}
    </div>
  );
}
function Empty({ text = "Нет данных" }) {
  if (/^Загруз/.test(text)) return <LunetSkeleton label={text} />;
  return (
    <div className="empty-state">
      <Search size={22} />
      <span>{text}</span>
    </div>
  );
}
const FIELD_LABELS = {
  id: "ID",
  tg_id: "Telegram ID",
  username: "Имя пользователя",
  email: "Почта",
  balance: "Баланс",
  banned: "Заблокирован",
  traffic_limit_bytes: "Лимит трафика",
  subscription_url: "Ссылка подписки",
  remnawave_user_id: "Remnawave ID",
  remnawave_user_uuid: "Remnawave UUID",
  created_at: "Создан",
  updated_at: "Обновлён",
  subscription_active: "Подписка активна",
  subscription_end: "Подписка до",
  user_id: "Пользователь",
  plan_id: "Тариф",
  status: "Статус",
  auto_renew: "Автопродление",
  current_period_start: "Период начинается",
  current_period_end: "Период заканчивается",
  next_renewal_at: "Следующее продление",
  gb_left: "Трафик осталось",
  device_limit: "Лимит устройств",
  active_now: "Активна сейчас",
  transaction_id: "Номер операции",
  payment_system: "Платёжная система",
  paid: "Оплачено",
  paid_at: "Оплачено",
  amount: "Сумма",
  code: "Промокод",
  usages_left: "Осталось активаций",
  used_count: "Использовано раз",
  is_activated: "Активирован",
  activated_at: "Дата активации",
  name: "Название",
  new_users: "Регистрации",
  attributed_users: "Регистрации",
  paid_users: "Пользователи с оплатой",
  paid_topups: "Оплаченные пополнения",
  paid_amount: "Сумма пополнений",
  filename: "Файл",
  size_bytes: "Размер файла",
  updated_at: "Обновлён",
};
function friendlyValue(key, value) {
  if (value === null || value === undefined || value === "") return "—";
  if (typeof value === "boolean") return value ? "Да" : "Нет";
  const translated = translateValue(key, value);
  if (translated !== null) return translated;
  if (["current_period_start", "current_period_end", "next_renewal_at", "created_at", "updated_at"].includes(key)) { const d = new Date(value); if (!Number.isNaN(d.getTime())) return d.toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" }); }
  if (key === "gb_left") return `${Number(value).toLocaleString("ru-RU")} ГБ`;
  if (key === "traffic_limit_bytes")
    return `${(Number(value) / 1024 ** 3).toFixed(2)} ГБ`;
  if (key.endsWith("_at") || key.endsWith("_end")) {
    const d = new Date(value);
    if (!Number.isNaN(d.getTime())) return d.toLocaleString("ru-RU");
  }
  if (key === "subscription_url" && String(value).startsWith("http"))
    return (
      <a href={value} target="_blank" rel="noreferrer">
        Открыть ссылку
      </a>
    );
  return String(value);
}
function friendlyLabel(key) {
  return (
    fieldLabels[key] || FIELD_LABELS[key] ||
    key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())
  );
}
function Dialog({ title, row, onClose, isUser, onAction, page, onResourceAction }) {
  const [success, setSuccess] = useState("");
  const [amount, setAmount] = useState("100"),
    [gb, setGb] = useState("1"),
    [days, setDays] = useState("30"),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [busyAction, setBusyAction] = useState(""),
    [error, setError] = useState("");
  if (!row) return null;
  const run = async (action) => {
    setSuccess("");
    if (action === "ban" && !reason.trim()) {
      setError("Укажите причину блокировки");
      return;
    }
    const risky = [
      "ban",
      "sub_balance",
      "sub_traffic",
      "reduce_subscription",
      "confirm",
      "approve",
      "reject",
      "delete",
    ].includes(action);
    if (
      risky &&
      !window.confirm(
        action === "ban"
          ? "Заблокировать пользователя?"
          : action === "delete"
            ? "Удалить промокод? Это действие нельзя отменить."
            : action === "reject"
              ? "Отклонить заявку на вывод?"
              : "Подтвердить операцию?",
      )
    )
      return;
    if (busy) return;
    setBusy(true);
    setBusyAction(action);
    setError("");
    try {
      if (isUser) await onAction(action, { amount: Number(amount), gb: Number(gb), duration_hours: Number(days) * 24, ...(action === "ban" ? { reason: reason.trim() } : {}) });
      else await onResourceAction(action);
      setSuccess("Операция выполнена");
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      setBusyAction("");
    }
  };
  return (
    <ModalFrame onClose={onClose} busy={busy}>
      <section className="dialog" role="dialog" aria-modal="true">
        {success && <Notice kind="success" role="status" onClose={()=>setSuccess("")}>{success}</Notice>}
        <div className="dialog-head">
          <div>
            <div className="eyebrow">Детальная информация</div>
            <h2>{title}</h2>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose} data-dialog-close="true" aria-label="Закрыть">
            <X size={17} />
          </Button>
        </div>
        <div className="dialog-grid">
          {Object.entries(row).map(
            ([key, value]) =>
              typeof value !== "object" && (
                <div className="detail-item" key={key}>
                  <span>{friendlyLabel(key)}</span>
                  <b>{friendlyValue(key, value)}</b>
                </div>
              ),
          )}
        </div>
        {isUser && (
          <div className="user-actions">
            <div className="action-section">
              <h3>Баланс</h3>
              <p className="muted">Укажите сумму в рублях.</p>
              <div className="action-row">
                <input
                  aria-label="Сумма в рублях"
                  type="number"
                  min="1"
                  value={amount}
                  onChange={(e) => setAmount(e.target.value)}
                />
                <Button disabled={busy} onClick={() => run("add_balance")}>
                  {busyAction === "add_balance" && <Spinner />}<Wallet size={14} /> Начислить
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => run("sub_balance")}
                >
                  {busyAction === "sub_balance" && <Spinner />}Списать
                </Button>
              </div>
            </div>
            <div className="action-section">
              <h3>Подписка и трафик</h3>
              <div className="action-fields">
                <label>
                  Дни подписки
                  <input
                    aria-label="Количество дней"
                    type="number"
                    min="1"
                    value={days}
                    onChange={(e) => setDays(e.target.value)}
                  />
                </label>
                <label>
                  Гигабайты
                  <input
                    aria-label="Количество гигабайт"
                    type="number"
                    min=".1"
                    step=".1"
                    value={gb}
                    onChange={(e) => setGb(e.target.value)}
                  />
                </label>
              </div>
              <div className="action-row">
                <Button
                  disabled={busy}
                  onClick={() => run("extend_subscription")}
                >
                  {busyAction === "extend_subscription" && <Spinner />}Продлить
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => run("reduce_subscription")}
                >
                  {busyAction === "reduce_subscription" && <Spinner />}Уменьшить срок
                </Button>
                <Button disabled={busy} onClick={() => run("add_traffic")}>
                  {busyAction === "add_traffic" && <Spinner />}Начислить ГБ
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => run("sub_traffic")}
                >
                  {busyAction === "sub_traffic" && <Spinner />}Списать ГБ
                </Button>
              </div>
            </div>
            <div className="action-section action-section-danger">
              {!row.banned && <label className="ui-field ban-reason-field"><span>Причина блокировки *</span><textarea rows="3" required value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Например: нарушение правил сервиса" /></label>}
              <p className="muted">
                Блокировка отключает VPN-доступ и отправляет уведомление в
                Telegram.
              </p>
              <div className="action-row">
                <Button
                  variant="danger"
                  disabled={busy}
                  onClick={() => run(row.banned ? "unban" : "ban")}
                >
                  {busyAction === (row.banned ? "unban" : "ban") && <Spinner />}{row.banned ? "Разблокировать" : "Заблокировать"}
                </Button>
              </div>
            </div>
            {error && <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>}
          </div>
        )}
        {!isUser && page === "transactions" && <div className="user-actions"><div className="action-section"><h3>Оплата</h3><p className="muted">Подтвердить оплату и начислить сумму на баланс пользователя.</p><Button disabled={busy || row.paid} onClick={() => run("confirm")}>{busyAction === "confirm" && <Spinner />}{row.paid ? "Уже подтверждено" : "Подтвердить транзакцию"}</Button></div></div>}
        {!isUser && page === "withdrawals" && <div className="user-actions"><div className="action-section"><h3>Решение по заявке</h3><p className="muted">После подтверждения деньги будут перечислены пользователю.</p><div className="action-row"><Button disabled={busy || row.status !== "pending"} onClick={() => run("approve")}>{busyAction === "approve" && <Spinner />}Подтвердить вывод</Button><Button variant="danger" disabled={busy || row.status !== "pending"} onClick={() => run("reject")}>{busyAction === "reject" && <Spinner />}Отклонить вывод</Button></div></div></div>}
        {!isUser && page === "promocodes" && <div className="user-actions"><div className="action-section action-section-danger"><h3>Управление промокодом</h3><p className="muted">Удаление промокода нельзя отменить.</p><Button variant="danger" disabled={busy} onClick={() => run("delete")}>Удалить промокод</Button></div></div>}
        {!isUser && page === "partners" && row.details && <div className="user-actions"><div className="action-section"><h3>Активность партнёрской ссылки</h3><div className="partner-summary"><span>Регистрации: <b>{row.details.summary?.attributed_users ?? 0}</b></span><span>Пользователи с оплатой: <b>{row.details.summary?.paid_users ?? 0}</b></span><span>Оплаченные пополнения: <b>{row.details.summary?.paid_topups ?? 0}</b></span><span>Сумма: <b>{row.details.summary?.paid_amount ?? 0} ?</b></span></div><div className="partner-activity-list">{(row.details.users || []).slice(0, 8).map((user) => <div key={user.user_id}><span>{user.username || `Пользователь #${user.user_id}`}</span><span>{user.paid_amount ? `${user.paid_amount} ?` : "Без оплат"}</span></div>)}</div></div></div>}
        {!isUser && page === "logs" && <div className="user-actions"><div className="action-section"><h3>Файл журнала</h3><Button disabled={busy} onClick={() => run("download")}>{busyAction === "download" && <Spinner />}Скачать лог</Button></div></div>}
        <div className="dialog-actions">
          <Button variant="outline" onClick={onClose} data-dialog-close="true" aria-label="Закрыть">
            Закрыть
          </Button>
        </div>
      </section>
    </ModalFrame>
  );
}
function CreateDialog({ page, onClose, onCreated }) {
  const [form, setForm] = useState({}),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const set = (key, value) =>
    setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (page === "broadcast") {
        const body = new FormData();
        body.append("text", form.text || "");
        body.append("parse_mode", form.parse_mode || "HTML");
        body.append("include_banned", String(Boolean(form.include_banned)));
        if (form.image) body.append("image", form.image);
        await api("/broadcast/upload", {
          method: "POST",
          credentials: "include",
          body,
        });
      } else {
        const payload =
          page === "subscriptions"
            ? {
                user_id: Number(form.user_id),
                plan_id: Number(form.plan_id),
                auto_renew: Boolean(form.auto_renew),
              }
            : page === "plans"
              ? {
                  name: form.name,
                  price: Number(form.price),
                  period_days: Number(form.period_days || 30),
                  gb_limit: Number(form.gb_limit || 0),
                  device_limit: Number(form.device_limit || 0),
                  purchase_limit: Number(form.purchase_limit || 0),
                  is_hidden: Boolean(form.is_hidden),
                  is_trial: Boolean(form.is_trial),
                }
              : page === "promocodes"
                ? {
                    code: form.code,
                    amount: Number(form.amount),
                    usages: Number(form.usages || 1),
                  }
                : page === "partners"
                  ? { name: form.name, code: form.code || null }
                  : {
                      username: form.username || form.user_id,
                      email: form.email,
                      password: form.password,
                      role: form.role || "support",
                      is_active: true,
                    };
        await api(`/${page}`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
      }
      await onCreated();
      onClose();
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  const input = (key, label, type = "text", required = true) => (
    <label className="ui-field" key={page === "admins" && key === "user_id" ? "username" : page === "admins" && key === "login" ? "email" : key}>
      <span>{page === "admins" && key === "user_id" ? "Имя пользователя" : page === "admins" && key === "login" ? "Почта" : label}</span>
      <input
        required={required}
        type={page === "admins" && key === "user_id" ? "text" : page === "admins" && key === "login" ? "email" : type}
        value={form[page === "admins" && key === "user_id" ? "username" : page === "admins" && key === "login" ? "email" : key] ?? ""}
        onChange={(e) => set(page === "admins" && key === "user_id" ? "username" : page === "admins" && key === "login" ? "email" : key, e.target.value)}
      />
    </label>
  );
  return (
    <ModalFrame onClose={onClose} busy={busy}>
      <section className={`dialog create-dialog ${page === "broadcast" ? "broadcast-dialog" : ""}`} role="dialog" aria-modal="true">
        <div className="dialog-head">
          <div>
            <div className="eyebrow">Новое действие</div>
            <h2>
              {page === "broadcast"
                ? "Создать рассылку"
                : `Добавить: ${meta[page]?.label || "запись"}`}
            </h2>
            {page === "broadcast" && <p className="muted">Сообщение будет отправлено пользователям после запуска.</p>}
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose} data-dialog-close="true" aria-label="Закрыть"
            aria-label="Закрыть"
          >
            <X size={17} />
          </Button>
        </div>
        <form onSubmit={submit} className="create-form">
          {page === "subscriptions" && (
            <>
              {input("user_id", "ID пользователя", "number")}
              {input("plan_id", "ID тарифа", "number")}
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={Boolean(form.auto_renew)}
                  onChange={(e) => set("auto_renew", e.target.checked)}
                />{" "}
                Автопродление
              </label>
            </>
          )}
          {page === "plans" && (
            <>
              {input("name", "Название тарифа")}
              {input("price", "Цена, ₽", "number")}
              {input("period_days", "Период, дней", "number")}
              {input("gb_limit", "Лимит трафика, ГБ", "number")}
              {input("device_limit", "Лимит устройств", "number")}
              {input(
                "purchase_limit",
                "Лимит покупок, 0 — без лимита",
                "number",
              )}
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={Boolean(form.is_hidden)}
                  onChange={(e) => set("is_hidden", e.target.checked)}
                />{" "}
                Скрыть тариф
              </label>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={Boolean(form.is_trial)}
                  onChange={(e) => set("is_trial", e.target.checked)}
                />{" "}
                Пробный тариф
              </label>
            </>
          )}
          {page === "promocodes" && (
            <>
              {input("code", "Код промокода")}
              {input("amount", "Сумма, ₽", "number")}
              {input("usages", "Количество использований", "number")}
            </>
          )}
          {page === "partners" && (
            <>
              {input("name", "Название партнёра")}
              {input("code", "Код ссылки", "text", false)}
            </>
          )}
          {page === "admins" && (
            <>
              {input("user_id", "ID пользователя", "number")}
              {input("login", "Логин")}
              {input("password", "Пароль", "password")}
              <label className="ui-field">
                <span>Роль</span>
                <Dropdown value={form.role || "support"} onChange={(value) => set("role", value)} options={[{ value: "support", label: "Поддержка" }, { value: "superadmin", label: "Суперадминистратор" }]} ariaLabel="Роль администратора" />
              </label>
            </>
          )}
          {page === "broadcast" && (
            <>
              <label className="ui-field">
                <span>Текст сообщения</span>
                <textarea
                  required
                  rows="7"
                  value={form.text || ""}
                  onChange={(e) => set("text", e.target.value)}
                  placeholder="Текст сообщения для пользователей"
                />
              </label>
              <label className="ui-field">
                <span>Формат</span>
                <Dropdown value={form.parse_mode || "HTML"} onChange={(value) => set("parse_mode", value)} options={[{ value: "HTML", label: "HTML" }, { value: "MarkdownV2", label: "MarkdownV2" }]} ariaLabel="Формат сообщения" />
              </label>
              <label className="ui-field">
                <span>Изображение, необязательно</span>
                <input
                  type="file"
                  accept="image/*"
                  onChange={(e) => set("image", e.target.files?.[0])}
                />
              </label>
              <label className="check-field">
                <input
                  type="checkbox"
                  checked={Boolean(form.include_banned)}
                  onChange={(e) => set("include_banned", e.target.checked)}
                />{" "}
                Включить заблокированных
              </label>
            </>
          )}
          {error && <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>}
          <div className="dialog-actions">
            <Button type="button" variant="outline" onClick={onClose} data-dialog-close="true" aria-label="Закрыть">
              Отмена
            </Button>
            <Button type="submit" loading={busy} disabled={busy}>
              {busy
                ? "Сохраняем…"
                : page === "broadcast"
                  ? "Запустить рассылку"
                  : "Создать"}
            </Button>
          </div>
        </form>
      </section>
    </ModalFrame>
  );
}
function SubscriptionDialog({ row, onClose, onUpdated }) {
  const [days, setDays] = useState("30");
  const [devices, setDevices] = useState("1");
  const [busy, setBusy] = useState(false);
  const [busyAction, setBusyAction] = useState("");
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  if (!row) return null;
  const run = async (action) => {
    if (busy) return;
    setBusy(true);
    setBusyAction(action);
    setError("");
    setSuccess("");
    try {
      if (action === "sync") {
        await api(`/subscriptions/${row.id}/sync`, { method: "POST" });
        setSuccess("Подписка успешно синхронизирована с панелью.");
      } else if (action === "add_devices" || action === "remove_devices") {
        const amount = Number(devices);
        if (!Number.isFinite(amount) || amount < 1) throw new Error("Укажите количество устройств больше нуля");
        await api(`/subscriptions/${row.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            device_limit: Math.max(0, Number(row.device_limit || 0) + (action === "add_devices" ? amount : -amount)),
          }),
        });
        setSuccess("Лимит устройств обновлён.");
      } else {
        const amount = Number(days);
        if (!Number.isFinite(amount) || amount < 1) throw new Error("Укажите количество дней больше нуля");
        await api(`/subscriptions/${row.id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ [action === "extend" ? "extend_days" : "reduce_days"]: amount }),
        });
        setSuccess("Срок подписки обновлён.");
      }
      try {
        await onUpdated();
      } catch {
        // Действие уже сохранено; обновление списка можно повторить вручную.
      }
    } catch (e) {
      setError(e.message || "Операция не выполнена");
    } finally {
      setBusy(false);
      setBusyAction("");
    }
  };
  return (
    <ModalFrame onClose={onClose} busy={busy}>
      <section className="dialog" role="dialog" aria-modal="true">
        <div className="dialog-head">
          <div><div className="eyebrow">Управление подпиской</div><h2>Подписка #{row.id}</h2></div>
          <Button variant="ghost" size="icon" onClick={onClose} data-dialog-close="true" aria-label="Закрыть"><X size={17}/></Button>
        </div>
        <div className="dialog-grid">{Object.entries(row).filter(([, value]) => typeof value !== "object").map(([key, value]) => <div className="detail-item" key={key}><span>{friendlyLabel(key)}</span><b>{friendlyValue(key, value)}</b></div>)}</div>
        <div className="user-actions">
          <div className="action-section"><h3>Срок действия</h3><div className="action-row"><input type="number" min="1" value={days} onChange={(e) => setDays(e.target.value)} aria-label="Количество дней"/><Button disabled={busy} onClick={() => run("extend")}>{busyAction === "extend" && <Spinner />}Продлить</Button><Button variant="outline" disabled={busy} onClick={() => run("reduce")}>{busyAction === "reduce" && <Spinner />}Уменьшить срок</Button></div></div>
          <div className="action-section"><h3>Устройства</h3><div className="action-row"><input type="number" min="1" value={devices} onChange={(e) => setDevices(e.target.value)} aria-label="Количество устройств"/><Button disabled={busy} onClick={() => run("add_devices")}>{busyAction === "add_devices" && <Spinner />}Добавить устройства</Button><Button variant="outline" disabled={busy} onClick={() => run("remove_devices")}>{busyAction === "remove_devices" && <Spinner />}Уменьшить устройства</Button></div></div>
          <div className="action-section"><h3>Синхронизация</h3><p className="muted">Отправить текущие срок, трафик, статус и лимит устройств в Remnawave.</p><Button type="button" disabled={busy} onClick={() => run("sync")}>{busyAction === "sync" ? <Spinner /> : <RefreshCw size={14}/>} {busy ? "Синхронизируем…" : "Синхронизировать с панелью"}</Button></div>
          {success && <Notice kind="success" role="status" onClose={()=>setSuccess("")}>{success}</Notice>}
          {error && <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>}
        </div>
        <div className="dialog-actions"><Button variant="outline" onClick={onClose} data-dialog-close="true" aria-label="Закрыть">Закрыть</Button></div>
      </section>
    </ModalFrame>
  );
}
function MaintenancePage() {
  const [maintenance, setMaintenance] = useState(null), [health, setHealth] = useState(null), [loadState, setLoadState] = useState(null), [message, setMessage] = useState("Сервер на технических работах."), [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [error, setError] = useState("");
  const load = async () => {
    setLoading(true); setError("");
    try {
      const [maintenanceData, healthData, serverLoad] = await Promise.all([api("/system/maintenance"), api("/system/health"), api("/system/server-load")]);
      setMaintenance(maintenanceData.maintenance || {}); setHealth(healthData); setLoadState(serverLoad);
    } catch (e) { setError(e.message || "Не удалось загрузить состояние сервера"); } finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);
  useEffect(() => { if (maintenance?.message) setMessage(maintenance.message); }, [maintenance]);
  const toggle = async () => {
    setBusy(true); setError("");
    try {
      const result = await api("/system/maintenance", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ enabled: !maintenance?.enabled, message }) });
      setMaintenance(result.maintenance || {});
    } catch (e) { setError(e.message || "Не удалось изменить режим обслуживания"); } finally { setBusy(false); }
  };
  return <div className="stack">
    {error && <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>}
    {loading ? <Empty text="Загрузка состояния сервера…" /> : <>
      <Card className={`maintenance-control-card ${maintenance?.enabled ? "is-enabled" : ""}`}>
        <div className="card-header"><div><h2>Технические работы</h2><p className="muted">При включении пользователи увидят сообщение о временной недоступности сервиса.</p></div><Badge tone={maintenance?.enabled ? "danger" : "success"}>{maintenance?.enabled ? "Включены" : "Сервис работает"}</Badge></div>
        <label className="ui-field"><span>Сообщение для пользователей</span><textarea value={message} onChange={(e) => setMessage(e.target.value)} rows="3" /></label>
        <div className="maintenance-actions"><Button variant={maintenance?.enabled ? "danger" : "default"} loading={busy} disabled={busy} onClick={toggle}>{busy ? "Сохраняем…" : maintenance?.enabled ? "Завершить техработы" : "Включить техработы"}</Button><RefreshButton disabled={busy} loading={loading} onClick={load}>Обновить данные</RefreshButton></div>
      </Card>
      <div className="maintenance-grid"><Card><CardHeader title="Сервисы"/><div className="health-list">{(health?.items || []).map((item) => <div className="health-row" key={item.key}><span>{item.label}</span><Badge tone={item.status === "ok" ? "success" : item.status === "warn" ? "warn" : "danger"}>{item.status === "ok" ? "Работает" : item.status === "warn" ? "Проверьте" : "Ошибка"}</Badge></div>)}</div></Card><Card><CardHeader title="Нагрузка сервера" action={<span className="muted">{loadState?.hostname || "—"}</span>}/><div className="server-metrics">{(loadState?.metrics || []).map((metric) => <div className="server-metric" key={metric.key}><div><span>{metric.label}</span><b>{metric.value || "—"}</b></div><div className="metric-bar"><i className={`metric-${metric.status || "ok"}`} style={{ width: `${Math.min(100, Math.max(0, Number(metric.percent) || 0))}%` }}/></div></div>)}</div><p className="muted">Аптайм: {loadState?.summary?.uptime || "—"} · Проверено: {friendlyValue("checked_at", loadState?.checked_at)}</p></Card></div>
    </>}
  </div>;
}
function LegalDialog({row,onClose,onUpdated}) {
  const [html,setHtml]=useState(""),[revision,setRevision]=useState(null),[loading,setLoading]=useState(true),[busy,setBusy]=useState(false),[error,setError]=useState(""),[attempt,setAttempt]=useState(0);
  useEffect(()=>{
    let current=true;setLoading(true);setError("");setRevision(null);
    api(`/legal/${row.key}`).then(document=>{if(current){setHtml(document.content??document.html??"");setRevision(document.revision)}}).catch(e=>{if(current)setError(e.message)}).finally(()=>{if(current)setLoading(false)});
    return()=>{current=false};
  },[row.key,attempt]);
  const save=async()=>{
    if(loading||busy||revision===null||!html.trim())return;
    setBusy(true);setError("");
    try{await api(`/legal/${row.key}`,{method:"PUT",headers:{"Content-Type":"application/json"},body:JSON.stringify({html,revision})});await onUpdated();onClose()}
    catch(e){setError(e.message)}finally{setBusy(false)}
  };
  return <ModalFrame onClose={onClose} busy={busy}><section className="dialog" role="dialog" aria-modal="true"><div className="dialog-head"><div><div className="eyebrow">Документ</div><h2>{row.title||row.key}</h2><p className="muted">Изменения публикуются для лендинга, кабинета и мини-приложения. Поддерживаются безопасные HTML-теги форматирования.</p></div><Button variant="ghost" size="icon" data-dialog-close="true" aria-label="Закрыть"><X size={17}/></Button></div>
    {loading?<LunetSkeleton rows={3} label="Загружаем текст документа…"/>:<><label className="ui-field"><span>Текст документа</span><textarea className="legal-editor" rows="18" value={html} disabled={busy||revision===null} onChange={e=>setHtml(e.target.value)}/></label><a href={`https://lunet.pro/terms/${row.key==="terms"?"":row.key+"/"}`} target="_blank" rel="noopener noreferrer">Открыть опубликованный документ</a></>}
    {error&&<Notice kind="error" role="alert"><span>{error}</span><Button variant="outline" disabled={busy} onClick={()=>setAttempt(value=>value+1)}>Загрузить актуальный текст</Button></Notice>}
    <div className="dialog-actions"><Button variant="outline" data-dialog-close="true" disabled={busy}>Отмена</Button><Button loading={busy} disabled={loading||revision===null||!html.trim()} onClick={save}>Сохранить документ</Button></div>
  </section></ModalFrame>;
}
function AdminLoginJournalDialog({ onClose }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => { api("/admins/login-events?limit=10").then((data) => setItems(data.items || [])).catch((e) => setError(e.message)); }, []);
  const date = (value) => value ? new Date(value).toLocaleString("ru-RU") : "—";
  return <ModalFrame onClose={onClose} busy={false}><section className="dialog admin-audit-dialog" role="dialog" aria-modal="true"><div className="dialog-head"><div><div className="eyebrow">Безопасность</div><h2>Журнал входов</h2><p className="muted">Кто и когда входил в панель администратора.</p></div><Button variant="ghost" size="icon" onClick={onClose} data-dialog-close="true" aria-label="Закрыть"><X size={17}/></Button></div>{error && <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>}{!items.length && !error ? <p className="muted">Записей пока нет.</p> : <div className="audit-list">{items.map((item) => <div className="audit-row" key={item.id}><span>{date(item.created_at)}</span><b>{item.username || item.email || "Неизвестный администратор"}</b><span className={item.success ? "audit-success" : "audit-failure"}>{item.success ? "Успешный вход" : "Неуспешная попытка"}</span></div>)}</div>}<div className="dialog-actions"><Button variant="outline" onClick={onClose} data-dialog-close="true" aria-label="Закрыть">Закрыть</Button></div></section></ModalFrame>;
}

function AdminAuditDialog({ admin, onClose, onSaved }) {
  const [form, setForm] = useState({ username: admin.username || "", email: admin.email || "", password: "", role: admin.role || "support" });
  const [audit, setAudit] = useState({ login_events: [], action_events: [] });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [confirmAction, setConfirmAction] = useState("");
  const changeAccess = async () => {
    if (busy) return;
    setBusy(true); setError("");
    try {
      await api(`/admins/${admin.id}`, confirmAction === "delete"
        ? { method: "DELETE" }
        : { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ is_active: !admin.is_active }) });
      await onSaved(); onClose();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  useEffect(() => {
    api(`/admins/${admin.id}/audit`).then(setAudit).catch((e) => setError(e.message));
  }, [admin.id]);
  const save = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      const payload = { username: form.username.trim(), email: form.email.trim(), role: form.role };
      if (form.password.trim()) payload.password = form.password.trim();
      await api(`/admins/${admin.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) });
      await onSaved(); onClose();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const date = (value) => value ? new Date(value).toLocaleString("ru-RU") : "—";
  return <ModalFrame onClose={onClose} busy={busy}>
    <section className="dialog admin-audit-dialog" role="dialog" aria-modal="true">
      <div className="dialog-head"><div><div className="eyebrow">Администратор</div><h2>{admin.username}</h2><p className="muted">Изменение данных и история работы в панели.</p></div><Button variant="ghost" size="icon" onClick={onClose} data-dialog-close="true" aria-label="Закрыть"><X size={17}/></Button></div>
      <form className="create-form" onSubmit={save}>
        <div className="admin-edit-grid">
          <Field label="Имя пользователя" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          <Field label="Электронная почта" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <Field label="Новый пароль" type="password" placeholder="Оставьте пустым, чтобы не менять" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <label className="ui-field"><span>Роль</span><Dropdown value={form.role} onChange={(role) => setForm({ ...form, role })} options={[{ value: "support", label: "Поддержка" }, { value: "superadmin", label: "Суперадминистратор" }]} ariaLabel="Роль администратора" /></label>
        </div>
        {error && <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>}
        <div className="dialog-actions"><Button type="button" variant="outline" onClick={onClose} data-dialog-close="true" aria-label="Закрыть">Отмена</Button><Button type="submit" loading={busy} disabled={busy}>{busy ? "Сохраняем…" : "Сохранить изменения"}</Button></div>
      </form>
      <div className="admin-access-actions">
        <h3>Доступ к панели</h3>
        <p className="muted">{admin.is_active ? "Доступ включён" : "Доступ отключён"}</p>
        {confirmAction ? <div className="access-confirm">
          <p>{confirmAction === "delete" ? "Удалить администратора? История действий сохранится, доступ будет закрыт." : admin.is_active ? "Отключить доступ? Все сеансы этого администратора будут завершены." : "Включить доступ для этого администратора?"}</p>
          <div className="dialog-actions"><Button variant="outline" disabled={busy} onClick={() => setConfirmAction("")}>Отмена</Button><Button variant={confirmAction === "delete" ? "danger" : "default"} loading={busy} onClick={changeAccess}>{confirmAction === "delete" ? "Удалить администратора" : admin.is_active ? "Отключить доступ" : "Включить доступ"}</Button></div>
        </div> : <div className="dialog-actions"><Button variant="outline" disabled={busy} onClick={() => setConfirmAction("toggle")}>{admin.is_active ? "Отключить доступ" : "Включить доступ"}</Button><Button variant="danger" disabled={busy} onClick={() => setConfirmAction("delete")}>Удалить администратора</Button></div>}
      </div>
      <div className="audit-section"><div className="audit-section-head"><h3>Журнал входов</h3><Button variant="outline" size="sm" onClick={() => downloadAdminFile(`/admins/${admin.id}/audit/download`, `admin-${admin.id}-audit.csv`).catch(e=>setError(e.message))}>Скачать CSV</Button></div>
        {!audit.login_events.length ? <p className="muted">Входов пока нет.</p> : <div className="audit-list">{audit.login_events.map((item) => <div className="audit-row" key={`login-${item.id}`}><span>{date(item.created_at)}</span><span>{item.success ? "Успешный вход" : "Неуспешная попытка"}</span><span>{item.ip_address || "IP неизвестен"}</span></div>)}</div>}
      </div>
      <div className="audit-section"><div className="audit-section-head"><h3>Последние 10 действий в панели</h3></div>
        {!audit.action_events.length ? <p className="muted">Действий пока нет.</p> : <div className="audit-list">{audit.action_events.map((item) => <div className="audit-row" key={`action-${item.id}`}><span>{date(item.created_at)}</span><b>{friendlyValue("action", item.action)}</b><span title={item.path}>{item.details || item.path}</span></div>)}</div>}
      </div>
    </section>
  </ModalFrame>;
}

function ResourcePage({ page }) {
  const [data, setData] = useState(null),
    [query, setQuery] = useState(""),
    [tablePage, setTablePage] = useState(1),
    [pageSize, setPageSize] = useState(25),
    [selected, setSelected] = useState(null),
    [selectedUserId, setSelectedUserId] = useState(null),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [createOpen, setCreateOpen] = useState(false),
    [loginJournalOpen, setLoginJournalOpen] = useState(false);
  const selectionRequest = useRef(0);
  const loadRequest = useRef(0);
  const closeSelection = () => { selectionRequest.current += 1; setSelected(null); setSelectedUserId(null); };
  const [sort, setSort] = useState({ key: "", direction: "desc" });
  const [filter, setFilter] = useState("all");
  const sortableFields = {
    users: ["id", "tg_id", "username", "email", "balance", "created_at", "updated_at", "subscription_end"],
    subscriptions: ["id", "user_id", "status", "current_period_end", "created_at"],
    transactions: ["id", "amount", "created_at", "paid_at"],
  }[page] || [];
  const filterConfig = {
    users: { parameter: "banned", label: "Статус пользователя", options: [{value:"all",label:"Все пользователи"},{value:"exclude",label:"Без блокировки"},{value:"only",label:"Заблокированные"}] },
    subscriptions: { parameter: "status", label: "Статус подписки", options: [{value:"all",label:"Все подписки"},{value:"active",label:"Активные"},{value:"past_due",label:"Просроченные"},{value:"expired",label:"Истёкшие"},{value:"canceled",label:"Отменённые"}] },
    transactions: { parameter: "paid", label: "Статус оплаты", options: [{value:"all",label:"Все транзакции"},{value:"paid",label:"Оплаченные"},{value:"unpaid",label:"Неоплаченные"}] },
  }[page];
  const config = resourceConfig[page];
  const serverPaged = ["users", "subscriptions", "transactions", "withdrawals", "referrals"].includes(page);
  const load = () => {
    const requestId = ++loadRequest.current;
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (serverPaged) {
      params.set("page", String(tablePage));
      params.set("page_size", String(pageSize));
      if (query.trim()) params.set("search", query.trim());
      if (sort.key && sortableFields.includes(sort.key)) { params.set("sort_by", sort.key); params.set("sort_dir", sort.direction); }
      if (filterConfig) params.set(filterConfig.parameter, filter);
    }
    const path = `${config[1]}${params.toString() ? `?${params.toString()}` : ""}`;
    return api(path)
      .then(value => { if(requestId === loadRequest.current) setData(value); })
      .catch(e => { if(requestId === loadRequest.current) setError(e.message); })
      .finally(() => { if(requestId === loadRequest.current) setLoading(false); });
  };
  useEffect(() => {
    load();
  }, [page, tablePage, pageSize, query, sort, filter]);
  useEffect(() => {
    setTablePage(1);
  }, [page]);
  useEffect(() => {
    const button = document.querySelector(
      ".toolbar-card .ui-button:last-child",
    );
    if (
      !button ||
      ![
        "subscriptions",
        "plans",
        "promocodes",
        "partners",
        "admins",
        "broadcast",
      ].includes(page)
    )
      return;
    const open = () => setCreateOpen(true);
    button.addEventListener("click", open);
    return () => button.removeEventListener("click", open);
  }, [page, data]);
  const rows = Array.isArray(data)
    ? data
    : data?.items ||
      data?.users ||
      data?.subscriptions ||
      data?.transactions ||
      data?.withdrawals ||
      data?.partners ||
      data?.admins ||
      data?.logs ||
      data?.data ||
      [];
  const filtered = useMemo(
    () =>
      rows.filter(
        (x) =>
          !query ||
          JSON.stringify(x).toLowerCase().includes(query.toLowerCase()),
      ),
    [rows, query],
  );
  const totalRows = serverPaged ? Number(data?.meta?.total || 0) : filtered.length;
  const totalPages = Math.max(1, serverPaged ? Number(data?.meta?.pages || 1) : Math.ceil(filtered.length / pageSize));
  const visibleRows = serverPaged ? filtered : filtered.slice((tablePage - 1) * pageSize, tablePage * pageSize);
  useEffect(() => {
    if (tablePage > totalPages) setTablePage(totalPages);
  }, [tablePage, totalPages]);
  const columns = rows[0]
    ? page === "users"
      ? ["id", "tg_id", "username", "email", "balance", "banned", "subscription_end"].filter((key) => key in rows[0])
      : Object.keys(rows[0])
          .filter((k) => typeof rows[0][k] !== "object")
          .slice(0, 7)
    : [];
  const openRow = async (row) => {
    const requestId = ++selectionRequest.current;
    setSelected(row);
    if (page === "users") setSelectedUserId(Number(row.id));
    if (page === "admins" && row.id) {
      try { const details = await api(`/admins/${row.id}/audit`); if (requestId === selectionRequest.current) setSelected({ ...row, audit: details }); } catch (e) { if (requestId === selectionRequest.current) setError(e.message); }
    } else if ((page === "users" || page === "subscriptions" || page === "partners") && (row.id || row.key)) {
      try {
        const details = page === "users" ? await api(`/users/${row.id}`) : page === "subscriptions" ? await api(`/subscriptions/${row.id}/details`) : page === "partners" ? await api(`/partners/${row.id}/details`) : await api(`/legal/${row.key}`);
        if (requestId === selectionRequest.current) setSelected({ ...(details.user || {}), ...(details.subscription || {}), ...(details.link || {}), ...row, details });
      } catch (e) {
        if (requestId === selectionRequest.current) setError(e.message);
      }
    }
  };
  const onResourceAction = async (action) => {
    if (!selected?.id && !(page === "logs" && selected?.filename)) return;
    if (page === "transactions" && action === "confirm") await api(`/transactions/${selected.id}/confirm`, { method: "POST" });
    if (page === "withdrawals" && ["approve", "reject"].includes(action)) await api(`/withdrawals/${selected.id}/${action}`, { method: "POST" });
    if (page === "promocodes" && action === "delete") { await api(`/promocodes/${selected.id}`, { method: "DELETE" }); setSelected(null); }
    if (page === "logs" && action === "download") { await downloadAdminFile(`/logs/${encodeURIComponent(selected.filename)}/download`, selected.filename); return; }
    await load();
  };
  const onAction = async (action, payload) => {
    const userId = selectedUserId || selected?.id;
    if (!userId) return;
    await api(`/users/${userId}/action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ action, ...payload }),
    });
    await load();
    const details = await api(`/users/${userId}`);
    setSelected({ ...selected, ...(details.user || {}), details });
  };
  return (
    <div className="stack">
      <Card className="toolbar-card">
        <div className="search-box">
          <Search size={15} />
          <input
            aria-label="Поиск по данным" placeholder="Поиск по данным…"
            value={query}
            onChange={(e) => { setQuery(e.target.value); setTablePage(1); }}
          />
        </div>
        {filterConfig && <div className="table-filter"><Dropdown value={filter} onChange={value => { setFilter(value); setTablePage(1); }} options={filterConfig.options} ariaLabel={filterConfig.label}/></div>}
        <RefreshButton onClick={load} loading={loading}/>
        {["subscriptions", "promocodes", "partners", "admins", "broadcast"].includes(page) && <Button onClick={() => setCreateOpen(true)}>Добавить</Button>}
      </Card>
      {page === "admins" && <Button variant="outline" onClick={() => setLoginJournalOpen(true)}>Журнал входов</Button>}
      <Card className={`table-card resource-table resource-${page}`}>
        {loading ? (
          <Empty text="Загрузка данных…" />
        ) : error && !rows.length ? (
          <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>
        ) : !filtered.length ? (
          <Empty />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c} aria-sort={sort.key===c?(sort.direction==="asc"?"ascending":"descending"):undefined}>{sortableFields.includes(c)?<button type="button" className="table-sort" onClick={()=>{setSort(current=>({key:c,direction:current.key===c&&current.direction==="asc"?"desc":"asc"}));setTablePage(1);}}>{friendlyLabel(c)}{sort.key===c?(sort.direction==="asc"?<ArrowUp size={13}/>:<ArrowDown size={13}/>):<ChevronDown size={13}/>}</button>:friendlyLabel(c)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row, i) => (
                  <tr
                    className="clickable-row"
                    tabIndex={0}
                    aria-label={`Открыть запись ${row.id || i + 1}`}
                    onKeyDown={event => { if(event.key === "Enter" || event.key === " ") { event.preventDefault(); openRow(row); } }}
                    onClick={() => openRow(row)}
                    key={row.id || i}
                  >
                    {columns.map((c) => (
                      <td key={c}>
                        {c.toLowerCase().includes("status") ? (
                          <Badge
                            tone={
                              ["active", "approved"].some((status) => String(row[c]).toLowerCase().includes(status))
                                ? "success"
                                : "muted"
                            }
                          >
                            {friendlyValue(c, row[c])}
                          </Badge>
                        ) : (
                          <span className="table-cell-text" title={String(friendlyValue(c, row[c]) ?? "")}>
                            {friendlyValue(c, row[c])}
                          </span>
                        )}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!loading && (serverPaged ? totalRows : filtered.length) > 0 && (
          <div className="pagination-bar">
            <span className="muted">Показано {serverPaged ? `${(tablePage - 1) * pageSize + 1}–${Math.min(tablePage * pageSize, totalRows)} из ${totalRows}` : `${(tablePage - 1) * pageSize + 1}–${Math.min(tablePage * pageSize, filtered.length)} из ${filtered.length}`}</span>
            <div className="pagination-controls">
              <label className="page-size-label">Строк
                <Dropdown value={pageSize} onChange={(value) => { setPageSize(Number(value)); setTablePage(1); }} options={[10, 25, 50, 100].map((size) => ({ value: size, label: String(size) }))} ariaLabel="Количество строк на странице" />
              </label>
              <Button variant="outline" size="icon" disabled={tablePage <= 1} onClick={() => setTablePage((value) => value - 1)} aria-label="Предыдущая страница"><ChevronLeft size={15}/></Button>
              <span className="page-number">{tablePage} / {totalPages}</span>
              <Button variant="outline" size="icon" disabled={tablePage >= totalPages} onClick={() => setTablePage((value) => value + 1)} aria-label="Следующая страница"><ChevronRight size={15}/></Button>
            </div>
          </div>
        )}
      </Card>
      {error && rows.length ? (
        <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>
      ) : null}
      <Dialog
        title={
          page === "users"
            ? `Пользователь #${selected?.id ?? ""}`
            : meta[page]?.label || "Запись"
        }
        row={page === "admins" || page === "subscriptions" || page === "legal" ? null : selected?.details?.user || selected}
        isUser={page === "users"}
        page={page}
        onAction={onAction}
        onResourceAction={onResourceAction}
        onClose={closeSelection}
      />
      {page === "admins" && selected && <AdminAuditDialog admin={selected} onClose={closeSelection} onSaved={load} />}
      {page === "admins" && loginJournalOpen && <AdminLoginJournalDialog onClose={() => setLoginJournalOpen(false)} />}
      {page === "subscriptions" && <SubscriptionDialog row={selected?.details?.subscription || selected} onClose={closeSelection} onUpdated={async () => { await load(); const details = await api(`/subscriptions/${selected.id}/details`); setSelected({ ...selected, ...(details.subscription || {}), details }); }} />}
      {page === "legal" && selected && <LegalDialog key={selected.key} row={selected} onClose={closeSelection} onUpdated={load} />}
      {createOpen && (
        <CreateDialog
          page={page}
          onClose={() => setCreateOpen(false)}
          onCreated={load}
        />
      )}
    </div>
  );
}

function PlanEditDialog({ plan, onClose, onSaved }) {
  const [form, setForm] = useState({ ...plan });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const set = (key, value) => setForm((current) => ({ ...current, [key]: value }));
  const submit = async (event) => {
    event.preventDefault(); setBusy(true); setError("");
    try {
      await api(`/plans/${plan.id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: String(form.name || "").trim(), price: Number(form.price), period_days: Number(form.period_days), gb_limit: Number(form.gb_limit || 0), device_limit: Number(form.device_limit || 0), purchase_limit: Number(form.purchase_limit || 0), is_hidden: Boolean(form.is_hidden), is_trial: Boolean(form.is_trial) }) });
      await onSaved(); onClose();
    } catch (e) { setError(e.message); } finally { setBusy(false); }
  };
  const field = (key, label, type = "text") => <label className="ui-field" key={key}><span>{label}</span><input required={key === "name"} type={type} value={form[key] ?? ""} onChange={(e) => set(key, type === "number" ? e.target.value : e.target.value)} /></label>;
  return <ModalFrame onClose={onClose} busy={busy}><section className="dialog create-dialog plan-edit-dialog" role="dialog" aria-modal="true"><div className="dialog-head"><div><div className="eyebrow">Настройка тарифа</div><h2>Редактировать тариф</h2><p className="muted">Изменения применятся к новым покупкам после сохранения.</p></div><Button variant="ghost" size="icon" onClick={onClose} data-dialog-close="true" aria-label="Закрыть"><X size={17}/></Button></div><form className="create-form" onSubmit={submit}>{field("name", "Название тарифа")}{field("price", "Стоимость, ₽", "number")}{field("period_days", "Срок действия, дней", "number")}{field("gb_limit", "Лимит трафика, ГБ", "number")}{field("device_limit", "Лимит устройств", "number")}{field("purchase_limit", "Лимит покупок, 0 — без ограничений", "number")}<label className="check-field"><input type="checkbox" checked={Boolean(form.is_hidden)} onChange={(e) => set("is_hidden", e.target.checked)}/>Скрыть тариф</label><label className="check-field"><input type="checkbox" checked={Boolean(form.is_trial)} onChange={(e) => set("is_trial", e.target.checked)}/>Пробный тариф</label>{error && <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>}<div className="dialog-actions"><Button type="button" variant="outline" onClick={onClose} data-dialog-close="true" aria-label="Закрыть">Отмена</Button><Button type="submit" loading={busy} disabled={busy}>{busy ? "Сохраняем…" : "Сохранить изменения"}</Button></div></form></section></ModalFrame>;
}

function PlansPage() {
  const [plans, setPlans] = useState([]),
    [loading, setLoading] = useState(true),
    [error, setError] = useState(""),
    [dragged, setDragged] = useState(null),
    [createOpen, setCreateOpen] = useState(false),
    [selected, setSelected] = useState(null),
    [editing, setEditing] = useState(null);
  const load = () => {
    setLoading(true);
    setError("");
    return api("/plans?sort_by=display_order&sort_dir=asc")
      .then((data) => setPlans(data.items || []))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
  }, []);
  const move = async (id, direction) => {
    await api(`/plans/${id}/move`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ direction }),
    });
    await load();
  };
  const drop = async (targetId) => {
    if (!dragged || dragged === targetId) return;
    const from = plans.findIndex((p) => p.id === dragged),
      to = plans.findIndex((p) => p.id === targetId);
    if (from < 0 || to < 0) return;
    const direction = from < to ? "down" : "up";
    try {
      for (let i = 0; i < Math.abs(to - from); i++)
        await move(dragged, direction);
    } catch (e) {
      setError(e.message);
      await load();
    } finally {
      setDragged(null);
    }
  };
  return (
    <div className="stack">
      <Card className="toolbar-card">
        <RefreshButton onClick={load} loading={loading}/>
        <Button onClick={() => setCreateOpen(true)}>Добавить тариф</Button>
      </Card>
      <Card className="table-card">
        {loading ? (
          <Empty text="Загрузка тарифов…" />
        ) : error && !plans.length ? (
          <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>
        ) : (
          <div className="plans-list">
            {plans.map((plan, index) => (
              <article
                className={`plan-row ${dragged === plan.id ? "is-dragging" : ""}`}
                key={plan.id}
                draggable
                onDragStart={() => setDragged(plan.id)}
                onDragEnd={() => setDragged(null)}
                onDragOver={(e) => e.preventDefault()}
                onDrop={() => drop(plan.id)}
                onClick={() => setSelected(plan)}
              >
                <button
                  className="drag-handle"
                  aria-label={`Перетащить тариф ${plan.name}`}
                >
                  <GripVertical size={18} />
                </button>
                <div className="plan-order">{index + 1}</div>
                <div className="plan-main">
                  <strong>{plan.name}</strong>
                  <span className="muted">
                    #{plan.id} · {plan.period_days} дн. · {plan.gb_limit ?? 0}{" "}
                    ГБ
                  </span>
                </div>
                <div className="plan-price">{plan.price} ₽</div>
                <Badge tone={plan.is_hidden ? "muted" : "success"}>
                  {plan.is_hidden ? "Скрыт" : "Активен"}
                </Badge>
                <div
                  className="plan-actions"
                  onClick={(e) => e.stopPropagation()}
                >
                  <Button variant="outline" size="sm" onClick={() => setEditing(plan)}>Изменить</Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={index === 0}
                    onClick={() => move(plan.id, "up")}
                    aria-label="Поднять тариф"
                  >
                    <ArrowUp size={15} />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    disabled={index === plans.length - 1}
                    onClick={() => move(plan.id, "down")}
                    aria-label="Опустить тариф"
                  >
                    <ArrowDown size={15} />
                  </Button>
                </div>
              </article>
            ))}
          </div>
        )}
      </Card>
      {error && plans.length ? (
        <Notice kind="error" role="alert" onClose={()=>setError("")}>{error}</Notice>
      ) : null}
      <Dialog
        title={selected ? `Тариф #${selected.id}` : "Тариф"}
        row={selected}
        onClose={() => setSelected(null)}
      />
      {createOpen && <CreateDialog page="plans" onClose={() => setCreateOpen(false)} onCreated={load} />}
      {editing && <PlanEditDialog plan={editing} onClose={() => setEditing(null)} onSaved={load} />}
    </div>
  );
}

function AdminChart({ stats }) { return <Suspense fallback={<LunetSkeleton rows={2}/>}><ActivityChart stats={stats} /></Suspense>; }
function adminLoginError(error) {
  if (/[а-яё]/i.test(error.message)) return error.message;
  const messages = {
    "Invalid credentials": "Неверная почта или пароль. Проверьте данные и попробуйте ещё раз.",
    "Invalid or expired verification code": "Код неверный или срок его действия истёк. Проверьте код или начните вход заново.",
    "Invalid verification code": "Код подтверждения неверный. Введите новый код из приложения или резервный код.",
    "Too many attempts. Try again later": "Слишком много попыток входа. Подождите немного и попробуйте снова.",
    "Too many verification attempts": "Лимит попыток подтверждения исчерпан. Подождите немного и начните вход заново.",
    "Unable to send verification code": "Не удалось отправить письмо с кодом. Попробуйте позже.",
    "Security configuration is incomplete": "Вход временно недоступен. Обратитесь к администратору сервера.",
    "Request origin is not allowed": "Не удалось подтвердить безопасность запроса. Откройте страницу входа заново.",
    "HTTPS is required": "Для входа откройте сайт по защищённому адресу HTTPS.",
  };
  if (messages[error.message]) return messages[error.message];
  if (error instanceof TypeError) return "Не удалось связаться с сервером. Проверьте подключение и попробуйте снова.";
  return "Не удалось выполнить вход. Попробуйте ещё раз чуть позже.";
}

function LoginErrorNotice({ message, onDismiss }) {
  if (!message) return null;
  return <CabinetToast message={message} kind="error" onClose={onDismiss}/>;
}

function AdminLogin() {
  const [login, setLogin] = useState(""),
    [password, setPassword] = useState(""),
    [code, setCode] = useState(""),
    [challenge, setChallenge] = useState(null),
    [recoveryCodes, setRecoveryCodes] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
    if (busy) return;
    setBusy(true);
    setError("");
    try {
      if (!challenge) {
        const result = await api("/auth/login", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email: login, password }),
        });
        setChallenge(result);
      } else {
        const result = await api("/auth/verify-2fa", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ challenge_id: challenge.challenge_id, code }),
        });
        if (result.requires_2fa) { setChallenge(result); setCode(""); }
        else if (result.recovery_codes) setRecoveryCodes(result.recovery_codes);
        else location.href = "/admin/dashboard";
      }
    } catch (e) {
      setError(adminLoginError(e));
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="login-page">
      <form className="login-form" onSubmit={submit}>
        <a className="admin-login-brand" href="https://lunet.pro/">Lunet <span>VPS</span></a>
        <h2>{recoveryCodes ? "Сохраните коды" : challenge ? "Подтвердите вход" : "Вход"}</h2>
        <p className="muted">
          {recoveryCodes ? "Одноразовые резервные коды для входа. Сохраните их в безопасном месте: повторно они не показываются." : challenge
            ? challenge.factor === "totp" ? "Введите код из приложения-аутентификатора или резервный код." : challenge.factor === "enroll" ? "Добавьте ключ ниже в приложение-аутентификатор и введите полученный шестизначный код." : `Код отправлен на ${challenge.email_hint || "вашу почту"}.`
            : "Введите логин и пароль администратора."}
        </p>
        {recoveryCodes ? <><pre className="admin-recovery-codes">{recoveryCodes.join("\n")}</pre><Button type="button" className="full" onClick={()=>location.assign("/admin/dashboard")}>Перейти в панель</Button></> : !challenge ? (
          <>
            <Field
              label="Почта"
              placeholder="Ваша почта"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              autoFocus
              required
              autoComplete="username"
            />
            <Field
              label="Пароль"
              placeholder="Пароль"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoComplete="current-password"
            />
          </>
        ) : (
          <>{challenge.factor === "enroll" && <div className="admin-factor-secret"><span>Ключ аутентификатора</span><code>{challenge.setup_secret}</code></div>}<Field
            label="Код подтверждения"
            placeholder="Код подтверждения"
            required
            inputMode={challenge.factor === "totp" ? "text" : "numeric"}
            pattern={challenge.factor === "totp" ? "[A-Za-z0-9_-]{6,32}" : "[0-9]{6}"}
            maxLength={challenge.factor === "totp" ? 32 : 6}
            value={code}
            onChange={(e) => setCode(e.target.value.trim())}
            autoFocus
            autoComplete="one-time-code"
          /></>
        )}
        <LoginErrorNotice message={error} onDismiss={() => setError("")} />
        {!recoveryCodes&&<Button type="submit" className="full" disabled={busy} loading={busy}>
          {busy ? "Проверяем…" : challenge ? "Подтвердить вход" : "Продолжить"}
        </Button>}
        {challenge && !recoveryCodes && (
          <Button
            type="button"
            variant="ghost"
            className="full"
            disabled={busy}
            onClick={() => {
              setChallenge(null);
              setCode("");
              setError("");
            }}
          >
            Изменить данные
          </Button>
        )}
        <p className="security-note">
          Двухфакторная проверка обязательна для каждого администратора.
        </p>
      </form>
    </main>
  );
}

function AdminNotFound() {
  return <NotFound description="Такого раздела в панели администратора нет." href="/admin/" action="Вернуться в админку"/>;
}

async function checkAdminSession() {
  const admin = await api("/auth/me");
  const page = location.pathname.split("/").filter(Boolean)[1] || "dashboard";
  if (admin.role === "support" && !new Set(["users","subscriptions","transactions","referrals"]).has(page)) {
    location.replace("/admin/users");
    throw Object.assign(new Error("Перенаправление"), { status:401 });
  }
  return admin;
}

function AdminWorkspace({ admin, page, navigate }) {
  const allowedPage = admin.role === "support" && !new Set(["users","subscriptions","transactions","referrals"]).has(page) ? "users" : page;
  useEffect(() => { if (allowedPage !== page) navigate(allowedPage, true); }, [allowedPage, page]);
  return <Shell page={allowedPage} initialAdmin={admin} onNavigate={navigate}>
    {allowedPage === "dashboard" ? <Dashboard key={allowedPage}/> : allowedPage === "plans" ? <PlansPage key={allowedPage}/> : allowedPage === "maintenance" ? <MaintenancePage key={allowedPage}/> : allowedPage === "servers" ? <ServersPage api={api}/> : <ResourcePage key={allowedPage} page={allowedPage}/>}
  </Shell>;
}

function AdminApp() {
  const readPage = () => location.pathname.split("/").filter(Boolean)[1] || "dashboard";
  const [page, setPage] = useState(readPage);
  useEffect(() => {
    const back = () => setPage(readPage());
    window.addEventListener("popstate", back);
    return () => window.removeEventListener("popstate", back);
  }, []);
  const navigate = (next, replace = false) => {
    if (next === readPage()) return;
    history[replace ? "replaceState" : "pushState"](null, "", `/admin/${next}`);
    setPage(next);
  };
  if (page === "login") return <AdminLogin />;
  if (page !== "dashboard" && page !== "plans" && page !== "maintenance" && page !== "servers" && !resourceConfig[page]) {
    return <AdminNotFound />;
  }
  return (
    <SessionGate check={checkAdminSession}>{admin => <AdminWorkspace admin={admin} page={page} navigate={navigate}/>}</SessionGate>
  );
}
function App() {
  const [pending,setPending]=useState(false),[code,setCode]=useState(""),[busy,setBusy]=useState(false),[error,setError]=useState("");
  const resolve=useRef([]);
  useEffect(()=>{
    requestAdminReauthentication=()=>new Promise(done=>{if(!resolve.current.length){setPending(true);setCode("");setError("");}resolve.current.push(done);});
    return()=>{resolve.current.forEach(done=>done(false));resolve.current=[];requestAdminReauthentication=async()=>false;};
  },[]);
  const close=()=>{if(busy)return;setPending(false);resolve.current.forEach(done=>done(false));resolve.current=[];};
  const submit=async event=>{event.preventDefault();if(busy)return;setBusy(true);setError("");try{await api("/auth/reauthenticate",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({code})});setPending(false);resolve.current.forEach(done=>done(true));resolve.current=[];}catch(e){setError(e.message);}finally{setBusy(false);}};
  return <><AdminApp/>{pending && <ModalFrame onClose={close} busy={busy}>
    <section className="dialog verification-dialog" role="dialog" aria-modal="true">
      <div className="dialog-head"><div><div className="verification-icon"><Shield size={24}/></div><h2>Подтвердите действие</h2></div><Button variant="ghost" size="icon" onClick={close} disabled={busy} aria-label="Закрыть"><X size={18}/></Button></div>
      <form onSubmit={submit} className="verification-form">
        <p className="muted">Введите шестизначный код из приложения-аутентификатора. Подтверждение действует 5 минут.</p>
        <Field label="Код подтверждения" value={code} onChange={e=>setCode(e.target.value.replace(/\D/g, "").slice(0,6))} inputMode="numeric" pattern="[0-9]{6}" maxLength={6} autoComplete="one-time-code" required/>
        <LoginErrorNotice message={error ? adminLoginError(new Error(error)) : ""} onDismiss={()=>setError("")}/>
        <div className="dialog-actions"><Button variant="outline" onClick={close} disabled={busy}>Отмена</Button><Button type="submit" loading={busy} disabled={code.length !== 6}>Подтвердить</Button></div>
      </form>
    </section>
  </ModalFrame>}</>;

}
createRoot(document.getElementById("root")).render(<App />);
