import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({resolve:{dedupe:["react","react-dom","lucide-react"]},
  plugins: [react()],
  base: "/cabinet/",
  server: {
    port: 5174,
    proxy: { "/api": { target: "http://127.0.0.1:8004", changeOrigin: true } },
  },
  build: { outDir: "../build/cabinet", emptyOutDir: true },
});
