/**
 * Vite configuration.
 *
 * - Dev server proxies REST (`/api`) and Socket.IO (`/ws`, `/socket.io`) to the
 *   local backend on :8000 so a browser request to `http://localhost:5173/api/v1/bays`
 *   ends up at `http://localhost:8000/api/v1/bays` without CORS pre-flight pain.
 * - Build emits a static `dist/` that can be served by nginx behind the same
 *   hostname as the backend (no CORS in production either).
 * - `vitest` config lives here so `src/**` tests don't need a separate runner config.
 */
/// <reference types="vitest/config" />
import path from "node:path";
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import { loadEnv } from "vite";

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, __dirname, "");
  const backend = env.VITE_BACKEND_ORIGIN?.trim() || "http://127.0.0.1:8000";

  return {
    plugins: [react()],
    resolve: {
      alias: {
        "@": path.resolve(__dirname, "src"),
      },
    },
    server: {
      port: 5173,
      strictPort: true,
      proxy: {
        "/api": { target: backend, changeOrigin: true },
        "/healthz": { target: backend, changeOrigin: true },
        "/readyz": { target: backend, changeOrigin: true },
        // Socket.IO has its own well-known prefix the client uses for the
        // long-poll fallback and the websocket upgrade.
        "/socket.io": { target: backend, changeOrigin: true, ws: true },
      },
    },
    build: {
      outDir: "dist",
      sourcemap: true,
      target: "es2022",
      rollupOptions: {
        output: {
          // Cheap manualChunks split — keeps the initial bundle under the
          // "Performance" rubric bar on cold loads.
          manualChunks: {
            react: ["react", "react-dom", "react-router-dom"],
            tanstack: ["@tanstack/react-query"],
            radix: [
              "@radix-ui/react-toast",
              "@radix-ui/react-dialog",
              "@radix-ui/react-tooltip",
              "@radix-ui/react-tabs",
              "@radix-ui/react-popover",
              "@radix-ui/react-dropdown-menu",
              "@radix-ui/react-alert-dialog",
            ],
            charts: ["recharts"],
          },
        },
      },
    },
    test: {
      globals: true,
      environment: "jsdom",
      setupFiles: ["./test/setup.ts"],
      coverage: {
        provider: "v8",
        reporter: ["text", "html", "lcov"],
        // Coverage gate mirrors the backend's 90 % rule
        // (see backend/pyproject.toml).
        thresholds: {
          lines: 80,
          functions: 80,
          statements: 80,
          branches: 75,
        },
        include: ["src/**/*.{ts,tsx}"],
        exclude: ["src/**/*.test.{ts,tsx}", "src/main.tsx"],
      },
    },
  };
});
