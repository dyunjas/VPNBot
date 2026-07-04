const SCRIPT_PARTS = [
  "/miniapp/js/features/features-01.js",
  "/miniapp/js/features/features-02.js",
];

if (!window.features_loaded) {
  window.features_loaded = true;

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
  })().catch((error) => {
    console.error(error);
  });
}
