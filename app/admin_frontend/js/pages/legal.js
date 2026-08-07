const legalState = {
  activeKey: "terms",
  documents: [],
  current: null,
};

function legalIcon(name) {
  if (typeof tablerIcon === "function") return tablerIcon(name);
  return "";
}

function renderLegalTabs() {
  const host = q("legal_tabs");
  if (!host) return;
  host.innerHTML = legalState.documents
    .map((item) => `
      <button class="legal-tab ${item.key === legalState.activeKey ? "is-active" : ""}" data-legal-key="${item.key}" type="button">
        ${legalIcon(item.key === "privacy" ? "eye" : item.key === "offer" ? "external" : "info")}
        <span>${safeText(item.title)}</span>
      </button>
    `)
    .join("");

  host.querySelectorAll("[data-legal-key]").forEach((button) => {
    button.addEventListener("click", async () => {
      legalState.activeKey = button.dataset.legalKey || "terms";
      renderLegalTabs();
      await loadLegalDocument();
    });
  });
}

async function loadLegalList() {
  const data = await api("/api/admin/legal");
  legalState.documents = data.items || [];
  renderLegalTabs();
}

async function loadLegalDocument() {
  const editor = q("legal_editor");
  const title = q("legal_doc_title");
  if (editor) {
    editor.setAttribute("contenteditable", "false");
    editor.textContent = "Загрузка...";
  }

  const data = await api(`/api/admin/legal/${legalState.activeKey}`);
  legalState.current = data;
  if (title) title.textContent = data.title || "Документ";
  if (editor) {
    editor.innerHTML = data.content || data.html || "";
    editor.setAttribute("contenteditable", "true");
    updateLegalStats();
  }
}

function updateLegalStats() {
  const editor = q("legal_editor");
  const chars = q("legal_chars");
  const lines = q("legal_lines");
  const value = editor?.innerText || "";
  if (chars) chars.textContent = `${value.length.toLocaleString("ru-RU")} символов`;
  if (lines) lines.textContent = `${value.split(/\r?\n/).length.toLocaleString("ru-RU")} строк`;
}

async function saveLegalDocument(button) {
  const editor = q("legal_editor");
  const html = editor?.innerHTML || "";
  await withButtonLoading(button, async () => {
    await api(`/api/admin/legal/${legalState.activeKey}`, {
      method: "PUT",
      body: JSON.stringify({ html }),
    });
    showToast("Документ сохранен", "success");
    await loadLegalDocument();
  }).catch((error) => alert(error.message));
}

document.addEventListener("DOMContentLoaded", async () => {
  if (!(await ensureAuthOrRedirect())) return;
  renderShell({
    activeKey: "legal",
    title: "Документы",
    subtitle: "Редактирование offer, privacy и terms",
    contentHtml: `
      <div class="page-shell legal-editor-page">
        <div class="card legal-editor-card">
          <div class="admin-section-head">
            <div>
              <div class="dashboard-section-card__eyebrow">Legal</div>
              <h3 id="legal_doc_title">Документ</h3>
              <div class="section-title">Редактируйте текст документа. Простые HTML-теги для форматирования поддерживаются.</div>
            </div>
            <div class="toolbar toolbar--compact legal-editor-actions">
              <button id="legal_reload" type="button">Обновить</button>
              <button id="legal_save" class="btn-primary" type="button">Сохранить</button>
            </div>
          </div>
          <div id="legal_tabs" class="legal-tabs"></div>
          <div id="legal_editor" class="legal-editor" contenteditable="true" spellcheck="true"></div>
          <div class="legal-editor-meta">
            <span id="legal_chars">0 символов</span>
            <span id="legal_lines">0 строк</span>
          </div>
        </div>
      </div>
    `,
  });

  q("legal_editor")?.addEventListener("input", updateLegalStats);
  q("legal_reload")?.addEventListener("click", async (event) => {
    await withButtonLoading(event.currentTarget, loadLegalDocument).catch((error) => alert(error.message));
  });
  q("legal_save")?.addEventListener("click", async (event) => saveLegalDocument(event.currentTarget));

  await loadLegalList();
  await loadLegalDocument();
});
