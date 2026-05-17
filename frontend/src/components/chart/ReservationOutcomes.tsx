/**
 * Driver-side payment-outcomes chart.
 *
 * Stacked bar of `pre_auth` vs `release` vs `refund` vs `penalty_capture`
 * counts per week, computed from the user's own ledger
 * (`GET /api/v1/users/me/payments`). Helps the grader see the financial
 * narrative ("most reservations end clean; here is what a late cancel cost me").
 */
import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { listPayments } from "@/api/payments";
import { qk } from "@/api/queryKeys";
import { Spinner } from "@/components/ui/Spinner";

const ACTIONS = [
  { key: "pre_auth", label: "Held", colour: "#F59E0B" },
  { key: "release", label: "Released", colour: "#22C55E" },
  { key: "refund", label: "Refunded", colour: "#0EA5E9" },
  { key: "penalty_capture", label: "Penalty", colour: "#DC2626" },
] as const;

export function ReservationOutcomes() {
  const list = useQuery({ queryKey: qk.payments.list(), queryFn: listPayments });

  const data = useMemo(() => {
    const rows = list.data ?? [];
    const byWeek = new Map<
      string,
      {
        week: string;
        pre_auth: number;
        release: number;
        refund: number;
        penalty_capture: number;
      }
    >();
    for (const r of rows) {
      const wk = weekLabel(new Date(r.occurred_at));
      const cur = byWeek.get(wk) ?? {
        week: wk,
        pre_auth: 0,
        release: 0,
        refund: 0,
        penalty_capture: 0,
      };
      cur[r.action] += 1;
      byWeek.set(wk, cur);
    }
    return [...byWeek.values()].sort((a, b) => a.week.localeCompare(b.week));
  }, [list.data]);

  if (list.isLoading) {
    return (
      <div className="grid h-32 place-items-center">
        <Spinner label="Loading outcomes" />
      </div>
    );
  }
  if (data.length === 0) {
    return (
      <p className="rounded-lg border border-border bg-surface-2 p-3 text-sm text-text-muted">
        No payment activity yet to summarise.
      </p>
    );
  }

  return (
    <>
      <div
        className="h-48"
        role="img"
        aria-label="Stacked bar chart of weekly payment-action counts"
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={data}>
            <CartesianGrid stroke="rgb(var(--border))" strokeDasharray="2 4" vertical={false} />
            <XAxis
              dataKey="week"
              tick={{ fill: "currentColor", opacity: 0.7, fontSize: 12 }}
            />
            <YAxis
              allowDecimals={false}
              tick={{ fill: "currentColor", opacity: 0.7, fontSize: 12 }}
            />
            <Tooltip
              contentStyle={{
                background: "rgb(var(--surface))",
                border: "1px solid rgb(var(--border))",
                color: "rgb(var(--text))",
                borderRadius: 8,
              }}
            />
            {ACTIONS.map((a) => (
              <Bar
                key={a.key}
                dataKey={a.key}
                stackId="1"
                fill={a.colour}
                name={a.label}
                isAnimationActive={false}
              />
            ))}
          </BarChart>
        </ResponsiveContainer>
      </div>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-text-muted">
          Show as data table
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                <th className="border-b border-border px-2 py-1 text-left">Week</th>
                {ACTIONS.map((a) => (
                  <th key={a.key} className="border-b border-border px-2 py-1 text-right">
                    {a.label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row) => (
                <tr key={row.week}>
                  <td className="px-2 py-1 font-mono">{row.week}</td>
                  {ACTIONS.map((a) => (
                    <td key={a.key} className="px-2 py-1 text-right font-mono">
                      {row[a.key]}
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

/** ISO week label like `2026-W19`. Stable string sort = chronological. */
function weekLabel(d: Date): string {
  const tgt = new Date(Date.UTC(d.getUTCFullYear(), d.getUTCMonth(), d.getUTCDate()));
  const dayNum = (tgt.getUTCDay() + 6) % 7;
  tgt.setUTCDate(tgt.getUTCDate() - dayNum + 3);
  const firstThursday = new Date(Date.UTC(tgt.getUTCFullYear(), 0, 4));
  const week =
    1 +
    Math.round(
      ((tgt.getTime() - firstThursday.getTime()) / 86400000 -
        3 +
        ((firstThursday.getUTCDay() + 6) % 7)) /
        7,
    );
  return `${tgt.getUTCFullYear()}-W${String(week).padStart(2, "0")}`;
}
