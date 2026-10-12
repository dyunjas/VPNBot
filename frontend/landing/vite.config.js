import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({resolve:{dedupe:["react","react-dom","lucide-react"]},
  plugins: [react()],
  server: { port: 5176, proxy: { "/api/public": "http://127.0.0.1:8004", "/api/auth/session": "http://127.0.0.1:8004" } },
  build: { outDir: "../build/landing", emptyOutDir: true }
});
