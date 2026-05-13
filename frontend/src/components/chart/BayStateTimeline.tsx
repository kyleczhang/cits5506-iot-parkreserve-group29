/**
 * 24-hour bay-state ribbon (stacked area).
 *
 * Drawn from `GET /api/v1/bays/{code}/events` aggregated by hour, then
 * summed across the bays passed in. Provides an accessible data-table
 * fallback in a `<details>` block (plan §7 / §3.4).
 */
import { useQueries } from "@tanstack/react-query";
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { listBayEvents } from "@/api/bays";
import { qk } from "@/api/queryKeys";
import { Spinner } from "@/components/ui/Spinner";
import { STATE_PALETTE } from "@/lib/theme";
import { bucketStateByHour, type HourTally } from "@/lib/buckets";

interface Props {
  codes: ReadonlyArray<string>;
}

const SERIES: Array<{ key: keyof Omit<HourTally, "hour">; label: string; colour: string }> = [
  { key: "available", label: "Available", colour: STATE_PALETTE.available },
  { key: "reserved", label: "Reserved", colour: STATE_PALETTE.reserved },
  { key: "pending_check_in", label: "Pending", colour: STATE_PALETTE.pending },
  { key: "occupied", label: "Occupied", colour: STATE_PALETTE.occupied },
  { key: "reserved_checked_in", label: "Checked in", colour: STATE_PALETTE.occupied },
  { key: "conflict", label: "Conflict", colour: STATE_PALETTE.conflict },
  { key: "offline", label: "Offline", colour: STATE_PALETTE.offline },
];

export function BayStateTimeline({ codes }: Props) {
  const results = useQueries({
    queries: codes.map((code) => ({
      queryKey: qk.bays.events(code, "24h"),
      queryFn: () => listBayEvents(code, { limit: 200 }),
      staleTime: 60_000,
    })),
  });

  const allLoaded = results.length > 0 && results.every((r) => !r.isLoading);
  if (!allLoaded) {
    return (
      <div className="grid h-40 place-items-center">
        <Spinner label="Loading 24-hour history" />
      </div>
    );
  }

  // Sum each bay's bucketed seconds-per-state into a single ribbon.
  const merged: HourTally[] = Array.from({ length: 24 }, (_, i) => ({
    hour: i,
    available: 0,
    reserved: 0,
    pending_check_in: 0,
    occupied: 0,
    reserved_checked_in: 0,
    conflict: 0,
    offline: 0,
  }));
  for (const r of results) {
    const buckets = bucketStateByHour(r.data ?? []);
    for (let i = 0; i < 24; i++) {
      const m = merged[i]!;
      const b = buckets[i]!;
      m.hour = b.hour;
      m.available += b.available;
      m.reserved += b.reserved;
      m.pending_check_in += b.pending_check_in;
      m.occupied += b.occupied;
      m.reserved_checked_in += b.reserved_checked_in;
      m.conflict += b.conflict;
      m.offline += b.offline;
    }
  }

  return (
    <>
      <div
        className="h-56"
        role="img"
        aria-label="Stacked-area chart of bay-state share across the last 24 hours"
      >
        <ResponsiveContainer width="100%" height="100%">
          <AreaChart data={merged}>
            <XAxis
              dataKey="hour"
              tickFormatter={(h) => `${h}:00`}
              stroke="currentColor"
              tick={{ fill: "currentColor", opacity: 0.7, fontSize: 12 }}
            />
            <YAxis hide />
            <Tooltip
              contentStyle={{
                background: "rgb(var(--surface))",
                border: "1px solid rgb(var(--border))",
                color: "rgb(var(--text))",
                borderRadius: 8,
              }}
              labelFormatter={(h) => `${h}:00`}
              formatter={(value: number, name: string) => [
                `${Math.round(value / 60)} min`,
                name,
              ]}
            />
            {SERIES.map((s) => (
              <Area
                key={s.key}
                type="step"
                dataKey={s.key}
                stackId="1"
                stroke={s.colour}
                fill={s.colour}
                fillOpacity={0.85}
                name={s.label}
                isAnimationActive={false}
              />
            ))}
          </AreaChart>
        </ResponsiveContainer>
      </div>

      {/* Data-table fallback for accessibility. */}
      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-text-muted">
          Show as data table
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                <th className="border-b border-border px-2 py-1 text-left">
                  Hour
                </th>
                {SERIES.map((s) => (
                  <th
                    key={s.key}
                    className="border-b border-border px-2 py-1 text-right"
                  >
                    {s.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {merged.map((row) => (
                <tr key={row.hour}>
                  <td className="px-2 py-1 font-mono">{row.hour}:00</td>
                  {SERIES.map((s) => (
                    <td key={s.key} className="px-2 py-1 text-right font-mono">
                      {Math.round(row[s.key] / 60)}m
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </>
  );
}
