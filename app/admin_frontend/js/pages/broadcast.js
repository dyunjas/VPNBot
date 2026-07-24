let broadcastPollTimer = null;
let currentBroadcastJobId = "";

function broadcastStatusLabel(status) {
  const value = String(status || "queued").toLowerCase();
  if (value === "completed") return statusBadge("approved");
  if (value === "failed") return statusBadge("rejected");
  return statusBadge("pending");
}

function broadcastTextPreview(text) {
  const value = String(text || "").replace(/\s+/g, " ").trim();
  if (!value) return "—";
  return value.length > 96 ? `${value.slice(0, 96)}...` : value;
}

function stopBroadcastPolling() {
  if (broadcastPollTimer) {
    clearTimeout(broadcastPollTimer);
    broadcastPollTimer = null;
  }
}

function renderBroadcastJob(job) {
  const status = String(job?.status || "queued");
  const total = Number(job?.total || 0);
  const processed = Number(job?.processed || 0);
  const success = Number(job?.success || 0);
  const failed = Number(job?.failed || 0);
  const progress = total > 0 ? Math.min(100, Math.round((processed / total) * 100)) : 0;
  const elapsed = Number(job?.elapsed_seconds || 0);
  const failedSamples = Array.isArray(job?.failed_samples) ? job.failed_samples : [];

  const statusBadgeHtml =
    broadcastStatusLabel(status);

  const sampleHtml = failedSamples.length
    ? `<div class="table-wrap">
         <table>
           <thead><tr><th>TG ID</th><th>Ошибка</th></tr></thead>
           <tbody>
             ${failedSamples
               .map((item) => `<tr><td>${safeText(item.tg_id)}</td><td>${safeText(item.error)}</td></tr>`)
               .join("")}
           </tbody>
         </table>
       </div>`
    : "<div class='page-sub'>Нет ошибок доставки</div>";

  return `
    <div class="summary-list">
      <div><span>Статус</span><b>${statusBadgeHtml}</b></div>
      <div><span>Прогресс</span><b>${processed}/${total} (${progress}%)</b></div>
      <div><span>Успешно</span><b>${success}</b></div>
      <div><span>Ошибок</span><b>${failed}</b></div>
      <div><span>Время выполнения</span><b>${elapsed} сек</b></div>
      <div><span>Job ID</span><b class="mono">${safeText(job?.job_id)}</b></div>
    </div>
    ${job?.error ? `<div class="badge danger">Ошибка: ${safeText(job.error)}</div>` : ""}
    ${status === "completed" || status === "failed" ? `<h4>Ошибки доставки (до 30)</h4>${sampleHtml}` : ""}
  `;
}

function renderBroadcastHistory(items) {
  if (!Array.isArray(items) || !items.length) {
    return `<div class="page-sub">История рассылок пока пуста</div>`;
  }

  return `
    <div class="table-wrap">
      <table>
        <thead>
          <tr>
            <th>Создана</th>
            <th>Статус</th>
            <th>Текст</th>
            <th>Получатели</th>
            <th>Успешно</th>
            <th>Ошибки</th>
            <th>Тип</th>
          </tr>
        </thead>
        <tbody>
          ${items
            .map(
              (item) => `
                <tr class="is-clickable-row" data-job-id="${safeText(item.job_id)}">
                  <td>${formatDateTime(item.created_at)}</td>
                  <td>${broadcastStatusLabel(item.status)}</td>
                  <td title="${safeText(item.text || "")}">${safeText(broadcastTextPreview(item.text))}</td>
                  <td>${safeText(item.total)}</td>
                  <td>${safeText(item.success)}</td>
                  <td>${safeText(item.failed)}</td>
                  <td>${item.has_image ? "Текст + изображение" : "Только текст"}</td>
                </tr>
              `,
            )
            .join("")}
        </tbody>
      </table>
    </div>
  `;
}

async function loadBroadcastHistory() {
  const host = q("history");
  if (!host) return;

  try {
    const data = await api("/api/admin/broadcast/history?limit=20");
    const items = data.items || [];
    host.innerHTML = renderBroadcastHistory(items);
    host.querySelectorAll("tr[data-job-id]").forEach((row) => {
      row.addEventListener("click", (event) => {
        event.stopPropagation();
        const jobId = row.getAttribute("data-job-id") || "";
        if (!jobId) return;
        const item = items.find((entry) => String(entry.job_id) === String(jobId)) || {};
        showRowContextMenu(row, [
          {
            label: "Открыть",
            onClick: async () => {
              currentBroadcastJobId = jobId;
              await pollBroadcast(jobId);
            },
          },
        ], {
          title: "Рассылка",
          meta: [
            { label: "Job ID", value: jobId },
            { label: "Статус", html: broadcastStatusLabel(item.status) },
            { label: "Получатели", value: item.total },
            { label: "Успешно", value: item.success },
            { label: "Ошибки", value: item.failed },
            { label: "Тип", value: item.has_image ? "Текст + изображение" : "Только текст" },
            { label: "Создана", value: formatDateTime(item.created_at) },
            { label: "Текст", value: broadcastTextPreview(item.text) },
          ],
        });
      });
    });
  } catch (err) {
    host.innerHTML = `<div class="page-sub">${safeText(err.message || "Не удалось загрузить историю")}</div>`;
  }
}

async function pollBroadcast(jobId) {
  try {
    const data = await api(`/api/admin/broadcast/jobs/${jobId}`);
    const job = data.job || {};
    q("result").innerHTML = renderBroadcastJob(job);

    if (job.status === "completed" || job.status === "failed") {
      stopBroadcastPolling();
      const sendBtn = q("send");
      if (sendBtn) sendBtn.disabled = false;
      await loadBroadcastHistory();
      if (job.status === "completed") showToast("Рассылка завершена", "success");
      return;
    }
  } catch (err) {
    showToast(err.message || "Ошибка получения статуса рассылки", "error");
  }

  broadcastPollTimer = setTimeout(() => pollBroadcast(jobId), 3000);
}

document.addEventListener("DOMContentLoaded", async () => {
  const MAX_IMAGE_SIZE_MB = 8;
  const MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024;

  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "broadcast",
    title: "Рассылки",
    subtitle: "Долгие рассылки выполняются в фоне, статус обновляется автоматически",
    contentHtml: `
      <div class="content-grid">
        <div class="card broadcast-card">
          <h3>Новая рассылка</h3>
          <div class="toolbar broadcast-toolbar">
            <select id="parse_mode">
              <option value="HTML">HTML</option>
              <option value="MarkdownV2">MarkdownV2</option>
            </select>
            <label class="broadcast-check" for="include_banned">
              <input id="include_banned" type="checkbox" />
              <span>Включить забаненных</span>
            </label>
          </div>
          <textarea id="text" class="broadcast-textarea" placeholder="Текст сообщения. Для premium emoji: <tg-emoji emoji-id='...'>⭐</tg-emoji>"></textarea>
          <div class="toolbar broadcast-toolbar broadcast-toolbar--bottom">
            <label class="file-picker" for="image">
              <span class="file-picker__button">Выбрать файл</span>
              <span id="image_name" class="file-picker__name">Файл не выбран</span>
            </label>
            <input id="image" type="file" accept="image/*" hidden />
            <button id="send" class="btn-primary">Запустить рассылку</button>
          </div>
        </div>
        <div class="card broadcast-result-card">
          <h3>Результат</h3>
          <div id="result">Результат появится после запуска</div>
        </div>
      </div>
      <div class="card">
        <div class="dashboard-section-card__head">
          <div>
            <div class="dashboard-section-card__eyebrow">История</div>
            <h3>Последние рассылки</h3>
          </div>
          <button id="reload_history" class="btn-outline-primary" type="button">Обновить</button>
        </div>
        <div id="history">Загрузка...</div>
      </div>
    `,
  });

  q("send").addEventListener("click", async (e) => {
    const text = q("text").value.trim();
    if (!text) return alert("Введите текст");

    const form = new FormData();
    form.set("text", text);
    form.set("parse_mode", q("parse_mode").value);
    form.set("include_banned", String(q("include_banned").checked));

    const file = q("image").files && q("image").files[0] ? q("image").files[0] : null;
    if (file && file.size > MAX_IMAGE_SIZE_BYTES) {
      return alert(`Изображение слишком большое. Максимум: ${MAX_IMAGE_SIZE_MB} МБ.`);
    }
    if (file) form.set("image", file);

    await withButtonLoading(e.currentTarget, async () => {
      stopBroadcastPolling();
      const data = await api("/api/admin/broadcast/upload", {
        method: "POST",
        body: form,
      });

      currentBroadcastJobId = String(data.job_id || "");
      if (!currentBroadcastJobId) throw new Error("Не удалось создать задачу рассылки");

      q("result").innerHTML = `
        <div class="summary-list">
          <div><span>Статус</span><b>${broadcastStatusLabel("pending")}</b></div>
          <div><span>Job ID</span><b class="mono">${safeText(currentBroadcastJobId)}</b></div>
        </div>
        <div class="page-sub">Рассылка запущена. Обновление статистики каждые 3 секунды.</div>
      `;
      q("send").disabled = true;
      await loadBroadcastHistory();
      pollBroadcast(currentBroadcastJobId);
    }).catch((err) => alert(err.message));
  });

  q("image")?.addEventListener("change", () => {
    const file = q("image").files && q("image").files[0] ? q("image").files[0] : null;
    q("image_name").textContent = file ? file.name : "Файл не выбран";
  });

  q("reload_history")?.addEventListener("click", async (e) => {
    await withButtonLoading(e.currentTarget, async () => {
      await loadBroadcastHistory();
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
    await loadBroadcastHistory();
  } catch (e) {
    alert(e.message);
  }
});
