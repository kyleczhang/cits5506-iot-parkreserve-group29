import { describe, expect, it } from "vitest";

import { bayOut } from "./bay";

describe("bayOut", () => {
  it("accepts decimal strings from the backend for last_distance_cm", () => {
    const parsed = bayOut.parse({
      code: "A1",
      label: "Bay A1",
      state: "occupied",
      last_distance_cm: "12.00",
      sensor_last_seen_at: "2026-05-12T02:15:55.461366Z",
      current_reservation_id: null,
      current_reservation_arrival: null,
      check_in_grace_expires_at: null,
    });

    expect(parsed.last_distance_cm).toBe(12);
  });
});
