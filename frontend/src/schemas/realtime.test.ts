/**
 * Locks the realtime payload shapes.
 *
 * Wire format mirrored from backend/app/sockets/events.py. The key
 * assertion is that `wsReservationAutoCheckedIn` is a strict SUPERSET
 * of `wsReservationUpdated` — that's what justifies the §4 setQueryData
 * exception. If this drifts, the cockpit's optimistic state flip needs
 * a re-evaluation.
 */
import { describe, expect, it } from "vitest";
import {
  wsBayUpdated,
  wsReservationAutoCheckedIn,
  wsReservationUpdated,
} from "./realtime";

describe("wsBayUpdated", () => {
  it("parses the minimum required shape", () => {
    const parsed = wsBayUpdated.parse({
      code: "B01",
      label: "Bay 1",
      state: "available",
    });
    expect(parsed.code).toBe("B01");
  });
});

describe("wsReservationAutoCheckedIn", () => {
  it("requires recognised_plate (the WS-only field)", () => {
    expect(() =>
      wsReservationAutoCheckedIn.parse({
        id: "00000000-0000-0000-0000-000000000001",
        bay_code: "B01",
        user_id: "00000000-0000-0000-0000-000000000002",
        status: "checked_in",
      }),
    ).toThrow();
  });

  it("is a superset of wsReservationUpdated", () => {
    const updatedKeys = Object.keys(wsReservationUpdated.shape).sort();
    const autoKeys = Object.keys(wsReservationAutoCheckedIn.shape).sort();
    // Every updated-key must appear in auto-checked-in (superset rule).
    for (const k of updatedKeys) {
      expect(autoKeys).toContain(k);
    }
    // And auto-checked-in carries strictly more keys.
    expect(autoKeys.length).toBeGreaterThan(updatedKeys.length);
  });
});
