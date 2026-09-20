import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const backend = "http://127.0.0.1:8765";

export default defineConfig({
  base: "/",
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/api": { target: backend, changeOrigin: false },
      "/media": { target: backend, changeOrigin: false },
      "/ws": { target: backend.replace("http", "ws"), ws: true, changeOrigin: false },
    },
  },
  build: {
    outDir: "dist",
    assetsDir: "assets",
    emptyOutDir: true,
    sourcemap: false,
  },
});
