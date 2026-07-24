const API_BASE = window.__ADMIN_API_BASE_URL || window.__API_BASE_URL || window.location.origin;

function getToken() {
  return "";
}

function setToken(token) {
  return token;
}

function clearToken() {
  return;
}

function q(id) {
  return document.getElementById(id);
}

function ensureToastRoot() {
  if (document.getElementById("toast-root")) return;
  const root = document.createElement("div");
  root.id = "toast-root";
  document.body.appendChild(root);
}

function showToast(message, kind = "error") {
  ensureToastRoot();
  const root = document.getElementById("toast-root");
  const el = document.createElement("div");
  el.className = `toast toast-${kind}`;
  el.textContent = String(message || "Событие");
  root.appendChild(el);
  setTimeout(() => {
    el.classList.add("hide");
    setTimeout(() => el.remove(), 240);
  }, 3200);
}

window.alert = (msg) => showToast(msg, "error");

function extractApiErrorMessage(detail) {
  if (detail === null || detail === undefined) return "";
  if (typeof detail === "string") {
    const value = detail.trim();
    if ((value.startsWith("{") && value.endsWith("}")) || (value.startsWith("[") && value.endsWith("]"))) {
      try {
        return extractApiErrorMessage(JSON.parse(value));
      } catch {
        return value;
      }
    }
    return value;
  }
  if (typeof detail === "number" || typeof detail === "boolean") return String(detail);
  if (Array.isArray(detail)) {
    return detail
      .map((item) => extractApiErrorMessage(item))
      .filter(Boolean)
      .join("; ");
  }
  if (typeof detail === "object") {
    if (typeof detail.message === "string" && detail.message.trim()) return detail.message.trim();
    if (typeof detail.detail === "string" && detail.detail.trim()) return detail.detail.trim();
    if (Array.isArray(detail.loc) && detail.msg) {
      return `${detail.loc.join(".")}: ${detail.msg}`;
    }
    const parts = Object.entries(detail)
      .map(([k, v]) => {
        const msg = extractApiErrorMessage(v);
        return msg ? `${k}: ${msg}` : "";
      })
      .filter(Boolean);
    return parts.join("; ");
  }
  return String(detail);
}

function translateValidationMessage(raw) {
  const text = String(raw || "").trim();
  const lower = text.toLowerCase();

  const fieldMap = {
    name: "название",
    code: "код",
    login: "логин",
    password: "пароль",
    amount: "сумма",
    usages: "количество активаций",
    text: "текст",
    image: "изображение",
    parse_mode: "режим форматирования",
  };

  const match = text.match(/^([a-zA-Z0-9_.\[\]-]+)\s*:\s*(.+)$/);
  let field = "";
  let message = text;

  if (match) {
    const pathParts = match[1].split(".");
    const fieldKey = pathParts[pathParts.length - 1];
    field = fieldMap[fieldKey] || fieldKey;
    message = match[2].trim();
  }

  const msgLower = message.toLowerCase();

  if (msgLower.includes("string should have at least 1 character")) {
    return field ? `Поле «${field}» не может быть пустым` : "Текстовое поле не может быть пустым";
  }
  if (msgLower.includes("field required")) {
    return field ? `Поле «${field}» обязательно для заполнения` : "Не заполнено обязательное поле";
  }
  if (msgLower.includes("string should have at least")) {
    const count = message.match(/at least\s+(\d+)/i)?.[1];
    return field && count ? `Поле «${field}» должно содержать минимум ${count} символа(ов)` : "Слишком короткое значение";
  }
  if (msgLower.includes("string should have at most")) {
    const count = message.match(/at most\s+(\d+)/i)?.[1];
    return field && count ? `Поле «${field}» должно содержать не больше ${count} символов` : "Слишком длинное значение";
  }
  if (msgLower.includes("input should be greater than or equal to")) {
    const count = message.match(/greater than or equal to\s+(\d+)/i)?.[1];
    return field && count ? `Поле «${field}» должно быть не меньше ${count}` : "Значение слишком маленькое";
  }
  if (msgLower.includes("input should be greater than")) {
    const count = message.match(/greater than\s+(\d+)/i)?.[1];
    return field && count ? `Поле «${field}» должно быть больше ${count}` : "Значение слишком маленькое";
  }
  if (msgLower.includes("input should be less than or equal to")) {
    const count = message.match(/less than or equal to\s+(\d+)/i)?.[1];
    return field && count ? `Поле «${field}» должно быть не больше ${count}` : "Значение слишком большое";
  }
  if (msgLower.includes("input should be less than")) {
    const count = message.match(/less than\s+(\d+)/i)?.[1];
    return field && count ? `Поле «${field}» должно быть меньше ${count}` : "Значение слишком большое";
  }
  if (msgLower.includes("input should be a valid integer")) {
    return field ? `Поле «${field}» должно быть целым числом` : "Введите целое число";
  }
  if (msgLower.includes("input should be a valid number")) {
    return field ? `Поле «${field}» должно быть числом` : "Введите число";
  }

  return text;
}

function friendlyAdminErrorMessage(detail, context = {}) {
  const raw = extractApiErrorMessage(detail);
  const s = raw.toLowerCase();
  const path = String(context.path || "");

  if (!raw) return "Произошла ошибка";
  if (s.includes("failed to fetch") || s.includes("networkerror") || s.includes("load failed")) {
    return "Не удалось подключиться к серверу";
  }
  if (s.includes("request entity too large")) {
    return "Файл слишком большой";
  }
  if (s === "not found" || s.includes('"detail":"not found"')) {
    return path.includes("/logs/") ? "Файл лога не найден" : "Запрашиваемый ресурс не найден";
  }
  if (s.includes("log file not found")) {
    return "Файл лога не найден";
  }
  if (s.includes("amount must be > 0")) {
    return "Сумма должна быть больше 0";
  }
  if (s.includes("gb must be > 0")) {
    return "Количество GB должно быть больше 0";
  }
  if (s.includes("promocode") && s.includes("already")) {
    return "Промокод с таким кодом уже существует";
  }
  if (s.includes("promocode") && s.includes("not found")) {
    return "Промокод не найден";
  }
  if (s.includes("unauthorized") || s.includes("invalid token") || s.includes("token expired")) {
    return "Сессия истекла. Войдите заново.";
  }
  if (path.includes("/auth/login") && (
    s.includes("incorrect") ||
    s.includes("invalid credentials") ||
    s.includes("wrong password") ||
    s.includes("wrong login") ||
    s.includes("unauthorized") ||
    s.includes("not found")
  )) {
    return "Неверный логин или пароль";
  }
  if (s.includes("forbidden") || s.includes("access denied")) return "Доступ запрещен";
  if (s.includes("validation") || s.includes("invalid input")) return "Проверьте введенные данные";
  if (raw.includes("body.") || raw.includes("query.") || raw.includes("path.")) {
    return translateValidationMessage(raw);
  }
  return raw;
}

function toErrorMessage(err, fallback = "Произошла ошибка") {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message || fallback;
  return extractApiErrorMessage(err) || fallback;
}

window.addEventListener("error", (event) => {
  const message = toErrorMessage(event.error || event.message, "Неожиданная ошибка на странице");
  showToast(message, "error");
});

window.addEventListener("unhandledrejection", (event) => {
  const message = toErrorMessage(event.reason, "Ошибка выполнения запроса");
  showToast(message, "error");
});

document.addEventListener("click", (e) => {
  const btn = e.target.closest("button");
  if (!btn) return;
  btn.classList.add("tap");
  setTimeout(() => btn.classList.remove("tap"), 170);
});

async function withButtonLoading(button, action) {
  if (!button) return action();
  const prevDisabled = button.disabled;
  button.classList.add("loading");
  button.disabled = true;
  try {
    return await action();
  } finally {
    button.classList.remove("loading");
    button.disabled = prevDisabled;
  }
}

async function hasAdminSession() {
  try {
    const res = await fetch(`${API_BASE}/api/admin/auth/me`, {
      method: "GET",
      credentials: "include",
    });
    if (!res.ok) {
      window.ADMIN_SESSION = null;
      return false;
    }
    window.ADMIN_SESSION = await res.json();
    return true;
  } catch {
    window.ADMIN_SESSION = null;
    return false;
  }
}

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const normalizedPath = path;
  const res = await fetch(`${API_BASE}${normalizedPath}`, { ...options, headers, credentials: "include" });
  const text = await res.text();

  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }

  if (res.status === 401) {
    if (!window.location.pathname.endsWith("/login")) {
      window.location.replace("/admin/login");
    }
    throw new Error(path.includes("/auth/login") ? "Неверный логин или пароль" : "Требуется вход в систему");
  }

  if (!res.ok) {
    const detail = data?.error?.message || data?.detail || data?.message || data;
    let err = friendlyAdminErrorMessage(detail, { path }) || `HTTP ${res.status}`;
    if (res.status === 413 || String(err).toLowerCase().includes("request entity too large")) {
      err = "Файл слишком большой для загрузки. Уменьшите размер изображения или увеличьте лимит client_max_body_size в nginx.";
    }
    showToast(err, "error");
    throw new Error(err);
  }

  return data;
}
