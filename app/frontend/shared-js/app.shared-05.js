async function bootstrap() {
  try {
    setLoader(true, "Загружаем кабинет...");
    initEvents();
    const initialView = getInitialViewFromUrl();
    const allowedViews = new Set(["home", "plans", "devices", "profile", "referral", "settings"]);
    const targetView = allowedViews.has(initialView) ? initialView : "home";

    if (IS_MINIAPP_PATH && state.initData) {
      await authorizeCabinetWithTelegram();
    }

    await Promise.all([
      loadProfile(),
      loadStatus(),
      loadDevices(),
    ]);

    switchView(targetView);
    revealApp();
    setLoader(false);

    if (!IS_MINIAPP_PATH && targetView !== "profile") {
      void loadTransactions().catch(() => {});
    }
    if (!IS_MINIAPP_PATH) void loadWithdrawals().catch(() => {});
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
