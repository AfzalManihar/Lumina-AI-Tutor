/// <reference types="vitest" />
import { defineConfig, loadEnv } from "vite";
import react from "@vitejs/plugin-react";

// The dev server proxies /api to the FastAPI backend so the httpOnly refresh cookie is same-origin.
// Override the target with VITE_BACKEND_URL (shell variable or frontend/.env).
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, ".", "");
  return {
    plugins: [react()],
    server: {
      port: 5173,
      proxy: { "/api": { target: env.VITE_BACKEND_URL || "http://127.0.0.1:8000", changeOrigin: false } },
    },
    test: { environment: "jsdom", globals: true, setupFiles: ["./src/test/setup.ts"], css: false },
  };
});
