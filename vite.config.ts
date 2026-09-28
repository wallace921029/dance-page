import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import path from "path";
import tailwindcss from "@tailwindcss/vite";

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  // 同时运行多个开发服务器（如隔离测试环境）时，用 VITE_CACHE_DIR 指定各自的依赖缓存目录，
  // 否则后启动的服务器重新打包依赖会覆盖前一个正在使用的文件，浏览器里会出现两份 React
  cacheDir: process.env.VITE_CACHE_DIR ?? "node_modules/.vite",
  optimizeDeps: {
    // 启动时扫描全部源码，一次性预打包所有依赖（包括还没有页面用到的 shadcn 组件依赖）。
    // 否则开发中第一次用到新组件时 Vite 会临时重新打包，已打开的页面可能同时加载两份 React
    entries: ["index.html", "src/**/*.{ts,tsx}"],
  },
  resolve: {
    alias: {
      "@": path.resolve(import.meta.dirname, "./src"),
    },
  },
  server: {
    proxy: {
      // scripts/dev.sh 会在后端改用其他端口时通过 API_PROXY_TARGET 传入实际地址
      "/api": process.env.API_PROXY_TARGET ?? "http://127.0.0.1:8000",
    },
  },
});
