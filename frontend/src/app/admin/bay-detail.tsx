/**
 * Per-bay drill-down — `/admin/bays/:code`.
 *
 * Three tabs (plan §5.9):
 *   1. Audit log — keyset-paginated, virtualised list of `BayEventOut`.
 *   2. Telemetry — heatmap + event-type donut + reservation outcomes.
 *   3. Open conflicts — slice of the global admin conflicts list
 *      filtered to this bay (cache shared with `/admin/conflicts`).
 */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import * as Tabs from "@radix-ui/react-tabs";
import { ArrowLeft, Ruler, Timer } from "lucide-react";

import { getBay } from "@/api/bays";
import { listOpenConflicts } from "@/api/conflicts";
import { qk } from "@/api/queryKeys";
import { Card } from "@/components/ui/Card";
import { Spinner } from "@/components/ui/Spinner";
import { BayStateBadge } from "@/components/bay/BayStateBadge";
import { AuditLog } from "@/components/bay/AuditLog";
import { OccupancyHeatmap } from "@/components/chart/OccupancyHeatmap";
import { EventTypeBreakdown } from "@/components/chart/EventTypeBreakdown";
import { ConflictDrawer } from "@/app/admin/conflict-drawer";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/time";

export function BayDetailPage() {
  const { code = "" } = useParams<{ code: string }>();
  const bay = useQuery({
    queryKey: qk.bays.detail(code),
    queryFn: () => getBay(code),
    enabled: Boolean(code),
  });
  const conflicts = useQuery({
    queryKey: qk.conflicts.open(),
    queryFn: listOpenConflicts,
  });
  const openForThisBay = useMemo(
    () => (conflicts.data ?? []).filter((c) => c.bay_code === code),
    [conflicts.data, code],
  );
  const [drawerId, setDrawerId] = useState<string | null>(null);

  if (bay.isLoading) {
    return (
      <div className="grid h-40 place-items-center">
        <Spinner label="Loading bay" />
      </div>
    );
  }
  if (bay.isError || !bay.data) {
    return (
      <Card className="border-danger/30 bg-danger/10 p-4 text-sm text-danger">
        Bay <span className="font-mono">{code}</span> not found.
      </Card>
    );
  }

  return (
    <div className="space-y-6">
      <Link
        to="/admin/grid"
        className="inline-flex items-center gap-1 text-sm text-text-muted hover:text-text"
      >
        <ArrowLeft className="h-4 w-4" aria-hidden="true" /> Back to grid
      </Link>

      <div className="grid gap-6 lg:grid-cols-[280px_1fr]">
        {/* Left rail — current state */}
        <aside className="space-y-3">
          <Card className="p-5">
            <header className="flex items-baseline justify-between">
              <h1 className="font-mono text-3xl font-semibold leading-none">
                {bay.data.code}
              </h1>
              <BayStateBadge state={bay.data.state} variant="compact" />
            </header>
            <p className="mt-1 text-sm text-text-muted">{bay.data.label}</p>
            <dl className="mt-4 grid grid-cols-[auto_1fr] gap-y-2 text-sm">
              <dt className="flex items-center gap-1.5 text-text-muted">
                <Ruler className="h-3.5 w-3.5" aria-hidden="true" /> Distance
              </dt>
              <dd className="text-right font-mono">
                {bay.data.last_distance_cm !== null &&
                bay.data.last_distance_cm !== undefined
                  ? `${bay.data.last_distance_cm.toFixed(1)} cm`
                  : "—"}
              </dd>
              <dt className="flex items-center gap-1.5 text-text-muted">
                <Timer className="h-3.5 w-3.5" aria-hidden="true" /> Last seen
              </dt>
              <dd className="text-right">
                {formatRelative(bay.data.sensor_last_seen_at)}
              </dd>
              {bay.data.current_reservation_id ? (
                <>
                  <dt className="text-text-muted">Reservation</dt>
                  <dd className="text-right font-mono text-xs">
                    {bay.data.current_reservation_id}
                  </dd>
                </>
              ) : null}
            </dl>
          </Card>
        </aside>

        {/* Right pane — tabbed views */}
        <Tabs.Root defaultValue="audit">
          <Tabs.List
            aria-label="Bay detail views"
            className="mb-4 inline-flex rounded-lg border border-border bg-surface p-1"
          >
            <TabTrigger value="audit" label="Audit log" />
            <TabTrigger value="telemetry" label="Telemetry" />
            <TabTrigger
              value="conflicts"
              label="Open conflicts"
              badge={openForThisBay.length}
            />
          </Tabs.List>

          <Tabs.Content value="audit" className="focus:outline-none">
            <AuditLog code={code} />
          </Tabs.Content>

          <Tabs.Content
            value="telemetry"
            className="space-y-4 focus:outline-none"
          >
            <Card className="p-5">
              <header className="mb-3">
                <h2 className="text-base font-semibold">
                  24-hour occupancy heatmap
                </h2>
                <p className="text-xs text-text-muted">
                  Dominant state per hour. Built from `bays/{code}/events`.
                </p>
              </header>
              <OccupancyHeatmap code={code} />
            </Card>
            <Card className="p-5">
              <header className="mb-3">
                <h2 className="text-base font-semibold">
                  Event-type breakdown (last 24 h)
                </h2>
                <p className="text-xs text-text-muted">
                  Donut with an accessible bar-chart fallback below.
                </p>
              </header>
              <EventTypeBreakdown code={code} />
            </Card>
          </Tabs.Content>

          <Tabs.Content
            value="conflicts"
            className="space-y-3 focus:outline-none"
          >
            {openForThisBay.length === 0 ? (
              <p className="rounded-lg border border-border bg-surface-2 p-4 text-sm text-text-muted">
                No open conflicts for this bay.
              </p>
            ) : (
              <ul className="space-y-2">
                {openForThisBay.map((c) => (
                  <li key={c.id}>
                    <button
                      type="button"
                      onClick={() => setDrawerId(c.id)}
                      className="flex w-full items-center justify-between rounded-lg border border-border bg-surface p-4 text-left hover:shadow-card-hover cursor-pointer"
                    >
                      <div>
                        <p>
                          <span
                            className={cn(
                              "inline-flex rounded-full border px-2 py-0.5 text-xs font-medium",
                              c.kind === "strong"
                                ? "border-danger/40 bg-danger/10 text-danger"
                                : "border-warn/40 bg-warn/10 text-warn",
                            )}
                          >
                            {c.kind}
                          </span>
                          {c.recognised_plate ? (
                            <span className="ml-2 font-mono text-sm">
                              {c.recognised_plate}
                            </span>
                          ) : null}
                        </p>
                        <p className="font-mono text-xs text-text-muted">
                          {formatRelative(c.detected_at)}
                        </p>
                      </div>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </Tabs.Content>
        </Tabs.Root>
      </div>

      {drawerId ? (
        <ConflictDrawer
          id={drawerId}
          onClose={() => setDrawerId(null)}
        />
      ) : null}
    </div>
  );
}

function TabTrigger({
  value,
  label,
  badge,
}: {
  value: string;
  label: string;
  badge?: number;
}) {
  return (
    <Tabs.Trigger
      value={value}
      className={cn(
        "inline-flex items-center gap-2 rounded-md px-3 py-1.5 text-sm font-medium",
        "text-text-muted transition-colors duration-150 cursor-pointer",
        "data-[state=active]:bg-surface-2 data-[state=active]:text-text",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
      )}
    >
      {label}
      {badge && badge > 0 ? (
        <span className="inline-flex h-5 min-w-[1.25rem] items-center justify-center rounded-full bg-danger px-1 text-xs font-semibold text-white">
          {badge}
        </span>
      ) : null}
    </Tabs.Trigger>
  );
}
