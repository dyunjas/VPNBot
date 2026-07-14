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
  el.textContent = String(message || "РЎРѕР±С‹С‚РёРµ");
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

function translateValidationMessage(raw) {
  const text = String(raw || "").trim();
  const lower = text.toLowerCase();

  const fieldMap = {
    name: "РЅР°Р·РІР°РЅРёРµ",
    code: "РєРѕРґ",
    login: "Р»РѕРіРёРЅ",
    password: "РїР°СЂРѕР»СЊ",
    amount: "СЃСѓРјРјР°",
    usages: "РєРѕР»РёС‡РµСЃС‚РІРѕ Р°РєС‚РёРІР°С†РёР№",
    text: "С‚РµРєСЃС‚",
    image: "РёР·РѕР±СЂР°Р¶РµРЅРёРµ",
    parse_mode: "СЂРµР¶РёРј С„РѕСЂРјР°С‚РёСЂРѕРІР°РЅРёСЏ",
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
    return field ? `РџРѕР»Рµ В«${field}В» РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РїСѓСЃС‚С‹Рј` : "РўРµРєСЃС‚РѕРІРѕРµ РїРѕР»Рµ РЅРµ РјРѕР¶РµС‚ Р±С‹С‚СЊ РїСѓСЃС‚С‹Рј";
  }
  if (msgLower.includes("field required")) {
    return field ? `РџРѕР»Рµ В«${field}В» РѕР±СЏР·Р°С‚РµР»СЊРЅРѕ РґР»СЏ Р·Р°РїРѕР»РЅРµРЅРёСЏ` : "РќРµ Р·Р°РїРѕР»РЅРµРЅРѕ РѕР±СЏР·Р°С‚РµР»СЊРЅРѕРµ РїРѕР»Рµ";
  }
  if (msgLower.includes("string should have at least")) {
    const count = message.match(/at least\s+(\d+)/i)?.[1];
    return field && count ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ СЃРѕРґРµСЂР¶Р°С‚СЊ РјРёРЅРёРјСѓРј ${count} СЃРёРјРІРѕР»Р°(РѕРІ)` : "РЎР»РёС€РєРѕРј РєРѕСЂРѕС‚РєРѕРµ Р·РЅР°С‡РµРЅРёРµ";
  }
  if (msgLower.includes("string should have at most")) {
    const count = message.match(/at most\s+(\d+)/i)?.[1];
    return field && count ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ СЃРѕРґРµСЂР¶Р°С‚СЊ РЅРµ Р±РѕР»СЊС€Рµ ${count} СЃРёРјРІРѕР»РѕРІ` : "РЎР»РёС€РєРѕРј РґР»РёРЅРЅРѕРµ Р·РЅР°С‡РµРЅРёРµ";
  }
  if (msgLower.includes("input should be greater than")) {
    const count = message.match(/greater than\s+(\d+)/i)?.[1];
    return field && count ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ Р±РѕР»СЊС€Рµ ${count}` : "Р—РЅР°С‡РµРЅРёРµ СЃР»РёС€РєРѕРј РјР°Р»РµРЅСЊРєРѕРµ";
  }
  if (msgLower.includes("input should be greater than or equal to")) {
    const count = message.match(/greater than or equal to\s+(\d+)/i)?.[1];
    return field && count ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ РЅРµ РјРµРЅСЊС€Рµ ${count}` : "Р—РЅР°С‡РµРЅРёРµ СЃР»РёС€РєРѕРј РјР°Р»РµРЅСЊРєРѕРµ";
  }
  if (msgLower.includes("input should be less than")) {
    const count = message.match(/less than\s+(\d+)/i)?.[1];
    return field && count ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ РјРµРЅСЊС€Рµ ${count}` : "Р—РЅР°С‡РµРЅРёРµ СЃР»РёС€РєРѕРј Р±РѕР»СЊС€РѕРµ";
  }
  if (msgLower.includes("input should be less than or equal to")) {
    const count = message.match(/less than or equal to\s+(\d+)/i)?.[1];
    return field && count ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ РЅРµ Р±РѕР»СЊС€Рµ ${count}` : "Р—РЅР°С‡РµРЅРёРµ СЃР»РёС€РєРѕРј Р±РѕР»СЊС€РѕРµ";
  }
  if (msgLower.includes("input should be a valid integer")) {
    return field ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ С†РµР»С‹Рј С‡РёСЃР»РѕРј` : "Р’РІРµРґРёС‚Рµ С†РµР»РѕРµ С‡РёСЃР»Рѕ";
  }
  if (msgLower.includes("input should be a valid number")) {
    return field ? `РџРѕР»Рµ В«${field}В» РґРѕР»Р¶РЅРѕ Р±С‹С‚СЊ С‡РёСЃР»РѕРј` : "Р’РІРµРґРёС‚Рµ С‡РёСЃР»Рѕ";
  }

  return text;
}

function friendlyAdminErrorMessage(detail, context = {}) {
  const raw = extractApiErrorMessage(detail);
  const s = raw.toLowerCase();
  const path = String(context.path || "");

  if (!raw) return "РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР°";
  if (s.includes("failed to fetch") || s.includes("networkerror") || s.includes("load failed")) {
    return "РќРµ СѓРґР°Р»РѕСЃСЊ РїРѕРґРєР»СЋС‡РёС‚СЊСЃСЏ Рє СЃРµСЂРІРµСЂСѓ";
  }
  if (s.includes("request entity too large")) {
    return "Р¤Р°Р№Р» СЃР»РёС€РєРѕРј Р±РѕР»СЊС€РѕР№";
  }
  if (s.includes("unauthorized") || s.includes("invalid token") || s.includes("token expired")) {
    return "РЎРµСЃСЃРёСЏ РёСЃС‚РµРєР»Р°. Р’РѕР№РґРёС‚Рµ Р·Р°РЅРѕРІРѕ.";
  }
  if (path.includes("/auth/login") && (
    s.includes("incorrect") ||
    s.includes("invalid credentials") ||
    s.includes("wrong password") ||
    s.includes("wrong login") ||
    s.includes("unauthorized") ||
    s.includes("not found")
  )) {
    return "РќРµРІРµСЂРЅС‹Р№ Р»РѕРіРёРЅ РёР»Рё РїР°СЂРѕР»СЊ";
  }
  if (s.includes("forbidden") || s.includes("access denied")) return "Р”РѕСЃС‚СѓРї Р·Р°РїСЂРµС‰С‘РЅ";
  if (s.includes("validation") || s.includes("invalid input")) return "РџСЂРѕРІРµСЂСЊС‚Рµ РІРІРµРґС‘РЅРЅС‹Рµ РґР°РЅРЅС‹Рµ";
  if (raw.includes("body.") || raw.includes("query.") || raw.includes("path.")) {
    return translateValidationMessage(raw);
  }
  return raw;
}

function toErrorMessage(err, fallback = "РџСЂРѕРёР·РѕС€Р»Р° РѕС€РёР±РєР°") {
  if (!err) return fallback;
  if (typeof err === "string") return err;
  if (err instanceof Error) return err.message || fallback;
  return extractApiErrorMessage(err) || fallback;
}

window.addEventListener("error", (event) => {
  const message = toErrorMessage(event.error || event.message, "РќРµРѕР¶РёРґР°РЅРЅР°СЏ РѕС€РёР±РєР° РЅР° СЃС‚СЂР°РЅРёС†Рµ");
  showToast(message, "error");
});

window.addEventListener("unhandledrejection", (event) => {
  const message = toErrorMessage(event.reason, "РћС€РёР±РєР° РІС‹РїРѕР»РЅРµРЅРёСЏ Р·Р°РїСЂРѕСЃР°");
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
    return res.ok;
  } catch {
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
      err = "Р¤Р°Р№Р» СЃР»РёС€РєРѕРј Р±РѕР»СЊС€РѕР№ РґР»СЏ Р·Р°РіСЂСѓР·РєРё. РЈРјРµРЅСЊС€РёС‚Рµ СЂР°Р·РјРµСЂ РёР·РѕР±СЂР°Р¶РµРЅРёСЏ РёР»Рё СѓРІРµР»РёС‡СЊС‚Рµ Р»РёРјРёС‚ client_max_body_size РІ nginx.";
    }
    showToast(err, "error");
    throw new Error(err);
  }

  return data;
}
