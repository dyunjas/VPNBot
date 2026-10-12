import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({resolve:{dedupe:["react","react-dom","lucide-react"]},
  plugins: [react(), tailwindcss()],
  base: "/admin/",
  server: {
    port: 5173,
    proxy: {
      "/api": { target: "http://127.0.0.1:8004", changeOrigin: true },
    },
  },
  build: { outDir: "../build/admin", emptyOutDir: true },
});
