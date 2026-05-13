/**
 * Tiny step-line sparkline of a bay's recent state transitions.
 *
 * Source data: `GET /api/v1/bays/{code}/events` filtered to
 * `state_changed` rows. Y axis is implicit (states project to ordinals
 * with a stable ordering — see `STATE_ORDER`); the line colour is
 * drawn from the current state for at-a-glance trend.
 */
import { LineChart, Line, ResponsiveContainer, YAxis } from "recharts";

import type { BayEventOut, BayState } from "@/schemas/bay";
import { STATE_PALETTE } from "@/lib/theme";

const STATE_ORDER: BayState[] = [
  "offline",
  "available",
  "reserved",
  "pending_check_in",
  "occupied",
  "reserved_checked_in",
  "conflict",
];

interface Props {
  events: ReadonlyArray<BayEventOut>;
  currentState: BayState;
}

export function BaySparkline({ events, currentState }: Props) {
  // Keep only the most recent N state_changed rows (oldest → newest).
  const series = events
    .filter((e) => e.kind === "state_changed" && e.to_state)
    .slice(0, 30)
    .map((e, i) => ({
      i,
      v: STATE_ORDER.indexOf((e.to_state as BayState) ?? "offline"),
    }))
    .reverse();

  if (series.length < 2) {
    return (
      <div
        className="grid h-10 place-items-center rounded bg-surface-2 text-xs text-text-muted"
        aria-label="Not enough state-change events to render a sparkline"
      >
        —
      </div>
    );
  }

  const colour = paletteColourFor(currentState);

  return (
    <div
      className="h-10 w-full"
      role="img"
      aria-label={`Recent state transitions, currently ${currentState.replace("_", " ")}`}
    >
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={series}>
          <YAxis hide domain={[0, STATE_ORDER.length - 1]} />
          <Line
            type="stepAfter"
            dataKey="v"
            stroke={colour}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

function paletteColourFor(state: BayState): string {
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
