import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  base: "/cabinet/",
  server: {
    port: 5174,
    proxy: { "/api": { target: "http://127.0.0.1:8004", changeOrigin: true } },
  },
  build: { outDir: "../frontend/cabinet_dist", emptyOutDir: true },
});
