const SCRIPT_PARTS = [
  "/admin/js/pages/dashboard/dashboard-01.js?v=6",
  "/admin/js/pages/dashboard/dashboard-02.js?v=8",
];

if (!window.dashboard_loaded) {
  window.dashboard_loaded = true;

  (async () => {
    for (const src of SCRIPT_PARTS) {
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = src;
        script.defer = true;
        script.onload = resolve;
        script.onerror = () => reject(new Error(`Failed to load ${src}`));
        document.head.appendChild(script);
      });
    }

    if (typeof window.initDashboardPage === "function") {
      if (!window.dashboard_page_initialized) {
        window.dashboard_page_initialized = true;
        await window.initDashboardPage();
      }
    } else {
      throw new Error("Dashboard bootstrap failed: initDashboardPage is not defined");
    }
  })().catch((error) => {
    console.error(error);
    if (typeof showToast === "function") {
      showToast(error?.message || "Не удалось загрузить обзор", "error");
    }
  });
}
