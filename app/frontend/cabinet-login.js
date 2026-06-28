const apiBase = window.__API_BASE_URL || window.location.origin;

function q(id) {
  return document.getElementById(id);
}

const statusEl = q("status");
const tabEmail = q("tab_email");
const tabTelegram = q("tab_telegram");
const formEmail = q("form_email");
const formTelegram = q("form_telegram");
const emailVerifyBlock = q("email_verify_block");
const tgVerifyBlock = q("tg_verify_block");

function setStatus(text, type = "") {
  if (!statusEl) return;
  statusEl.textContent = String(text || "");
  statusEl.classList.remove("success", "error");
  if (type) statusEl.classList.add(type);
}

function mapErrorMessage(err) {
  const raw = String(err || "").toLowerCase();
  if (!raw) return "Не удалось выполнить запрос.";
  if (raw.includes("invalid credentials") || raw.includes("wrong password") || raw.includes("wrong login") || raw.includes("неверный")) {
    return "Неверный логин или код.";
  }
  if (raw.includes("http 404") || raw.includes("not found")) return "Пользователь не найден.";
  if (raw.includes("invalid or expired code")) return "Неверный или просроченный код.";
  if (raw.includes("invalid code") || raw.includes("code expired") || raw.includes("code is invalid")) return "Неверный или просроченный код.";
  if (raw.includes("unauthorized")) return "Сессия недействительна. Войдите повторно.";
  if (raw.includes("smtp")) return "Проблема с отправкой письма. Проверьте SMTP на сервере.";
  if (raw.includes("http 503")) return "Сервис временно недоступен.";
  if (raw.includes("failed to fetch") || raw.includes("networkerror") || raw.includes("load failed")) return "Не удалось подключиться к серверу.";
  return String(err || "Не удалось выполнить запрос.");
}

async function post(path, body) {
  const res = await fetch(`${apiBase}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body || {}),
  });
  const data = await res.json().catch(() => ({}));

  if (!res.ok) {
    const detail = data?.detail || data?.message || data?.error || `HTTP ${res.status}`;
    const detailText = String(detail).toLowerCase();
    if (res.status === 400 && detailText.includes("email")) throw new Error("Введите корректный email.");
    if (res.status === 400 && detailText.includes("telegram")) throw new Error("Введите корректный Telegram ID.");
    if (res.status === 401) throw new Error("Неверный логин или код.");
    throw new Error(detail);
  }

  return data;
}

function resetSteps() {
  emailVerifyBlock.classList.add("is-hidden");
  tgVerifyBlock.classList.add("is-hidden");
  q("email_code").value = "";
  q("tg_code").value = "";
}

function setMode(mode) {
  const emailMode = mode === "email";
  tabEmail.classList.toggle("is-active", emailMode);
  tabTelegram.classList.toggle("is-active", !emailMode);
  tabEmail.setAttribute("aria-selected", emailMode ? "true" : "false");
  tabTelegram.setAttribute("aria-selected", emailMode ? "false" : "true");
  formEmail.classList.toggle("is-hidden", !emailMode);
  formTelegram.classList.toggle("is-hidden", emailMode);
  setStatus("");
}

async function sendEmailCode() {
  const email = (q("email").value || "").trim();
  if (!email) throw new Error("Введите email.");
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) throw new Error("Введите корректный email.");
  await post("/cabinet-api/auth/send-email-code", { email });
  emailVerifyBlock.classList.remove("is-hidden");
  q("email_code").focus();
  setStatus("Код отправлен на email.", "success");
}

async function verifyEmail() {
  const email = (q("email").value || "").trim();
  const code = (q("email_code").value || "").trim();
  if (!email || !code) throw new Error("Заполните email и код.");
  const data = await post("/cabinet-api/auth/verify-code", { channel: "email", email, code });
  localStorage.setItem("cabinet_access_token", data.access_token);
  window.location.replace("/cabinet");
}

async function sendTelegramCode() {
  const tgRaw = (q("tg_id").value || "").trim();
  const tgId = Number(tgRaw);
  if (!Number.isFinite(tgId)) throw new Error("Введите корректный Telegram ID.");
  await post("/cabinet-api/auth/send-telegram-code", { tg_id: tgId });
  tgVerifyBlock.classList.remove("is-hidden");
  q("tg_code").focus();
  setStatus("Код отправлен в Telegram.", "success");
}

async function verifyTelegram() {
  const tgRaw = (q("tg_id").value || "").trim();
  const code = (q("tg_code").value || "").trim();
  const tgId = Number(tgRaw);
  if (!Number.isFinite(tgId) || !code) throw new Error("Заполните Telegram ID и код.");
  const data = await post("/cabinet-api/auth/verify-code", { channel: "telegram", tg_id: tgId, code });
  localStorage.setItem("cabinet_access_token", data.access_token);
  window.location.replace("/cabinet");
}

async function runAction(action) {
  try {
    setStatus("");
    await action();
  } catch (e) {
    setStatus(mapErrorMessage(e?.message || e), "error");
  }
}

tabEmail?.addEventListener("click", () => setMode("email"));
tabTelegram?.addEventListener("click", () => setMode("telegram"));
q("send_email_code")?.addEventListener("click", () => runAction(sendEmailCode));
q("verify_email")?.addEventListener("click", () => runAction(verifyEmail));
q("send_tg_code")?.addEventListener("click", () => runAction(sendTelegramCode));
q("verify_tg")?.addEventListener("click", () => runAction(verifyTelegram));

resetSteps();
setMode("email");
