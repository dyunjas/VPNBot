const CACHE_KEY = "lunet.telegram.launch";
const MAX_AGE_MS = 60 * 60 * 1000;
let waiting;

export function readTelegramData() {
  const sdk = window.Telegram?.WebApp?.initData;
  const hash = new URLSearchParams(location.hash.replace(/^#/, "")).get("tgWebAppData");
  const current = sdk || hash || "";
  if (current) {
    try { sessionStorage.setItem(CACHE_KEY, JSON.stringify({data:current,savedAt:Date.now()})); } catch {}
    return current;
  }
  try {
    const cached = JSON.parse(sessionStorage.getItem(CACHE_KEY) || "null");
    if (cached?.data && Date.now() - cached.savedAt < MAX_AGE_MS) return cached.data;
    sessionStorage.removeItem(CACHE_KEY);
  } catch {}
  return "";
}

export function waitForTelegramData(timeout = 15000) {
  const current = readTelegramData();
  if (current) return Promise.resolve(current);
  if (!waiting) waiting = new Promise((resolve,reject)=>{
    const started = Date.now();
    const timer = setInterval(()=>{
      const data = readTelegramData();
      if (data) { clearInterval(timer); resolve(data); }
      else if (Date.now() - started >= timeout) {
        clearInterval(timer);
        reject(Object.assign(new Error("Не удалось получить данные Telegram. Откройте мини-приложение заново через бота Lunet."),{code:"telegram_missing"}));
      }
    },100);
  }).finally(()=>{waiting=null});
  return waiting;
}

// Capture signed launch data before the Telegram SDK or a challenge redirect
// replaces the hash. This data is always validated by the backend.
readTelegramData();

export async function api(path, body = {}) {
  const initData = await waitForTelegramData();
  const response = await fetch(path,{method:"POST",headers:{"Content-Type":"application/json",Accept:"application/json"},credentials:"same-origin",body:JSON.stringify({...body,initData})});
  const isJSON = /application\/json/i.test(response.headers.get("content-type") || "");
  if (!isJSON) {
    // Never replay POSTs: a payment or purchase could already have completed.
    throw new Error("Проверка защиты ещё не завершена. Завершите её и нажмите «Повторить».");
  }
  const data = await response.json();
  if (!response.ok) {
    const missing = /init.?data.*missing/i.test(String(data.detail));
    const error = new Error(missing ? "Telegram не передал данные входа. Откройте приложение заново из бота." : typeof data.detail === "string" ? data.detail : "Не удалось выполнить запрос. Попробуйте ещё раз.");
    if (response.status===403&&data.detail==="banned")error.code="banned";
    if (missing)error.code="telegram_missing";
    throw error;
  }
  return data;
}
