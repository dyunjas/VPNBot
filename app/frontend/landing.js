function randomToken(size = 24) {
  const chars = "abcdefghijklmnopqrstuvwxyz0123456789";
  let out = "";
  for (let i = 0; i < size; i += 1) out += chars[Math.floor(Math.random() * chars.length)];
  return out;
}

function toFlagEmoji(countryCode) {
  const code = String(countryCode || "").trim().toUpperCase();
  if (!/^[A-Z]{2}$/.test(code)) return "";
  const base = 127397;
  return String.fromCodePoint(...code.split("").map((c) => base + c.charCodeAt(0)));
}

function parseLocation(rawName) {
  const raw = String(rawName || "").trim();
  if (!raw) return { label: "Локация", code: "", flag: "🌐" };

  // Берем первые две латинские буквы в начале строки как код страны (ru/us/de...)
  // и отрезаем их из отображаемого названия.
  const m = raw.match(/^([^A-Za-z]*)([A-Za-z]{2})([\s._-]*)(.*)$/);
  let code = "";
  let label = raw;
  if (m) {
    code = String(m[2] || "").toUpperCase();
    label = String(m[4] || "").trim();
  }

  label = label.replace(/^[\s._-]+/, "").trim();
  if (!label) {
    label = raw.replace(/^([^A-Za-z]*)([A-Za-z]{2})/, "").replace(/^[\s._-]+/, "").trim() || raw;
  }

  return {
    label,
    code,
    flag: toFlagEmoji(code) || "🌐",
  };
}

function selectLocation(rawName) {
  const selectedEl = document.getElementById("location-selected");
  const chips = Array.from(document.querySelectorAll(".chip"));
  chips.forEach((c) => c.classList.toggle("active", c.dataset.raw === rawName));

  const parsed = parseLocation(rawName);
  const shown = `${parsed.flag} ${parsed.label}`;
  selectedEl.textContent = `Выбрана локация: ${shown}. Сервер готов к подключению в боте.`;
}

async function loadLocations() {
  const wrap = document.getElementById("locations");
  const selectedEl = document.getElementById("location-selected");
  try {
    const res = await fetch("/landing-data");
    const data = await res.json();
    const locations = Array.isArray(data.locations) ? data.locations : [];
    if (!locations.length) throw new Error("no locations");

    wrap.innerHTML = "";
    locations.forEach((rawName, idx) => {
      const parsed = parseLocation(rawName);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = `chip${idx === 0 ? " active" : ""}`;
      btn.dataset.raw = rawName;
      btn.textContent = `${parsed.flag} ${parsed.label}`;
      btn.addEventListener("click", () => selectLocation(rawName));
      wrap.appendChild(btn);
    });

    selectLocation(locations[0]);
  } catch {
    selectedEl.textContent = "Не удалось загрузить локации. Обновите страницу или попробуйте позже.";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const keyEl = document.getElementById("sub-key");
  if (keyEl) keyEl.textContent = `https://lunetpn/sub/${randomToken(18)}`;
  loadLocations();
});
