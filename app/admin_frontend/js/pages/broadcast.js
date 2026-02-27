let broadcastPollTimer = null;
let currentBroadcastJobId = "";

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
    status === "completed"
      ? statusBadge("approved")
      : status === "failed"
        ? statusBadge("rejected")
        : statusBadge("pending");

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

async function pollBroadcast(jobId) {
  try {
    const data = await api(`/admin-api/broadcast/jobs/${jobId}`);
    const job = data.job || {};
    q("result").innerHTML = renderBroadcastJob(job);

    if (job.status === "completed" || job.status === "failed") {
      stopBroadcastPolling();
      const sendBtn = q("send");
      if (sendBtn) sendBtn.disabled = false;
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

  ensureAuthOrRedirect();
  renderShell({
    activeKey: "broadcast",
    title: "Рассылки",
    subtitle: "Долгие рассылки выполняются в фоне, статус обновляется автоматически",
    contentHtml: `
      <div class="content-grid">
        <div class="card">
          <h3>Новая рассылка</h3>
          <div class="toolbar">
            <select id="parse_mode">
              <option value="HTML">HTML</option>
              <option value="MarkdownV2">MarkdownV2</option>
            </select>
            <label class="inline-field"><input id="include_banned" type="checkbox" /> Включить забаненных</label>
          </div>
          <textarea id="text" placeholder="Текст сообщения. Для premium emoji: <tg-emoji emoji-id='...'>⭐</tg-emoji>"></textarea>
          <div class="toolbar">
            <input id="image" type="file" accept="image/*" />
            <button id="send" class="btn-primary">Запустить рассылку</button>
          </div>
        </div>
        <div class="card">
          <h3>Результат</h3>
          <div id="result">Результат появится после запуска</div>
        </div>
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
      const data = await api("/admin-api/broadcast/upload", {
        method: "POST",
        body: form,
      });

      currentBroadcastJobId = String(data.job_id || "");
      if (!currentBroadcastJobId) throw new Error("Не удалось создать задачу рассылки");

      q("result").innerHTML = `
        <div class="summary-list">
          <div><span>Статус</span><b>${statusBadge("pending")}</b></div>
          <div><span>Job ID</span><b class="mono">${safeText(currentBroadcastJobId)}</b></div>
        </div>
        <div class="page-sub">Рассылка запущена. Обновление статистики каждые 3 секунды.</div>
      `;
      q("send").disabled = true;
      pollBroadcast(currentBroadcastJobId);
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
  } catch (e) {
    alert(e.message);
  }
});

