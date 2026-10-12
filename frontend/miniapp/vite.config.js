import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
export default defineConfig({resolve:{dedupe:["react","react-dom","lucide-react"]},plugins:[react(),tailwindcss()],base:"/miniapp/",build:{outDir: "../build/miniapp",emptyOutDir:true,assetsDir:"react-assets"},server:{port:5175,proxy:{"/api":{target:"http://127.0.0.1:8004",changeOrigin:true}}}});
