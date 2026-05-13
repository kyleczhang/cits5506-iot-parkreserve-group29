/**
 * Locks the query-key convention (plan §4 binding rule).
 * Any future singular/plural drift will trip this test.
 */
import { describe, expect, it } from "vitest";
import { qk } from "./queryKeys";

describe("query key convention", () => {
  it("uses plural resource names as the first segment", () => {
    expect(qk.bays.list()[0]).toBe("bays");
    expect(qk.reservations.list()[0]).toBe("reservations");
    expect(qk.payments.list()[0]).toBe("payments");
    expect(qk.plates.list()[0]).toBe("plates");
    expect(qk.conflicts.open()[0]).toBe("conflicts");
  });

  it("path-shapes detail keys as [resource, id]", () => {
    expect(qk.reservations.detail("abc")).toEqual(["reservations", "abc"]);
    expect(qk.bays.detail("B01")).toEqual(["bays", "B01"]);
  });

  it("nests sub-resources after the parent id", () => {
    expect(qk.bays.events("B01", "24h")).toEqual(["bays", "B01", "events", "24h"]);
  });
});
