const API_BASE = window.__ADMIN_API_BASE_URL || window.__API_BASE_URL || window.location.origin;

function getToken() {
  return localStorage.getItem("admin_access_token") || "";
}

function setToken(token) {
  localStorage.setItem("admin_access_token", token);
}

function clearToken() {
  localStorage.removeItem("admin_access_token");
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
  if (typeof detail === "string") return detail.trim();
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
  if (s.includes("forbidden") || s.includes("access denied")) return "Доступ запрещён";
  if (s.includes("validation") || s.includes("invalid input")) return "Проверьте введённые данные";
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

async function api(path, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (!(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  const token = getToken();
  if (token) {
    headers.Authorization = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, { ...options, headers });
  const text = await res.text();

  let data = {};
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }

  if (res.status === 401) {
    clearToken();
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
