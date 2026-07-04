const SHARED_APP_PARTS = [
  "/miniapp/shared-js/app.shared-01.js",
  "/miniapp/shared-js/app.shared-02.js",
  "/miniapp/shared-js/app.shared-03.js",
  "/miniapp/shared-js/app.shared-04.js",
  "/miniapp/shared-js/app.shared-05.js",
];

if (!window.__sharedAppPartsLoaded) {
  window.__sharedAppPartsLoaded = true;

  (async () => {
    for (const src of SHARED_APP_PARTS) {
      await new Promise((resolve, reject) => {
        const script = document.createElement("script");
        script.src = src;
        script.defer = true;
        script.onload = resolve;
        script.onerror = () => reject(new Error(`Failed to load ${src}`));
        document.head.appendChild(script);
      });
    }
  })().catch((error) => {
    console.error(error);
  });
}
