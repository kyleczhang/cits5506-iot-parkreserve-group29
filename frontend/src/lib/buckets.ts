/**
 * Bucketing helpers for the admin telemetry pipeline.
 *
 * The backend exposes raw `bay_events` rows; the telemetry charts
 * project these into hourly slices over a 24 h window. Pure functions
 * so each chart can render synchronously from cached data without a
 * Web-Worker round-trip (small datasets — three demo bays).
 */
import type { BayEventOut, BayState } from "@/schemas/bay";

/** Tally of how many seconds each state held during a single hour. */
export interface HourTally {
  hour: number; // 0..23 (local time of the bucket)
  available: number;
  reserved: number;
  pending_check_in: number;
  occupied: number;
  reserved_checked_in: number;
  conflict: number;
  offline: number;
}

export const ZERO_TALLY: Omit<HourTally, "hour"> = {
  available: 0,
  reserved: 0,
  pending_check_in: 0,
  occupied: 0,
  reserved_checked_in: 0,
  conflict: 0,
  offline: 0,
};

/**
 * Build a 24-row table where each row carries the share-of-hour each
 * state held. We iterate `state_changed` rows oldest→newest, carry
 * forward the "current" state, and accumulate seconds-per-bucket.
 */
export function bucketStateByHour(
  events: ReadonlyArray<BayEventOut>,
  now: Date = new Date(),
): ReadonlyArray<HourTally> {
  const stateRows = events
    .filter((e) => e.kind === "state_changed" && e.to_state)
    .slice()
    .sort((a, b) => Date.parse(a.created_at) - Date.parse(b.created_at));

  const startMs = now.getTime() - 24 * 3600 * 1000;
  const buckets: HourTally[] = [];
  for (let i = 0; i < 24; i++) {
    buckets.push({ ...ZERO_TALLY, hour: new Date(startMs + i * 3600 * 1000).getHours() });
  }

  // Seed with the most recent state observed before the window opened
  // (so we don't leave the first hour empty when the bay was steady).
  let prevState: BayState | null = null;
  let prevAt = startMs;
  const beforeWindow = stateRows.filter(
    (e) => Date.parse(e.created_at) < startMs,
  );
  if (beforeWindow.length > 0) {
    const last = beforeWindow[beforeWindow.length - 1];
    prevState = (last?.to_state as BayState) ?? null;
  }

  const inWindow = stateRows.filter(
    (e) => Date.parse(e.created_at) >= startMs,
  );

  for (const ev of inWindow) {
    const t = Date.parse(ev.created_at);
    if (prevState) {
      accumulate(buckets, prevState, prevAt, t, startMs);
    }
    prevState = (ev.to_state as BayState) ?? null;
    prevAt = t;
  }
  // Tail — from the last transition (or window start) to "now".
  if (prevState) {
    accumulate(buckets, prevState, prevAt, now.getTime(), startMs);
  }
  return buckets;
}

function accumulate(
  buckets: HourTally[],
  state: BayState,
  fromMs: number,
  toMs: number,
  windowStartMs: number,
): void {
  const clampedFrom = Math.max(fromMs, windowStartMs);
  const clampedTo = Math.max(toMs, clampedFrom);
  for (let i = 0; i < 24; i++) {
    const bucketStart = windowStartMs + i * 3600 * 1000;
    const bucketEnd = bucketStart + 3600 * 1000;
    const overlap = Math.max(
      0,
      Math.min(clampedTo, bucketEnd) - Math.max(clampedFrom, bucketStart),
    );
    if (overlap > 0) {
      buckets[i]![state] += overlap / 1000;
    }
  }
}

/** Dominant state for each hour — for the heatmap. */
export function dominantStatePerHour(
  buckets: ReadonlyArray<HourTally>,
): BayState[] {
  return buckets.map((b) => {
    const order: BayState[] = [
      "available",
      "reserved",
      "pending_check_in",
      "occupied",
      "reserved_checked_in",
      "conflict",
      "offline",
    ];
    let winner: BayState = "offline";
    let max = 0;
    for (const s of order) {
      const v = b[s];
      if (v > max) {
        winner = s;
        max = v;
      }
    }
    return winner;
  });
}

/** Counts by event kind over the entire input (24 h slice in practice). */
export function countByKind(
  events: ReadonlyArray<BayEventOut>,
): Record<string, number> {
  const out: Record<string, number> = {};
  for (const e of events) {
    out[e.kind] = (out[e.kind] ?? 0) + 1;
  }
  return out;
}
