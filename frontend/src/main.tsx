/**
 * Application bootstrap.
 *
 * Wires React 18 concurrent root, the TanStack Query client, the router
 * (`@/app/root`), the auth provider, and the global Radix Toast viewport.
 * Anything that needs to live for the lifetime of the tab is mounted here.
 */
import React from "react";
import ReactDOM from "react-dom/client";
import { RouterProvider } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import "@/index.css";
import { router } from "@/app/root";
import { AuthProvider } from "@/auth/AuthProvider";
import { Toaster } from "@/components/ui/Toaster";

/**
 * Query client configuration.
 *
 * - `staleTime: 30s` keeps the bay grid and reservation lists from
 *   re-fetching on every focus while WebSocket events are the primary
 *   source of freshness (see plan §8).
 * - `retry: 2` on queries: tolerates transient network blips during the
 *   live demo without masking real backend errors.
 * - Mutations never retry — every mutation in this app is either
 *   idempotent server-side (cancel, check-in) or has side-effects we
 *   must not duplicate (booking creates a deposit hold).
 */
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      gcTime: 5 * 60_000,
      retry: 2,
      refetchOnWindowFocus: true,
    },
    mutations: {
      retry: 0,
    },
  },
});

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Missing #root mount node in index.html");
}

ReactDOM.createRoot(rootEl).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <AuthProvider>
        <RouterProvider router={router} />
        <Toaster />
      </AuthProvider>
    </QueryClientProvider>
  </React.StrictMode>,
);
