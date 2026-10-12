self.addEventListener("install", () => self.skipWaiting());
self.addEventListener("activate", (event) => event.waitUntil((async () => {
  for (const key of await caches.keys()) if (key.startsWith("lunet-cabinet-shell-")) await caches.delete(key);
  await self.clients.claim();
})()));
// Private pages/API remain network-only; never replay a cached authenticated response.
