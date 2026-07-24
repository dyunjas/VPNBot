async function api(path, body = {}) {
  const useCabinet = IS_CABINET_PATH && !HAS_AUTH_INITDATA;
  const targetPath = useCabinet
    ? path.replace(/^\/api\/mini/, "/api").replace(/^\/api\/cabinet/, "/api").replace(/^\/mini/, "/api")
    : path.replace(/^\/mini/, "/api");
  const headers = { "Content-Type": "application/json" };
  const payload = useCabinet ? body : { initData: state.initData, ...body };
  const cabinetToken = getCabinetToken();
  if (useCabinet && cabinetToken) headers.Authorization = `Bearer ${cabinetToken}`;
  let res = await fetch(`${BACKEND_URL}${targetPath}`, {
    method: "POST",
    headers,
    credentials: useCabinet ? "include" : "same-origin",
    body: JSON.stringify(payload),
  });

  if (useCabinet && res.status === 401) {
    const refreshRes = await fetch(`${BACKEND_URL}/api/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refreshRes.ok) {
      const refreshData = await refreshRes.json().catch(() => ({}));
      const nextToken = String(refreshData.access_token || "");
      if (nextToken) {
        localStorage.setItem(CABINET_TOKEN_KEY, nextToken);
        headers.Authorization = `Bearer ${nextToken}`;
        res = await fetch(`${BACKEND_URL}${targetPath}`, {
          method: "POST",
          headers,
          credentials: "include",
          body: JSON.stringify(payload),
        });
      }
    }
  }

  let data = {};
  try {
    data = await res.json();
  } catch {
    data = {};
  }

  if (!res.ok) {
    const rawDetail = normalizeErrorDetail(data.detail || data.error || `HTTP ${res.status}`);
    const rawStr = String(rawDetail || "").toLowerCase();
    if (rawStr.includes("недостаточно средств") || rawStr.includes("insufficient balance")) {
      throw new Error("Недостаточно средств на балансе. Пополните баланс.");
    }
    if (res.status >= 500) {
      const err = new Error("\u0421\u0435\u0440\u0432\u0435\u0440 \u043d\u0435 \u0434\u043e\u0441\u0442\u0443\u043f\u0435\u043d. \u0418\u0434\u0443\u0442 \u0442\u0435\u0445\u043d\u0438\u0447\u0435\u0441\u043a\u0438\u0435 \u0440\u0430\u0431\u043e\u0442\u044b.");
      err.code = "SERVER_UNAVAILABLE";
      showUnavailableScreen();
      throw err;
    }
    if (res.status === 403 && rawStr.includes("banned")) {
      const err = new Error("BANNED");
      err.code = "BANNED";
      throw err;
    }
    throw new Error(friendlyErrorMessage(rawDetail));
  }
  return data;
}

function switchView(view) {
  const current = document.querySelector(".view.view--active");
  const next = $(`view-${view}`);
  if (!next || next === current) return;

  current?.classList.remove("view--active", "view-enter", "view-leave");
  next.classList.add("view--active");

  document.querySelectorAll(".tab").forEach((tab) => tab.classList.toggle("tab--active", tab.dataset.tab === view));
  document.querySelectorAll(".side-link[data-tab]").forEach((tab) => tab.classList.toggle("is-active", tab.dataset.tab === view));

  if (view === "plans") loadPlans();
  if (view === "devices") loadDevices();
  if (view === "profile" && !IS_MINIAPP_PATH) loadTransactions();
  if (view === "referral") {
    loadReferral();
    if (!IS_MINIAPP_PATH) loadWithdrawals();
  }
}

function setTextSkeleton(ids, loading) {
  ids.forEach((id) => {
    const el = $(id);
    if (!el) return;
    el.classList.toggle("text-skeleton", loading);
  });
}

function renderDeviceSkeleton(count = 1) {
  return Array.from({ length: count }, () => `
    <div class="item device-card device-card--skeleton" aria-hidden="true">
      <div class="device-card__icon skeleton-block"></div>
      <div class="device-card__body">
        <div class="skeleton-line skeleton-line--title"></div>
        <div class="skeleton-line skeleton-line--meta"></div>
        <div class="skeleton-line skeleton-line--meta skeleton-line--short"></div>
      </div>
      <div class="skeleton-pill"></div>
    </div>
  `).join("");
}

function formatDate(iso) {
  if (!iso) return "-";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? "-" : d.toLocaleString("ru-RU");
}

function calcDaysLeft(endIso) {
  if (!endIso) return 0;
  const end = new Date(endIso);
  if (Number.isNaN(end.getTime())) return 0;
  const msLeft = end.getTime() - Date.now();
  if (msLeft <= 0) return 0;
  return Math.ceil(msLeft / (24 * 60 * 60 * 1000));
}

function formatGbValue(bytes) {
  const num = Number(bytes || 0);
  if (!Number.isFinite(num) || num <= 0) return "0 GB";
  return `${(num / (1024 ** 3)).toFixed(1)} GB`;
}

function formatTrafficPercent(part, total) {
  const totalNum = Number(total || 0);
  const partNum = Number(part || 0);
  if (!Number.isFinite(totalNum) || totalNum <= 0) return 0;
  const pct = Math.max(0, Math.min(100, (partNum / totalNum) * 100));
  return Math.round(pct);
}

function toNonNegativeInt(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return 0;
  return Math.max(0, Math.trunc(n));
}

function formatDevicesCounter(sub, remnawave) {
  const limit = toNonNegativeInt(sub?.devices_limit ?? remnawave?.hwidDeviceLimit);
  const usedFromSub = sub?.devices_used;
  const leftFromSub = sub?.devices_left;
  let used = 0;

  if (usedFromSub !== undefined && usedFromSub !== null) {
    used = toNonNegativeInt(usedFromSub);
  } else if (leftFromSub !== undefined && leftFromSub !== null && limit > 0) {
    used = Math.max(limit - toNonNegativeInt(leftFromSub), 0);
  }

  return {
    used,
    limit,
    text: limit > 0 ? `${used}/${limit}` : `${used}/∞`,
  };
}

function statusBadge(status) {
  const s = String(status || "").toLowerCase();
  if (s === "approved") return '<span class="badge badge--ok">Подтвержден</span>';
  if (s === "rejected") return '<span class="badge badge--bad">Отклонен</span>';
  if (s === "pending") return '<span class="badge badge--wait">Ожидает</span>';
  return '<span class="badge">Неизвестно</span>';
}

async function loadProfile() {
  setTextSkeleton(["home-name", "home-id", "home-balance", "ref-balance", "ref-invited"], true);
  const data = await api("/api/profile");
  const user = data.user || {};
  const ref = data.referral || {};
  const tgUser = tg?.initDataUnsafe?.user;

  const name = [tgUser?.first_name, tgUser?.last_name].filter(Boolean).join(" ") || user.username || "Пользователь";
  const photo = tgUser?.photo_url || FALLBACK_AVATAR;

  state.userId = user.tg_id;

  $("home-avatar").src = photo;
  $("home-name").textContent = name;
  $("home-id").textContent = `ID: ${user.tg_id || "-"}`;
  $("home-id-copy")?.setAttribute("data-id", String(user.tg_id || ""));
  $("home-balance").textContent = `${user.balance || 0} ₽`;

  $("ref-balance").textContent = `${ref.balance || 0} ₽`;
  $("ref-invited").textContent = String(ref.invited_count || 0);
  setTextSkeleton(["home-name", "home-id", "home-balance", "ref-balance", "ref-invited"], false);
}

async function loadStatus() {
  setTextSkeleton([
    "sub-title",
    "sub-days-left",
    "sub-end-date",
    "sub-traffic-text",
  ], true);
  const data = await api("/api/status");
  const sub = data.subscription || {};
  const remnawave = data.remnawave || {};
  const limitBytes = Number(remnawave.trafficLimitBytes || 0);
  const usedBytes = Number(remnawave.usedTrafficBytes || 0);
  const usedPercent = formatTrafficPercent(usedBytes, limitBytes);
  const progressFill = document.getElementById("sub-progress-fill");

  if (!data.has_subscription) {
    $("sub-title").textContent = "Подписка неактивна";
    $("sub-days-left").textContent = "0";
    $("sub-end-date").textContent = "—";
    $("sub-traffic-text").textContent = "—";
    $("sub-badge").textContent = "Неактивна";
    progressFill?.style.setProperty("width", "0%");
    const subLinkWrap = $("sub-link-wrap");
    if (subLinkWrap) subLinkWrap.style.display = "none";
    if ($("sub-link")) $("sub-link").textContent = "Ссылка синхронизируется...";
    if ($("quick-connect-state")) $("quick-connect-state").textContent = "Подписка недоступна";
    state.subscriptionUrl = null;
    setTextSkeleton([
      "sub-title",
      "sub-days-left",
      "sub-end-date",
      "sub-traffic-text",
    ], false);
    return;
  }

  const daysLeft = calcDaysLeft(sub.current_period_end);

  $("sub-title").textContent = "Подписка активна";
  $("sub-days-left").textContent = String(daysLeft);
  $("sub-end-date").textContent = formatDate(sub.current_period_end);
  $("sub-traffic-text").textContent = `${formatGbValue(usedBytes)} / ${formatGbValue(limitBytes)}`;
  $("sub-badge").textContent = "Активна";
  progressFill?.style.setProperty("width", `${usedPercent}%`);

  state.subscriptionUrl = data.subscription_url || null;
  const subLinkWrap = $("sub-link-wrap");
  if (subLinkWrap) subLinkWrap.style.display = "";
  if ($("sub-link")) $("sub-link").textContent = state.subscriptionUrl || "Ссылка синхронизируется...";
  if ($("quick-connect-state")) $("quick-connect-state").textContent = "VPN отключен";
  setTextSkeleton([
    "sub-title",
    "sub-days-left",
    "sub-end-date",
    "sub-traffic-text",
  ], false);
}

async function loadReferral() {
  const data = await api("/api/referral/info");
  state.businessSettings = {
    ...(state.businessSettings || {}),
    ...(data.business_settings || {}),
  };
  state.referralUrl = data.referral_url || null;
  $("ref-link").textContent = state.referralUrl || "Ссылка недоступна";

  const r = data.referral || {};
  $("ref-extra").textContent = `Процент: ${r.percent || 0}% | Приглашено: ${r.invited_count || 0} | Баланс: ${r.balance || 0} ₽`;
}
