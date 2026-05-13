import { describe, expect, it } from "vitest";
import { formatMmSs, parseIso, secondsUntil } from "./time";

describe("parseIso", () => {
  it("parses a valid ISO string", () => {
    expect(parseIso("2026-05-12T01:02:03Z")?.getUTCFullYear()).toBe(2026);
  });
  it("returns null for nullish inputs", () => {
    expect(parseIso(null)).toBeNull();
    expect(parseIso(undefined)).toBeNull();
    expect(parseIso("")).toBeNull();
  });
  it("returns null for malformed input", () => {
    expect(parseIso("not-a-date")).toBeNull();
  });
});

describe("formatMmSs", () => {
  it("renders mm:ss zero-padded", () => {
    expect(formatMmSs(0)).toBe("00:00");
    expect(formatMmSs(65)).toBe("01:05");
    expect(formatMmSs(600)).toBe("10:00");
  });
  it("prefixes negative values with a minus", () => {
    expect(formatMmSs(-65)).toBe("-01:05");
  });
  it("returns a dash for non-finite input", () => {
    expect(formatMmSs(Number.NaN)).toBe("—:—");
  });
});

describe("secondsUntil", () => {
  it("is positive for a future target", () => {
    const future = new Date(Date.now() + 30_000).toISOString();
    expect(secondsUntil(future)).toBeGreaterThan(25);
  });
  it("is negative for a past target", () => {
    const past = new Date(Date.now() - 30_000).toISOString();
    expect(secondsUntil(past)).toBeLessThan(0);
  });
  it("returns NaN for nullish input", () => {
    expect(Number.isNaN(secondsUntil(null))).toBe(true);
  });
});
