import React, { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  BarChart3,
  Bell,
  BookOpen,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  CircleDollarSign,
  FileText,
  Gauge,
  GripVertical,
  Headphones,
  LayoutDashboard,
  LoaderCircle,
  LogOut,
  Menu,
  Moon,
  Percent,
  Megaphone,
  RefreshCw,
  Search,
  Server,
  Settings,
  Shield,
  Ticket,
  UserCog,
  Users,
  Wallet,
  X,
  ArrowUp,
  ArrowDown,
} from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Legend,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import "./styles.css";
import "./ui-overrides.css";

const API_BASE = window.__ADMIN_API_BASE_URL || "";
const api = async (path, options = {}) => {
  const r = await fetch(`${API_BASE}/api/admin${path}`, {
    credentials: "include",
    ...options,
  });
  if (r.status === 401) {
    location.href = "/admin/login";
    throw new Error("Необходима авторизация");
  }
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `HTTP ${r.status}`);
  return data;
};
const downloadAdminFile = async (path, filename) => {
  const response = await fetch(`${API_BASE}/api/admin${path}`, { credentials: "include" });
  if (response.status === 401) {
    location.href = "/admin/login";
    throw new Error("Необходима авторизация");
  }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    throw new Error(data.detail || `HTTP ${response.status}`);
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
  ...props
}) {
  return (
    <button
      type={props.type || "button"}
      className={`ui-button ui-button-${variant} ui-button-${size} ${className}`}
      {...props}
    >
      {children}
    </button>
  );
}

function Spinner() {
  return <LoaderCircle className="button-spinner" size={15} role="status" aria-label="Загрузка" />;
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
  const [open, setOpen] = useState(false);
  const root = useRef(null);
  const selected = options.find((option) => String(option.value) === String(value)) || options[0];
  useEffect(() => {
    const close = (event) => { if (root.current && !root.current.contains(event.target)) setOpen(false); };
    document.addEventListener("mousedown", close);
    return () => document.removeEventListener("mousedown", close);
  }, []);
  return <div className={`custom-dropdown ${open ? "is-open" : ""}`} ref={root}>
    <button type="button" className="custom-dropdown-trigger" aria-haspopup="listbox" aria-expanded={open} aria-label={ariaLabel} onClick={() => setOpen((state) => !state)}>
      <span>{selected?.label ?? value}</span><ChevronDown size={15} />
    </button>
    {open && <div className="custom-dropdown-menu" role="listbox">
      {options.map((option) => <button type="button" role="option" aria-selected={String(option.value) === String(value)} className={`custom-dropdown-option ${String(option.value) === String(value) ? "is-selected" : ""}`} key={option.value} onClick={() => { onChange(option.value); setOpen(false); }}>{option.label}</button>)}
    </div>}
  </div>;
}
function Icon({ icon: C, size = 16 }) {
  return C ? <C size={size} strokeWidth={1.8} /> : null;
}

function Login() {
  const [login, setLogin] = useState(""),
    [password, setPassword] = useState(""),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    setError("");
    try {
      await api("/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ login, password }),
      });
      location.href = "/admin/dashboard";
    } catch (err) {
      setError(err.message || "Не удалось выполнить вход");
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="login-page">
      <div className="login-panel">
        <div className="brand">
          <span className="brand-mark logo-mark"><img src="/miniapp/assets/lunet-logo.png" alt="Lunet" /></span>
          <span>
            <b>Lunet</b>
            <small>Control center</small>
          </span>
        </div>
        <div className="login-copy">
          <Badge tone="success">
            <span className="status-dot" /> Защищённая зона
          </Badge>
          <h1>
            Управление сервисом
            <br />в одном пространстве
          </h1>
          <p>Пользователи, платежи, подписки и состояние инфраструктуры.</p>
        </div>
      </div>
      <form className="login-form" onSubmit={submit}>
        <div className="eyebrow">Авторизация</div>
        <h2>Добро пожаловать</h2>
        <p className="muted">Введите данные учётной записи администратора.</p>
        <Field
          label="Логин"
          value={login}
          onChange={(e) => setLogin(e.target.value)}
          autoFocus
          autoComplete="username"
        />
        <Field
          label="Пароль"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          autoComplete="current-password"
        />
        <div className="form-error">{error}</div>
        <Button type="submit" className="full" disabled={busy}>
          {busy ? "Выполняется…" : "Войти в панель"}
        </Button>
        <p className="security-note">
          Доступ к панели журналируется и защищён.
        </p>
      </form>
    </main>
  );
}

function Shell({ page, children }) {
  const [open, setOpen] = useState(false),
    [dark, setDark] = useState(localStorage.getItem("admin-theme") === "dark"),
    [userMenu, setUserMenu] = useState(false),
    [admin, setAdmin] = useState(null);
  useEffect(() => {
    document.documentElement.classList.toggle("dark", dark);
    localStorage.setItem("admin-theme", dark ? "dark" : "light");
  }, [dark]);
  useEffect(() => {
    api("/auth/me")
      .then((me) => {
        setAdmin(me);
        if (me.role === "support" && !new Set(["users", "subscriptions", "transactions", "referrals"]).has(page))
          location.replace("/admin/users");
      })
      .catch(() => {});
  }, [page]);
  useEffect(() => {
    if (!admin) return;
    const name = admin.username || admin.login || "Администратор";
    document
      .querySelectorAll(".sidebar-user b, .user-menu-name")
      .forEach((node) => {
        node.textContent = name;
      });
    document
      .querySelectorAll(".sidebar-user .avatar, .user-menu-trigger .avatar")
      .forEach((node) => {
        node.textContent = name.slice(0, 1).toUpperCase();
      });
  }, [admin]);
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
  const logout = async () => {
    await api("/auth/logout", { method: "POST" }).catch(() => {});
    location.href = "/admin/login";
  };
  return (
    <div className="admin-shell">
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="sidebar-brand">
          <span className="brand-mark logo-mark"><img src="/miniapp/assets/lunet-logo.png" alt="Lunet" /></span>
          <span>
            <b>Lunet</b>
            <small>Control center</small>
          </span>
        </div>
        <nav>
          {visibleNav.map((group) => (
            <div className="nav-group" key={group.group}>
              <div className="nav-label">{group.group}</div>
              {group.items.map((item) => (
                <a
                  className={page === item.key ? "active" : ""}
                  href={`/admin/${item.key}`}
                  onClick={() => setOpen(false)}
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
          <span className="avatar">A</span>
          <span>
            <b>Администратор</b>
            <small>Системный доступ</small>
          </span>
          <button className="icon-button" onClick={logout} aria-label="Выйти">
            <LogOut size={16} />
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
            <Button
              variant="outline"
              size="icon"
              onClick={() => setDark(!dark)}
              aria-label="Тема"
            >
              {dark ? <Moon size={16} /> : <Moon size={16} />}
            </Button>
            <div className="user-menu-wrap">
              <Button
                variant="ghost"
                className="user-menu-trigger"
                aria-expanded={userMenu}
                onClick={() => setUserMenu(!userMenu)}
              >
                <span className="avatar">A</span>
                <span className="user-menu-name">Администратор</span>
                <ChevronDown size={14} />
              </Button>
              {userMenu && (
                <div className="user-menu" role="menu">
                  <div className="user-menu-caption">Системный доступ</div>
                  <button
                    role="menuitem"
                    onClick={() => {
                      setDark(!dark);
                      setUserMenu(false);
                    }}
                  >
                    <Moon size={15} /> {dark ? "Светлая тема" : "Тёмная тема"}
                  </button>
                  <button role="menuitem" onClick={logout}>
                    <LogOut size={15} /> Выйти
                  </button>
                </div>
              )}
            </div>
          </div>
        </header>
        <main className="page">
          {page !== "payments" && <div className="page-heading">
            <div>
              <div className="eyebrow">Lunet workspace</div>
              <h1>{meta[page]?.label || "Дашборд"}</h1>
              <p className="muted">
                {page === "dashboard"
                  ? "Обзор состояния сервиса и ключевых показателей"
                  : "Управление разделом и данными системы"}
              </p>
            </div>
          </div>}
          {children}
        </main>
      </div>
    </div>
  );
}

function Dashboard() {
  const [data, setData] = useState(null),
    [error, setError] = useState(""),
    [chartFrom, setChartFrom] = useState(""),
    [chartTo, setChartTo] = useState("");
  const load = () => {
    const params =
      chartFrom || chartTo
        ? `?chart_from=${chartFrom || chartTo}&chart_to=${chartTo || chartFrom}`
        : "";
    return api(`/stats${params}`)
      .then(setData)
      .catch((e) => setError(e.message));
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
      stats.total_revenue ? `${stats.total_revenue} RUB` : null,
      Wallet,
    ],
  ];
  return (
    <div className="stack">
      <div className="stats-grid">
        {cards
          .filter(([, , icon]) => icon !== Shield && icon !== Server)
          .map(([label, value, icon]) => (
            <Card className="stat-card" key={label}>
              <div className="stat-icon">
                <Icon icon={icon} size={18} />
              </div>
              <div>
                <span className="muted">{label}</span>
                <strong>{value ?? "—"}</strong>
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
              <Button variant="outline" size="sm" onClick={load}>
                <RefreshCw size={14} /> Обновить
              </Button>
            }
          />
          {error ? (
            <Empty text={error} />
          ) : data ? (
            <div className="chart-summary">
              <div>
                <strong>{stats.month_revenue ?? 0} RUB</strong>
                <span className="muted">Выручка за текущий месяц</span>
              </div>
              <AdminChart stats={stats} />
            </div>
          ) : (
            <Empty text="Загрузка данных…" />
          )}
        </Card>
        <Card>
          <CardHeader title="Состояние системы" />
          <div className="health-list">
            <Health label="API" />
            <Health label="База данных" />
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
function Health({ label }) {
  return (
    <div className="health-row">
      <span>{label}</span>
      <Badge tone="success">
        <Check size={12} /> Работает
      </Badge>
    </div>
  );
}
function Empty({ text = "Нет данных" }) {
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
  email: "Email",
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
  if (key === "status") return ({ active: "Активна", expired: "Истекла", canceled: "Отменена", past_due: "Просрочена", pending: "На рассмотрении", approved: "Одобрено", rejected: "Отклонено" }[String(value)] || String(value));
  if (["current_period_start", "current_period_end", "next_renewal_at", "created_at", "updated_at"].includes(key)) { const d = new Date(value); if (!Number.isNaN(d.getTime())) return d.toLocaleString("ru-RU", { dateStyle: "medium", timeStyle: "short" }); }
  if (key === "gb_left") return `${Number(value).toLocaleString("ru-RU")} ГБ`;
  if (key === "traffic_limit_bytes")
    return `${(Number(value) / 1024 ** 3).toFixed(2)} GB`;
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
    FIELD_LABELS[key] ||
    key.replaceAll("_", " ").replace(/\b\w/g, (char) => char.toUpperCase())
  );
}
function Dialog({ title, row, onClose, isUser, onAction, page, onResourceAction }) {
  const [amount, setAmount] = useState("100"),
    [gb, setGb] = useState("1"),
    [days, setDays] = useState("30"),
    [reason, setReason] = useState(""),
    [busy, setBusy] = useState(false),
    [busyAction, setBusyAction] = useState(""),
    [error, setError] = useState("");
  if (!row) return null;
  const run = async (action) => {
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
    setBusy(true);
    setBusyAction(action);
    setError("");
    try {
      if (isUser) await onAction(action, { amount: Number(amount), gb: Number(gb), duration_hours: Number(days) * 24, ...(action === "ban" ? { reason: reason.trim() } : {}) });
      else await onResourceAction(action);
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
      setBusyAction("");
    }
  };
  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section className="dialog" role="dialog" aria-modal="true">
        <div className="dialog-head">
          <div>
            <div className="eyebrow">Детальная информация</div>
            <h2>{title}</h2>
            <p className="muted">
              Данные синхронизированы с панелью. Изменения попадут в историю
              пользователя.
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
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
              <p className="muted">Укажи сумму в рублях.</p>
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
                  {busyAction === "add_traffic" && <Spinner />}Начислить GB
                </Button>
                <Button
                  variant="outline"
                  disabled={busy}
                  onClick={() => run("sub_traffic")}
                >
                  {busyAction === "sub_traffic" && <Spinner />}Списать GB
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
            {error && <div className="inline-error">{error}</div>}
          </div>
        )}
        {!isUser && page === "transactions" && <div className="user-actions"><div className="action-section"><h3>Оплата</h3><p className="muted">Подтвердить оплату и начислить сумму на баланс пользователя.</p><Button disabled={busy || row.paid} onClick={() => run("confirm")}>{busyAction === "confirm" && <Spinner />}{row.paid ? "Уже подтверждено" : "Подтвердить транзакцию"}</Button></div></div>}
        {!isUser && page === "withdrawals" && <div className="user-actions"><div className="action-section"><h3>Решение по заявке</h3><p className="muted">После подтверждения деньги будут перечислены пользователю.</p><div className="action-row"><Button disabled={busy || row.status !== "pending"} onClick={() => run("approve")}>{busyAction === "approve" && <Spinner />}Подтвердить вывод</Button><Button variant="danger" disabled={busy || row.status !== "pending"} onClick={() => run("reject")}>{busyAction === "reject" && <Spinner />}Отклонить вывод</Button></div></div></div>}
        {!isUser && page === "promocodes" && <div className="user-actions"><div className="action-section action-section-danger"><h3>Управление промокодом</h3><p className="muted">Удаление промокода нельзя отменить.</p><Button variant="danger" disabled={busy} onClick={() => run("delete")}>Удалить промокод</Button></div></div>}
        {!isUser && page === "partners" && row.details && <div className="user-actions"><div className="action-section"><h3>Активность партнёрской ссылки</h3><div className="partner-summary"><span>Регистрации: <b>{row.details.summary?.attributed_users ?? 0}</b></span><span>Пользователи с оплатой: <b>{row.details.summary?.paid_users ?? 0}</b></span><span>Оплаченные пополнения: <b>{row.details.summary?.paid_topups ?? 0}</b></span><span>Сумма: <b>{row.details.summary?.paid_amount ?? 0} RUB</b></span></div><div className="partner-activity-list">{(row.details.users || []).slice(0, 8).map((user) => <div key={user.user_id}><span>{user.username || `Пользователь #${user.user_id}`}</span><span>{user.paid_amount ? `${user.paid_amount} RUB` : "Без оплат"}</span></div>)}</div></div></div>}
        {!isUser && page === "logs" && <div className="user-actions"><div className="action-section"><h3>Файл журнала</h3><Button disabled={busy} onClick={() => run("download")}>{busyAction === "download" && <Spinner />}Скачать лог</Button></div></div>}
        <div className="dialog-actions">
          <Button variant="outline" onClick={onClose}>
            Закрыть
          </Button>
        </div>
      </section>
    </div>
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
    setBusy(true);
    setError("");
    try {
      if (page === "broadcast") {
        const body = new FormData();
        body.append("text", form.text || "");
        body.append("parse_mode", form.parse_mode || "HTML");
        body.append("include_banned", String(Boolean(form.include_banned)));
        if (form.image) body.append("image", form.image);
        const response = await fetch(`${API_BASE}/api/admin/broadcast/upload`, {
          method: "POST",
          credentials: "include",
          body,
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok)
          throw new Error(data.detail || `HTTP ${response.status}`);
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
      <span>{page === "admins" && key === "user_id" ? "Username" : page === "admins" && key === "login" ? "Email" : label}</span>
      <input
        required={required}
        type={page === "admins" && key === "user_id" ? "text" : page === "admins" && key === "login" ? "email" : type}
        value={form[page === "admins" && key === "user_id" ? "username" : page === "admins" && key === "login" ? "email" : key] ?? ""}
        onChange={(e) => set(page === "admins" && key === "user_id" ? "username" : page === "admins" && key === "login" ? "email" : key, e.target.value)}
      />
    </label>
  );
  return (
    <div
      className="dialog-backdrop"
      role="presentation"
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}
    >
      <section className={`dialog create-dialog ${page === "broadcast" ? "broadcast-dialog" : ""}`} role="dialog" aria-modal="true">
        <div className="dialog-head">
          <div>
            <div className="eyebrow">Новое действие</div>
            <h2>
              {page === "broadcast"
                ? "Создать рассылку"
                : `Добавить: ${meta[page]?.label || "запись"}`}
            </h2>
            <p className="muted">После сохранения данные появятся в таблице.</p>
          </div>
          <Button
            variant="ghost"
            size="icon"
            onClick={onClose}
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
              {input("price", "Цена, RUB", "number")}
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
                Trial-тариф
              </label>
            </>
          )}
          {page === "promocodes" && (
            <>
              {input("code", "Код промокода")}
              {input("amount", "Сумма, RUB", "number")}
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
          {error && <div className="inline-error">{error}</div>}
          <div className="dialog-actions">
            <Button type="button" variant="outline" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" disabled={busy}>
              {busy
                ? "Сохраняем…"
                : page === "broadcast"
                  ? "Запустить рассылку"
                  : "Создать"}
            </Button>
          </div>
        </form>
      </section>
    </div>
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
    <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <section className="dialog" role="dialog" aria-modal="true">
        <div className="dialog-head">
          <div><div className="eyebrow">Управление подпиской</div><h2>Подписка #{row.id}</h2><p className="muted">Изменения сразу сохраняются и синхронизируются с панелью.</p></div>
          <Button variant="ghost" size="icon" onClick={onClose} aria-label="Закрыть"><X size={17}/></Button>
        </div>
        <div className="dialog-grid">{Object.entries(row).filter(([, value]) => typeof value !== "object").map(([key, value]) => <div className="detail-item" key={key}><span>{friendlyLabel(key)}</span><b>{friendlyValue(key, value)}</b></div>)}</div>
        <div className="user-actions">
          <div className="action-section"><h3>Срок действия</h3><div className="action-row"><input type="number" min="1" value={days} onChange={(e) => setDays(e.target.value)} aria-label="Количество дней"/><Button disabled={busy} onClick={() => run("extend")}>{busyAction === "extend" && <Spinner />}Продлить</Button><Button variant="outline" disabled={busy} onClick={() => run("reduce")}>{busyAction === "reduce" && <Spinner />}Уменьшить срок</Button></div></div>
          <div className="action-section"><h3>Устройства</h3><div className="action-row"><input type="number" min="1" value={devices} onChange={(e) => setDevices(e.target.value)} aria-label="Количество устройств"/><Button disabled={busy} onClick={() => run("add_devices")}>{busyAction === "add_devices" && <Spinner />}Добавить устройства</Button><Button variant="outline" disabled={busy} onClick={() => run("remove_devices")}>{busyAction === "remove_devices" && <Spinner />}Уменьшить устройства</Button></div></div>
          <div className="action-section"><h3>Синхронизация</h3><p className="muted">Отправить текущие срок, трафик, статус и лимит устройств в Remnawave.</p><Button type="button" disabled={busy} onClick={() => run("sync")}>{busyAction === "sync" ? <Spinner /> : <RefreshCw size={14}/>} {busy ? "Синхронизируем…" : "Синхронизировать с панелью"}</Button></div>
          {success && <div className="inline-success">{success}</div>}
          {error && <div className="inline-error">{error}</div>}
        </div>
        <div className="dialog-actions"><Button variant="outline" onClick={onClose}>Закрыть</Button></div>
      </section>
    </div>
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
    {error && <div className="inline-error">{error}</div>}
    {loading ? <Empty text="Загрузка состояния сервера…" /> : <>
      <Card className={`maintenance-control-card ${maintenance?.enabled ? "is-enabled" : ""}`}>
        <div className="card-header"><div><h2>Технические работы</h2><p className="muted">При включении пользователи увидят сообщение о временной недоступности сервиса.</p></div><Badge tone={maintenance?.enabled ? "danger" : "success"}>{maintenance?.enabled ? "Включены" : "Сервис работает"}</Badge></div>
        <label className="ui-field"><span>Сообщение для пользователей</span><textarea value={message} onChange={(e) => setMessage(e.target.value)} rows="3" /></label>
        <div className="maintenance-actions"><Button variant={maintenance?.enabled ? "danger" : "default"} disabled={busy} onClick={toggle}>{busy ? "Сохраняем…" : maintenance?.enabled ? "Завершить техработы" : "Включить техработы"}</Button><Button variant="outline" disabled={busy} onClick={load}><RefreshCw size={14}/> Обновить данные</Button></div>
      </Card>
      <div className="maintenance-grid"><Card><CardHeader title="Сервисы"/><div className="health-list">{(health?.items || []).map((item) => <div className="health-row" key={item.key}><span>{item.label}</span><Badge tone={item.status === "ok" ? "success" : item.status === "warn" ? "warn" : "danger"}>{item.status === "ok" ? "Работает" : item.status === "warn" ? "Проверьте" : "Ошибка"}</Badge></div>)}</div></Card><Card><CardHeader title="Нагрузка сервера" action={<span className="muted">{loadState?.hostname || "—"}</span>}/><div className="server-metrics">{(loadState?.metrics || []).map((metric) => <div className="server-metric" key={metric.key}><div><span>{metric.label}</span><b>{metric.value || "—"}</b></div><div className="metric-bar"><i className={`metric-${metric.status || "ok"}`} style={{ width: `${Math.min(100, Math.max(0, Number(metric.percent) || 0))}%` }}/></div></div>)}</div><p className="muted">Аптайм: {loadState?.summary?.uptime || "—"} · Проверено: {friendlyValue("checked_at", loadState?.checked_at)}</p></Card></div>
    </>}
  </div>;
}
function LegalDialog({ row, onClose, onUpdated }) {
  const [html, setHtml] = useState(row?.details?.content || ""), [busy, setBusy] = useState(false), [error, setError] = useState("");
  if (!row) return null;
  const save = async () => { setBusy(true); setError(""); try { await api(`/legal/${row.key}`, { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ html }) }); await onUpdated(); onClose(); } catch (e) { setError(e.message); } finally { setBusy(false); } };
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><section className="dialog" role="dialog" aria-modal="true"><div className="dialog-head"><div><div className="eyebrow">Документ</div><h2>{row.title || row.key}</h2><p className="muted">Поддерживаются HTML-теги форматирования. Скрипты и опасные атрибуты запрещены.</p></div><Button variant="ghost" size="icon" onClick={onClose}><X size={17}/></Button></div><label className="ui-field"><span>Содержимое документа</span><textarea className="legal-editor" rows="18" value={html} onChange={(e) => setHtml(e.target.value)} /></label>{error && <div className="inline-error">{error}</div>}<div className="dialog-actions"><Button variant="outline" onClick={onClose}>Отмена</Button><Button disabled={busy} onClick={save}>{busy ? "Сохраняем…" : "Сохранить документ"}</Button></div></section></div>;
}
function PaymentMethodsPage() {
  const [methods, setMethods] = useState([]), [loading, setLoading] = useState(true), [busy, setBusy] = useState(""), [error, setError] = useState(""), [success, setSuccess] = useState("");
  const load = async () => { setLoading(true); setError(""); try { const data = await api("/system/payment-methods"); setMethods(data.items || []); } catch (e) { setError(e.message); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);
  const toggle = async (method) => { setBusy(method.key); setError(""); setSuccess(""); try { const data = await api("/system/payment-methods", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ methods: { [method.key]: !method.enabled } }) }); setMethods(data.items || []); setSuccess(`${method.name}: настройки сохранены.`); } catch (e) { setError(e.message); } finally { setBusy(""); } };
  return <div className="stack"><div className="page-heading"><div className="eyebrow">Оплата</div><h1>Платёжные методы</h1><p className="muted">Управление доступностью способов пополнения баланса.</p></div>{error && <div className="inline-error">{error}</div>}{success && <div className="inline-success">{success}</div>}{loading ? <Empty text="Загрузка платёжных методов…" /> : <div className="payment-method-grid">{methods.map((method) => <Card key={method.key} className="payment-method-card"><div className="payment-method-top"><div><div className="eyebrow">Способ оплаты</div><h2>{method.name}</h2></div><Badge tone={method.enabled && method.configured ? "success" : method.enabled ? "warn" : "muted"}>{!method.configured ? "Не настроен" : method.enabled ? "Включён" : "Отключён"}</Badge></div><p className="muted">{method.configured ? "Учётные данные найдены в конфигурации сервера." : "Добавьте учётные данные в .env, чтобы метод стал доступен."}</p><div className="payment-method-actions"><Button disabled={busy === method.key || !method.configured} variant={method.enabled ? "outline" : "default"} onClick={() => toggle(method)}>{busy === method.key ? "Сохраняем…" : method.enabled ? "Отключить" : "Включить"}</Button><Button variant="ghost" size="sm" onClick={load}>Обновить статус</Button></div></Card>)}</div>}</div>;
}
function PaymentMethodsSettingsPage() {
  const [methods, setMethods] = useState([]), [loading, setLoading] = useState(true), [busy, setBusy] = useState(""), [error, setError] = useState(""), [success, setSuccess] = useState(""), [form, setForm] = useState({});
  const fields = { cryptobot: [{ key: "api_token", label: "Токен CryptoBot", secret: true }], pally: [{ key: "api_token", label: "API-токен Pally", secret: true }, { key: "shop_id", label: "ID магазина" }, { key: "success_url", label: "URL успешной оплаты" }, { key: "fail_url", label: "URL отменённой оплаты" }], platega: [{ key: "merchant_id", label: "Merchant ID" }, { key: "secret", label: "Секрет Platega", secret: true }, { key: "method_card", label: "Метод оплаты: карта", type: "number" }, { key: "method_sbp", label: "Метод оплаты: СБП", type: "number" }] };
  const load = async () => { setLoading(true); setError(""); try { const data = await api("/system/payment-methods"); setMethods(data.items || []); } catch (e) { setError(e.message); } finally { setLoading(false); } };
  useEffect(() => { load(); }, []);
  const updateField = (method, key, value) => setForm((current) => ({ ...current, [`${method}.${key}`]: value }));
  const save = async (method) => { setBusy(method.key); setError(""); setSuccess(""); try { const values = {}; (fields[method.key] || []).forEach((field) => { const value = form[`${method.key}.${field.key}`]; if (value !== undefined && value !== "") values[field.key] = field.type === "number" ? Number(value) : value; }); const data = await api("/system/payment-methods", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ methods: { [method.key]: method.enabled }, settings: { [method.key]: values } }) }); setMethods(data.items || []); setForm({}); setSuccess(`${method.name}: настройки сохранены.`); } catch (e) { setError(e.message); } finally { setBusy(""); } };
  const toggle = async (method) => { setBusy(`${method.key}:toggle`); setError(""); try { const data = await api("/system/payment-methods", { method: "PUT", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ methods: { [method.key]: !method.enabled } }) }); setMethods(data.items || []); } catch (e) { setError(e.message); } finally { setBusy(""); } };
  return <div className="stack"><div className="page-heading"><div className="eyebrow">Оплата</div><h1>Платёжные методы</h1><p className="muted">Включайте способы оплаты и изменяйте их параметры. Пустое поле оставляет сохранённое значение без изменений.</p></div>{error && <div className="inline-error">{error}</div>}{success && <div className="inline-success">{success}</div>}{loading ? <Empty text="Загрузка платёжных методов…" /> : <div className="payment-method-grid">{methods.map((method) => <Card key={method.key} className="payment-method-card"><div className="payment-method-top"><div><div className="eyebrow">Способ оплаты</div><h2>{method.name}</h2></div><Badge tone={method.enabled && method.configured ? "success" : method.enabled ? "warn" : "muted"}>{!method.configured ? "Не настроен" : method.enabled ? "Включён" : "Отключён"}</Badge></div><div className="payment-fields">{(fields[method.key] || []).map((field) => <label className="ui-field" key={field.key}><span>{field.label}</span><input type={field.secret ? "password" : field.type || "text"} value={form[`${method.key}.${field.key}`] || ""} placeholder={method.settings?.[field.key] ? (field.secret ? method.settings[field.key] : String(method.settings[field.key])) : "Не задано"} onChange={(e) => updateField(method.key, field.key, e.target.value)} /></label>)}</div><div className="payment-method-actions"><Button disabled={busy === method.key} onClick={() => save(method)}>{busy === method.key ? "Сохраняем…" : "Сохранить настройки"}</Button><Button disabled={busy === `${method.key}:toggle` || !method.configured} variant="outline" onClick={() => toggle(method)}>{method.enabled ? "Отключить" : "Включить"}</Button></div></Card>)}</div>}</div>;
}
function AdminLoginJournalDialog({ onClose }) {
  const [items, setItems] = useState([]);
  const [error, setError] = useState("");
  useEffect(() => { api("/admins/login-events?limit=10").then((data) => setItems(data.items || [])).catch((e) => setError(e.message)); }, []);
  const date = (value) => value ? new Date(value).toLocaleString("ru-RU") : "—";
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><section className="dialog admin-audit-dialog" role="dialog" aria-modal="true"><div className="dialog-head"><div><div className="eyebrow">Безопасность</div><h2>Журнал входов</h2><p className="muted">Кто и когда входил в панель администратора.</p></div><Button variant="ghost" size="icon" onClick={onClose}><X size={17}/></Button></div>{error && <div className="inline-error">{error}</div>}{!items.length && !error ? <p className="muted">Записей пока нет.</p> : <div className="audit-list">{items.map((item) => <div className="audit-row" key={item.id}><span>{date(item.created_at)}</span><b>{item.username || item.email || "Неизвестный администратор"}</b><span className={item.success ? "audit-success" : "audit-failure"}>{item.success ? "Успешный вход" : "Неуспешная попытка"}</span></div>)}</div>}<div className="dialog-actions"><Button variant="outline" onClick={onClose}>Закрыть</Button></div></section></div>;
}

function AdminAuditDialog({ admin, onClose, onSaved }) {
  const [form, setForm] = useState({ username: admin.username || "", email: admin.email || "", password: "", role: admin.role || "support" });
  const [audit, setAudit] = useState({ login_events: [], action_events: [] });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
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
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
    <section className="dialog admin-audit-dialog" role="dialog" aria-modal="true">
      <div className="dialog-head"><div><div className="eyebrow">Администратор</div><h2>{admin.username}</h2><p className="muted">Изменение данных и история работы в панели.</p></div><Button variant="ghost" size="icon" onClick={onClose}><X size={17}/></Button></div>
      <form className="create-form" onSubmit={save}>
        <div className="admin-edit-grid">
          <Field label="Имя пользователя" value={form.username} onChange={(e) => setForm({ ...form, username: e.target.value })} required />
          <Field label="Электронная почта" type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} required />
          <Field label="Новый пароль" type="password" placeholder="Оставьте пустым, чтобы не менять" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} />
          <label className="ui-field"><span>Роль</span><Dropdown value={form.role} onChange={(role) => setForm({ ...form, role })} options={[{ value: "support", label: "Поддержка" }, { value: "superadmin", label: "Суперадминистратор" }]} ariaLabel="Роль администратора" /></label>
        </div>
        {error && <div className="inline-error">{error}</div>}
        <div className="dialog-actions"><Button type="button" variant="outline" onClick={onClose}>Отмена</Button><Button type="submit" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить изменения"}</Button></div>
      </form>
      <div className="audit-section"><div className="audit-section-head"><h3>Журнал входов</h3><Button variant="outline" size="sm" onClick={() => window.open(`${API_BASE}/api/admin/admins/${admin.id}/audit/download`, "_blank", "noopener,noreferrer")}>Скачать CSV</Button></div>
        {!audit.login_events.length ? <p className="muted">Входов пока нет.</p> : <div className="audit-list">{audit.login_events.map((item) => <div className="audit-row" key={`login-${item.id}`}><span>{date(item.created_at)}</span><span>{item.success ? "Успешный вход" : "Неуспешная попытка"}</span><span>{item.ip_address || "IP неизвестен"}</span></div>)}</div>}
      </div>
      <div className="audit-section"><div className="audit-section-head"><h3>Последние 10 действий в панели</h3></div>
        {!audit.action_events.length ? <p className="muted">Действий пока нет.</p> : <div className="audit-list">{audit.action_events.map((item) => <div className="audit-row" key={`action-${item.id}`}><span>{date(item.created_at)}</span><b>{item.action}</b><span title={item.path}>{item.details || item.path}</span></div>)}</div>}
      </div>
    </section>
  </div>;
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
  const config = resourceConfig[page];
  const serverPaged = ["users", "subscriptions", "transactions", "withdrawals", "referrals"].includes(page);
  const load = () => {
    setLoading(true);
    setError("");
    const params = new URLSearchParams();
    if (serverPaged) {
      params.set("page", String(tablePage));
      params.set("page_size", String(pageSize));
      if (query.trim()) params.set("search", query.trim());
    }
    const path = `${config[1]}${params.toString() ? `?${params.toString()}` : ""}`;
    return api(path)
      .then(setData)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };
  useEffect(() => {
    load();
  }, [page, tablePage, pageSize, query]);
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
    ? Object.keys(rows[0])
        .filter((k) => typeof rows[0][k] !== "object")
        .slice(0, 7)
    : [];
  const openRow = async (row) => {
    const requestId = ++selectionRequest.current;
    setSelected(row);
    if (page === "users") setSelectedUserId(Number(row.id));
    if (page === "admins" && row.id) {
      try { const details = await api(`/admins/${row.id}/audit`); if (requestId === selectionRequest.current) setSelected({ ...row, audit: details }); } catch (e) { if (requestId === selectionRequest.current) setError(e.message); }
    } else if ((page === "users" || page === "subscriptions" || page === "partners" || page === "legal") && (row.id || row.key)) {
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
            placeholder="Поиск по данным…"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </div>
        <Button variant="outline" onClick={load}>
          <RefreshCw size={14} /> Обновить
        </Button>
        {["subscriptions", "promocodes", "partners", "admins", "broadcast"].includes(page) && <Button onClick={() => setCreateOpen(true)}>Добавить</Button>}
      </Card>
      {page === "admins" && <Button variant="outline" onClick={() => setLoginJournalOpen(true)}>Журнал входов</Button>}
      <Card className={`table-card resource-table resource-${page}`}>
        {loading ? (
          <Empty text="Загрузка данных…" />
        ) : error && !rows.length ? (
          <Empty text={error} />
        ) : !filtered.length ? (
          <Empty />
        ) : (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  {columns.map((c) => (
                    <th key={c}>{friendlyLabel(c)}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {visibleRows.map((row, i) => (
                  <tr
                    className="clickable-row"
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
        <div className="inline-error">{error}</div>
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
        onClose={() => setSelected(null)}
      />
      {page === "admins" && selected && <AdminAuditDialog admin={selected} onClose={() => setSelected(null)} onSaved={load} />}
      {page === "admins" && loginJournalOpen && <AdminLoginJournalDialog onClose={() => setLoginJournalOpen(false)} />}
      {page === "subscriptions" && <SubscriptionDialog row={selected?.details?.subscription || selected} onClose={() => setSelected(null)} onUpdated={async () => { await load(); const details = await api(`/subscriptions/${selected.id}/details`); setSelected({ ...selected, ...(details.subscription || {}), details }); }} />}
      {page === "legal" && <LegalDialog row={selected} onClose={() => setSelected(null)} onUpdated={load} />}
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
  return <div className="dialog-backdrop" role="presentation" onMouseDown={(e) => e.target === e.currentTarget && onClose()}><section className="dialog create-dialog plan-edit-dialog" role="dialog" aria-modal="true"><div className="dialog-head"><div><div className="eyebrow">Настройка тарифа</div><h2>Редактировать тариф</h2><p className="muted">Изменения применятся к новым покупкам после сохранения.</p></div><Button variant="ghost" size="icon" onClick={onClose} aria-label="Закрыть"><X size={17}/></Button></div><form className="create-form" onSubmit={submit}>{field("name", "Название тарифа")}{field("price", "Стоимость, ₽", "number")}{field("period_days", "Срок действия, дней", "number")}{field("gb_limit", "Лимит трафика, ГБ", "number")}{field("device_limit", "Лимит устройств", "number")}{field("purchase_limit", "Лимит покупок, 0 — без ограничений", "number")}<label className="check-field"><input type="checkbox" checked={Boolean(form.is_hidden)} onChange={(e) => set("is_hidden", e.target.checked)}/>Скрыть тариф</label><label className="check-field"><input type="checkbox" checked={Boolean(form.is_trial)} onChange={(e) => set("is_trial", e.target.checked)}/>Пробный тариф</label>{error && <div className="inline-error">{error}</div>}<div className="dialog-actions"><Button type="button" variant="outline" onClick={onClose}>Отмена</Button><Button type="submit" disabled={busy}>{busy ? "Сохраняем…" : "Сохранить изменения"}</Button></div></form></section></div>;
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
        <div className="toolbar-copy">
          <strong>Порядок тарифов</strong>
          <span className="muted">
            Перетащите строку вверх или вниз — порядок сохранится в API.
          </span>
        </div>
        <Button variant="outline" onClick={load}>
          <RefreshCw size={14} /> Обновить
        </Button>
        <Button onClick={() => setCreateOpen(true)}>Добавить тариф</Button>
      </Card>
      <Card className="table-card">
        {loading ? (
          <Empty text="Загрузка тарифов…" />
        ) : error && !plans.length ? (
          <Empty text={error} />
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
                <div className="plan-price">{plan.price} RUB</div>
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
        <div className="inline-error">{error}</div>
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

function ChartTooltipContent({ active, payload, label }) {
  if (!active || !payload?.length) return null;
  return (
    <div className="chart-tooltip">
      <b>{label}</b>
      {payload.map((item) => (
        <div key={item.dataKey}>
          <span
            className="chart-tooltip-dot"
            style={{ background: item.color }}
          />
          {item.name}: <strong>{item.value}</strong>
        </div>
      ))}
    </div>
  );
}
function AdminChart({ stats }) {
  const payments = stats.payments_chart || [];
  const data = (stats.users_chart || []).map((item, index) => ({
    label: item.label || item.date || item.key || index + 1,
    users: Number(item.count ?? item.value ?? item.users ?? 0),
    payments: Number(payments[index]?.amount ?? 0),
  }));
  if (!data.length) return <Empty text="Нет данных за выбранный период" />;
  return (
    <div className="chart-container">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={data}
          margin={{ top: 8, right: 8, left: -24, bottom: 0 }}
        >
          <CartesianGrid vertical={false} stroke="var(--chart-grid)" />
          <XAxis
            dataKey="label"
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "var(--chart-muted)" }}
          />
          <YAxis
            axisLine={false}
            tickLine={false}
            tick={{ fontSize: 11, fill: "var(--chart-muted)" }}
            allowDecimals={false}
          />
          <Tooltip
            cursor={{ fill: "var(--chart-hover)" }}
            content={<ChartTooltipContent />}
          />
          <Legend wrapperStyle={{ fontSize: 11 }} />
          <Bar
            name="Пользователи"
            dataKey="users"
            fill="var(--chart-1)"
            radius={[4, 4, 0, 0]}
            maxBarSize={36}
          />
          <Bar
            name="Выручка, RUB"
            dataKey="payments"
            fill="var(--chart-2)"
            radius={[4, 4, 0, 0]}
            maxBarSize={36}
          />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
function AdminLogin() {
  const [login, setLogin] = useState(""),
    [password, setPassword] = useState(""),
    [code, setCode] = useState(""),
    [challenge, setChallenge] = useState(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const submit = async (event) => {
    event.preventDefault();
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
        await api("/auth/verify-2fa", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ challenge_id: challenge.challenge_id, code }),
        });
        location.href = "/admin/dashboard";
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setBusy(false);
    }
  };
  return (
    <main className="login-page">
      <div className="login-panel">
        <div className="brand">
          <span className="brand-mark logo-mark"><img src="/miniapp/assets/lunet-logo.png" alt="Lunet" /></span>
          <span>
            <b>Lunet</b>
            <small>Control center</small>
          </span>
        </div>
        <div className="login-copy">
          <Badge tone="success">
            <span className="status-dot" /> Защищённая зона
          </Badge>
          <h1>
            Управление сервисом
            <br />в одном пространстве
          </h1>
          <p>Доступ к панели подтверждается одноразовым кодом на email.</p>
        </div>
      </div>
      <form className="login-form" onSubmit={submit}>
        <div className="eyebrow">Авторизация</div>
        <h2>{challenge ? "Подтвердите вход" : "Добро пожаловать"}</h2>
        <p className="muted">
          {challenge
            ? `Код отправлен на ${challenge.email_hint || "ваш email"}.`
            : "Введите логин и пароль администратора."}
        </p>
        {!challenge ? (
          <>
            <Field
              label="Email"
              value={login}
              onChange={(e) => setLogin(e.target.value)}
              autoFocus
              autoComplete="username"
            />
            <Field
              label="Пароль"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              autoComplete="current-password"
            />
          </>
        ) : (
          <Field
            label="Код подтверждения"
            inputMode="numeric"
            pattern="[0-9]{6}"
            maxLength={6}
            value={code}
            onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))}
            autoFocus
            autoComplete="one-time-code"
          />
        )}
        <div className="form-error">{error}</div>
        <Button type="submit" className="full" disabled={busy}>
          {busy ? "Проверяем…" : challenge ? "Подтвердить вход" : "Продолжить"}
        </Button>
        {challenge && (
          <Button
            type="button"
            variant="ghost"
            className="full"
            onClick={() => {
              setChallenge(null);
              setCode("");
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
  return <main className="not-found-page"><div className="not-found-card"><span className="not-found-code">404</span><h1>Страница не найдена</h1><p>Такого раздела в панели администратора нет.</p><a className="not-found-action" href="/admin/">Вернуться в админку</a></div></main>;
}

function App() {
  const path = location.pathname.split("/").filter(Boolean);
  const page = path[1] || "dashboard";
  if (page === "login") return <AdminLogin />;
  if (page !== "dashboard" && page !== "plans" && page !== "maintenance" && !resourceConfig[page]) {
    return <AdminNotFound />;
  }
  return (
    <Shell page={page}>
      {page === "dashboard" ? (
        <Dashboard />
      ) : page === "plans" ? (
        <PlansPage />
      ) : page === "maintenance" ? (
        <MaintenancePage />
      ) : (
        resourceConfig[page] ? <ResourcePage page={page} /> : <AdminNotFound />
      )}
    </Shell>
  );
}
createRoot(document.getElementById("root")).render(<App />);
