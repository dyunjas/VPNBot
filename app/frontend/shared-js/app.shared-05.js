async function bootstrap() {
  try {
    setLoader(true, "Загружаем данные...");
    initEvents();
    const initialView = getInitialViewFromUrl();
    const allowedViews = new Set(["home", "plans", "devices", "profile", "settings"]);
    const targetView = allowedViews.has(initialView) ? initialView : "home";

    await Promise.all([
      loadProfile(),
      loadStatus(),
      loadDevices(),
    ]);

    switchView(targetView);
    revealApp();
    setLoader(false);

    if (targetView !== "profile") {
      void loadTransactions().catch(() => {});
    }
    void loadWithdrawals().catch(() => {});
  } catch (e) {
    if (e?.code === "BANNED" || String(e?.message || "").toLowerCase().includes("banned")) {
      showBannedScreen();
      return;
    }
    if (e?.code === "SERVER_UNAVAILABLE") {
      showUnavailableScreen();
      return;
    }
    revealApp();
    setLoader(false);
    toast(e.message || "Ошибка загрузки");
  }
}

if (CAN_BOOT) bootstrap();

