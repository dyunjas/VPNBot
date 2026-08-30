import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

const adminDevPrefix = () => ({
  name: "admin-dev-prefix",
  configureServer(server) {
    server.middlewares.use((req, _res, next) => {
      if (req.url === "/admin" || req.url === "/admin/") req.url = "/";
      else if (req.url?.startsWith("/admin/")) req.url = req.url.slice("/admin".length);
      next();
    });
  },
});

export default defineConfig({
  plugins: [adminDevPrefix(), react(), tailwindcss()],
  base: "/admin/",
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8004", changeOrigin: true },
    },
  },
  build: { outDir: "../admin_frontend/dist", emptyOutDir: true },
});
