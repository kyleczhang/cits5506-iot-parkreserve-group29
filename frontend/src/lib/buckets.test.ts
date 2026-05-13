import { describe, expect, it } from "vitest";
import { bucketStateByHour, countByKind, dominantStatePerHour } from "./buckets";
import type { BayEventOut } from "@/schemas/bay";

const NOW = new Date("2026-05-12T12:00:00Z");

function evt(partial: Partial<BayEventOut>): BayEventOut {
  return {
    id: Math.floor(Math.random() * 1e9),
    kind: "state_changed",
    from_state: null,
    to_state: null,
    reservation_id: null,
    payload: {},
    created_at: NOW.toISOString(),
    ...partial,
  };
}

describe("bucketStateByHour", () => {
  it("returns 24 buckets", () => {
    expect(bucketStateByHour([], NOW)).toHaveLength(24);
  });

  it("accumulates seconds across buckets when state spans hours", () => {
    // Bay was `available` from 24h ago through to "now".
    const events: BayEventOut[] = [
      evt({
        kind: "state_changed",
        to_state: "available",
        created_at: new Date(NOW.getTime() - 25 * 3600 * 1000).toISOString(),
      }),
    ];
    const buckets = bucketStateByHour(events, NOW);
    const total = buckets.reduce((acc, b) => acc + b.available, 0);
    // 24h ≈ 86 400 s, allow rounding slack.
    expect(total).toBeGreaterThan(86_000);
    expect(total).toBeLessThan(86_500);
  });
});

describe("dominantStatePerHour", () => {
  it("picks the state with the highest seconds in each bucket", () => {
    const buckets = bucketStateByHour(
      [
        evt({
          kind: "state_changed",
          to_state: "occupied",
          created_at: new Date(NOW.getTime() - 25 * 3600 * 1000).toISOString(),
        }),
      ],
      NOW,
    );
    const dominant = dominantStatePerHour(buckets);
    expect(dominant.every((s) => s === "occupied")).toBe(true);
  });
});

describe("countByKind", () => {
  it("counts each kind", () => {
    const result = countByKind([
      evt({ kind: "state_changed" }),
      evt({ kind: "state_changed" }),
      evt({ kind: "conflict_strong" }),
    ]);
    expect(result["state_changed"]).toBe(2);
    expect(result["conflict_strong"]).toBe(1);
  });
});
