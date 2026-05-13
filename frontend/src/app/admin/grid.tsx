/**
 * Admin live grid — `/admin/grid`.
 *
 * Data flow per plan §5.8:
 *   - `GET /api/v1/bays` for tile state, refetched on `bay.updated`
 *     (debounced 250 ms inside the realtime bus).
 *   - One `GET /api/v1/bays/{code}/events` per bay for the 30-min
 *     sparkline. Fanned out in parallel; cache shared with the
 *     drill-down at `qk.bays.events(code, "30min")`.
 *   - Telemetry strip at the top reads from the 24 h slice shared
 *     between this page and the drill-down telemetry tab.
 */
import { useQueries, useQuery } from "@tanstack/react-query";
import { useNavigate } from "react-router-dom";

import { listBayEvents, listBays } from "@/api/bays";
import { qk } from "@/api/queryKeys";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { BayStateBadge } from "@/components/bay/BayStateBadge";
import { BaySparkline } from "@/components/bay/BaySparkline";
import { BayStateTimeline } from "@/components/chart/BayStateTimeline";
import { formatRelative } from "@/lib/time";
import { cn } from "@/lib/cn";
import type { BayOut } from "@/schemas/bay";

export function AdminGrid() {
  const navigate = useNavigate();
  const bays = useQuery({
    queryKey: qk.bays.list(),
    queryFn: listBays,
  });

  return (
    <div className="space-y-6">
      <header className="flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Live grid</h1>
        <span className="text-sm text-text-muted">
          Updates over WebSocket · debounced 250 ms
        </span>
      </header>

      {/* KPI strip */}
      <KpiStrip bays={bays.data ?? []} />

      {/* Telemetry ribbon */}
      <Card className="p-5">
        <header className="mb-3 flex items-baseline justify-between">
          <h2 className="text-base font-semibold tracking-tight">
            Bay state over the last 24 hours
          </h2>
          <span className="text-xs text-text-muted">
            Stacked share across all bays
          </span>
        </header>
        <BayStateTimeline codes={(bays.data ?? []).map((b) => b.code)} />
      </Card>

      {/* Tile grid */}
      {bays.isLoading ? (
        <div className="grid h-40 place-items-center">
          <Spinner label="Loading bays" />
        </div>
      ) : bays.isError ? (
        <Card className="p-4 text-sm text-danger">Couldn&apos;t load bays.</Card>
      ) : (
        <ul className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
          {bays.data?.map((bay) => (
            <li key={bay.code}>
              <OpsBayTile bay={bay} onSelect={(code) => navigate(`/admin/bays/${code}`)} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------

function KpiStrip({ bays }: { bays: ReadonlyArray<BayOut> }) {
  const total = bays.length;
  const available = bays.filter((b) => b.state === "available").length;
  const busy = bays.filter(
    (b) =>
      b.state === "occupied" ||
      b.state === "reserved" ||
      b.state === "reserved_checked_in" ||
      b.state === "pending_check_in",
  ).length;
  const offline = bays.filter((b) => b.state === "offline").length;
  const conflict = bays.filter((b) => b.state === "conflict").length;

  return (
    <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <KpiCard label="Bays online" value={total - offline} sub={`of ${total} total`} />
      <KpiCard label="Available" value={available} tone="success" />
      <KpiCard label="Reserved / occupied" value={busy} tone="warn" />
      <KpiCard
        label="Conflicts"
        value={conflict}
        tone={conflict > 0 ? "danger" : "muted"}
      />
    </ul>
  );
}

function KpiCard({
  label,
  value,
  sub,
  tone = "muted",
}: {
  label: string;
  value: number;
  sub?: string;
  tone?: "muted" | "success" | "warn" | "danger";
}) {
  const toneClass = {
    muted: "text-text",
    success: "text-success",
    warn: "text-warn",
    danger: "text-danger",
  }[tone];
  return (
    <li>
      <Card className="p-4">
        <p className="text-xs uppercase tracking-wider text-text-muted">
          {label}
        </p>
        <p className={cn("mt-2 font-mono text-3xl font-semibold", toneClass)}>
          {value}
        </p>
        {sub ? <p className="mt-1 text-xs text-text-muted">{sub}</p> : null}
      </Card>
    </li>
  );
}

// ---------------------------------------------------------------------------

function OpsBayTile({
  bay,
  onSelect,
}: {
  bay: BayOut;
  onSelect: (code: string) => void;
}) {
  // Per-bay events fan-out (plan §5.8). Cached at `qk.bays.events(code, "30min")`.
  const events = useQueries({
    queries: [
      {
        queryKey: qk.bays.events(bay.code, "30min"),
        queryFn: () => listBayEvents(bay.code, { limit: 50 }),
        staleTime: 60_000,
      },
    ],
  });
  const evRow = events[0];
  const ring =
    bay.state === "conflict"
      ? "ring-2 ring-state-conflict/60"
      : bay.state === "pending_check_in"
        ? "ring-2 ring-state-pending/60"
        : "";
  return (
    <Card
      interactive
      onClick={() => onSelect(bay.code)}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect(bay.code);
        }
      }}
      tabIndex={0}
      role="button"
      aria-label={`Open bay ${bay.code}`}
      className={cn("space-y-3 p-4", ring)}
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-2xl font-semibold leading-none">
            {bay.code}
          </p>
          <p className="mt-1 text-sm text-text-muted">{bay.label}</p>
        </div>
        <BayStateBadge state={bay.state} variant="compact" />
      </header>

      <BaySparkline events={evRow?.data ?? []} currentState={bay.state} />

      <dl className="grid grid-cols-2 gap-y-1 text-xs">
        <dt className="text-text-muted">Distance</dt>
        <dd className="text-right font-mono">
          {bay.last_distance_cm !== null && bay.last_distance_cm !== undefined
            ? `${bay.last_distance_cm.toFixed(1)} cm`
            : "—"}
        </dd>
        <dt className="text-text-muted">Last seen</dt>
        <dd className="text-right">
          {formatRelative(bay.sensor_last_seen_at)}
        </dd>
        {bay.current_reservation_id ? (
          <>
            <dt className="text-text-muted">Reservation</dt>
            <dd className="text-right font-mono">
              {bay.current_reservation_id.slice(0, 8)}…
            </dd>
          </>
        ) : null}
      </dl>
    </Card>
  );
}
