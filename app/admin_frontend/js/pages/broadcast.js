document.addEventListener("DOMContentLoaded", async () => {
  const MAX_IMAGE_SIZE_MB = 8;
  const MAX_IMAGE_SIZE_BYTES = MAX_IMAGE_SIZE_MB * 1024 * 1024;

  ensureAuthOrRedirect();
  renderShell({
    activeKey: "broadcast",
    title: "Рассылки",
    subtitle: "Загрузка изображения и HTML-текста (поддержка <tg-emoji>)",
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
          <textarea id="text" placeholder="Текст сообщения. Для премиум emoji: <tg-emoji emoji-id='...'>⭐</tg-emoji>"></textarea>
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
      const data = await api("/admin-api/broadcast/upload", {
        method: "POST",
        body: form,
      });
      q("result").innerHTML = `
        <div>${statusBadge("ok")} Рассылка завершена</div>
        <div>Всего получателей: <b>${safeText(data.total)}</b></div>
        <div>Успешно: <b>${safeText(data.success)}</b></div>
        <div>Ошибок: <b>${safeText(data.failed)}</b></div>
      `;
    }).catch((err) => alert(err.message));
  });

  try {
    await renderSessionInfo();
  } catch (e) {
    alert(e.message);
  }
});
