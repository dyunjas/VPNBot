function formatBytes(bytes) {
  const value = Number(bytes || 0);
  if (!Number.isFinite(value) || value <= 0) return "0 B";
  const units = ["B", "KB", "MB", "GB"];
  let idx = 0;
  let size = value;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  const rounded = idx === 0 ? String(Math.round(size)) : size.toFixed(2);
  return `${rounded} ${units[idx]}`;
}

function openLogDownload(filename) {
  const encoded = encodeURIComponent(filename);
  fetch(`/api/admin/logs/${encoded}/download`, {
    credentials: "include",
  })
    .then(async (res) => {
      if (res.status === 401) {
        window.location.replace("/admin/login");
        return null;
      }
      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `HTTP ${res.status}`);
      }
      return res.blob();
    })
    .then((blob) => {
      if (!blob) return;
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    })
    .catch((err) => {
      alert(toErrorMessage(err, "Не удалось скачать лог"));
    });
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "logs",
    title: "Логи",
    subtitle: "Файлы бизнес-логов: пополнения, подписки, рефералка и выводы",
    contentHtml: `
      <div class="toolbar">
        <button id="refresh" class="btn-primary">Обновить список</button>
      </div>
      <div class="card">
        <div class="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Файл</th><th>Размер</th><th>Обновлен</th><th>Действие</th>
              </tr>
            </thead>
            <tbody id="tbody"></tbody>
          </table>
        </div>
      </div>
    `,
  });

  async function loadLogs() {
    const data = await api("/api/admin/logs?limit=200");
    const items = data.items || [];
    const tbody = q("tbody");
    tbody.innerHTML = "";

    if (!items.length) {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td colspan="4">Файлы логов не найдены</td>`;
      tbody.appendChild(tr);
      return;
    }

    items.forEach((item) => {
      const updatedAt = item.updated_at ? new Date(item.updated_at * 1000).toLocaleString("ru-RU") : "—";
      const tr = document.createElement("tr");
      tr.innerHTML = `
        <td class="mono">${safeText(item.filename)}</td>
        <td>${formatBytes(item.size_bytes)}</td>
        <td>${updatedAt}</td>
        <td><button class="btn-primary js-download" data-file="${encodeURIComponent(item.filename)}">Скачать</button></td>
      `;
      tbody.appendChild(tr);
    });

    tbody.querySelectorAll(".js-download").forEach((btn) => {
      btn.addEventListener("click", () => {
        const encoded = btn.getAttribute("data-file") || "";
        const filename = decodeURIComponent(encoded);
        openLogDownload(filename);
      });
    });
  }

  q("refresh").addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, loadLogs).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    await loadLogs();
  } catch (e) {
    alert(e.message);
  }
});
