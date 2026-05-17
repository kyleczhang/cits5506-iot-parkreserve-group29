/**
 * Per-bay 24-hour heatmap.
 *
 * Plain CSS grid (24 columns × 1 row); each cell colour = dominant
 * state for that hour. No chart library needed — keeps the bundle
 * tight, and the data-table fallback is essentially free.
 */
import { useQuery } from "@tanstack/react-query";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../ui/SimpleTooltip";

import { listBayEvents } from "@/api/bays";
import { qk } from "@/api/queryKeys";
import { Spinner } from "@/components/ui/Spinner";
import { STATE_PALETTE } from "@/lib/theme";
import { bucketStateByHour, dominantStatePerHour } from "@/lib/buckets";

interface Props {
  code: string;
}

export function OccupancyHeatmap({ code }: Props) {
  const events = useQuery({
    queryKey: qk.bays.events(code, "24h"),
    queryFn: () => listBayEvents(code, { limit: 200 }),
    staleTime: 60_000,
  });

  if (events.isLoading) {
    return (
      <div className="grid h-16 place-items-center">
        <Spinner size="sm" label="Loading heatmap" />
      </div>
    );
  }
  if (events.isError) {
    return (
      <p className="text-sm text-danger">Couldn&apos;t load heatmap data.</p>
    );
  }

  const buckets = bucketStateByHour(events.data ?? []);
  const dominant = dominantStatePerHour(buckets);

  return (
    <TooltipProvider>
      <div
        className="grid gap-1"
        style={{ gridTemplateColumns: "repeat(24, minmax(0, 1fr))" }}
        role="img"
        aria-label="24-hour occupancy heatmap; each cell shows the dominant state for that hour"
      >
        {dominant.map((state, hour) => (
          <Tooltip key={hour}>
            <TooltipTrigger>
              <span
                aria-label={`${hour}:00 — ${state.replace("_", " ")}`}
                className="block h-8 rounded"
                style={{ background: colourFor(state) }}
              />
            </TooltipTrigger>
            <TooltipContent>
              {String(hour).padStart(2, "0")}:00 — {state.replace("_", " ")}
            </TooltipContent>
          </Tooltip>
        ))}
      </div>

      <details className="mt-3 text-sm">
        <summary className="cursor-pointer text-text-muted">
          Show as data table
        </summary>
        <div className="mt-2 overflow-x-auto">
          <table className="min-w-full text-xs">
            <thead>
              <tr>
                <th className="border-b border-border px-2 py-1 text-left">Hour</th>
                <th className="border-b border-border px-2 py-1 text-left">Dominant</th>
              </tr>
            </thead>
            <tbody>
              {dominant.map((state, hour) => (
                <tr key={hour}>
                  <td className="px-2 py-1 font-mono">
                    {String(hour).padStart(2, "0")}:00
                  </td>
                  <td className="px-2 py-1">{state.replace("_", " ")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </details>
    </TooltipProvider>
  );
}

function colourFor(state: string): string {
  switch (state) {
    case "available":
      return STATE_PALETTE.available;
    case "reserved":
    case "pending_check_in":
      return STATE_PALETTE.reserved;
    case "occupied":
    case "reserved_checked_in":
      return STATE_PALETTE.occupied;
    case "conflict":
      return STATE_PALETTE.conflict;
    case "offline":
    default:
      return STATE_PALETTE.offline;
  }
}
