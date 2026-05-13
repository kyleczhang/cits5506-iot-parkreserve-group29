/**
 * Public landing page.
 *
 * - Marketing hero (concise; this is an academic prototype, not a
 *   product website).
 * - Live bay strip — polls `GET /api/v1/bays` every 5 s while the tab
 *   is visible (Page Visibility API stops the poll on hidden tabs).
 *   We do NOT open a Socket.IO connection here per plan §5.1.
 */
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ArrowRight, ParkingCircle, RadioTower, ShieldCheck } from "lucide-react";

import { listBays } from "@/api/bays";
import { qk } from "@/api/queryKeys";
import { useAuth } from "@/auth/AuthProvider";
import { BayTile } from "@/components/bay/BayTile";
import { Button } from "@/components/ui/Button";
import { Spinner } from "@/components/ui/Spinner";

export function Landing() {
  const { status, user } = useAuth();
  const bays = useQuery({
    queryKey: qk.bays.list(),
    queryFn: listBays,
    refetchInterval: (q) =>
      typeof document !== "undefined" && document.visibilityState === "hidden"
        ? false
        : 5_000,
  });

  return (
    <div className="min-h-screen bg-bg text-text">
      <header className="border-b border-border bg-surface">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <Link
            to="/"
            className="inline-flex items-center gap-2 text-text"
            aria-label="ParkReserve home"
          >
            <ParkingCircle className="h-6 w-6 text-brand" aria-hidden="true" />
            <span className="text-lg font-semibold">ParkReserve</span>
          </Link>
          <nav className="flex items-center gap-3">
            {status === "authenticated" ? (
              <Button
                onClick={() => {
                  window.location.assign(
                    user?.role === "admin" ? "/admin/grid" : "/app",
                  );
                }}
                trailingIcon={<ArrowRight className="h-4 w-4" />}
              >
                Open dashboard
              </Button>
            ) : (
              <>
                <Link to="/login">
                  <Button variant="ghost">Sign in</Button>
                </Link>
                <Link to="/register">
                  <Button trailingIcon={<ArrowRight className="h-4 w-4" />}>
                    Get started
                  </Button>
                </Link>
              </>
            )}
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-12">
        <section className="grid items-center gap-10 md:grid-cols-[1.1fr_1fr]">
          <div>
            <p className="inline-flex items-center gap-2 rounded-full bg-brand/10 px-3 py-1 text-xs font-medium text-brand">
              <RadioTower aria-hidden="true" className="h-3.5 w-3.5" />
              Live IoT mirror
            </p>
            <h1 className="mt-4 text-3xl font-semibold tracking-tight md:text-4xl">
              Reserve a paid-facility parking bay,{" "}
              <span className="text-brand">honour it, or pay the penalty.</span>
            </h1>
            <p className="mt-4 max-w-prose text-text-muted">
              ParkReserve mirrors the per-bay state from a Raspberry Pi gateway
              + ESP32-CAM sensors. Bind a licence plate, book a bay, drive in —
              automatic LPR check-in handles the rest. Late cancels, no-shows
              and weak conflicts are settled financially from a deposit held at
              booking; strong-evidence conflicts refund you in full.
            </p>
            <div className="mt-6 flex flex-wrap gap-3">
              <Link to="/register">
                <Button size="lg" trailingIcon={<ArrowRight className="h-4 w-4" />}>
                  Create a driver account
                </Button>
              </Link>
              <Link to="/login">
                <Button size="lg" variant="secondary">
                  I already have an account
                </Button>
              </Link>
            </div>
            <p className="mt-6 flex items-start gap-2 text-xs text-text-muted">
              <ShieldCheck aria-hidden="true" className="mt-0.5 h-4 w-4 shrink-0" />
              Mock payment only — no real bank network is contacted in this
              prototype.
            </p>
          </div>

          <div className="rounded-2xl border border-border bg-surface-2 p-4 shadow-card">
            <header className="flex items-baseline justify-between px-2 pb-3">
              <h2 className="text-sm font-semibold text-text">Live bay status</h2>
              <span className="text-xs text-text-muted">
                Polled every 5 s
              </span>
            </header>
            {bays.isLoading ? (
              <div className="grid h-40 place-items-center">
                <Spinner label="Loading bay status" />
              </div>
            ) : bays.isError ? (
              <p className="rounded-lg bg-danger/10 p-3 text-sm text-danger">
                Couldn&apos;t load bay status. Is the backend running on{" "}
                <code className="font-mono">localhost:8000</code>?
              </p>
            ) : (
              <ul className="grid gap-3 sm:grid-cols-2 md:grid-cols-1 lg:grid-cols-2">
                {bays.data?.map((bay) => (
                  <li key={bay.code}>
                    <BayTile bay={bay} />
                  </li>
                ))}
              </ul>
            )}
          </div>
        </section>
      </main>

      <footer className="border-t border-border bg-surface">
        <div className="mx-auto max-w-6xl px-6 py-6 text-xs text-text-muted">
          ParkReserve · CITS 5506 Group 29 · Mock-payment prototype.
        </div>
      </footer>
    </div>
  );
}
