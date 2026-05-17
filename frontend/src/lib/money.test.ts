import { describe, expect, it } from "vitest";
import { formatCents, isOutboundPayment } from "./money";

describe("formatCents", () => {
  it("formats positive cents as AUD with two decimals", () => {
    expect(formatCents(1000)).toMatch(/\$10\.00/);
    expect(formatCents(123)).toMatch(/\$1\.23/);
  });

  it("formats zero correctly", () => {
    expect(formatCents(0)).toMatch(/\$0\.00/);
  });

  it("renders negative amounts with a minus", () => {
    expect(formatCents(-500)).toMatch(/-\$5\.00/);
  });

  it("returns a dash for non-finite input", () => {
    expect(formatCents(Number.NaN)).toBe("—");
    expect(formatCents(Infinity)).toBe("—");
  });
});

describe("isOutboundPayment", () => {
  it("treats pre_auth and penalty_capture as out", () => {
    expect(isOutboundPayment("pre_auth")).toBe(true);
    expect(isOutboundPayment("penalty_capture")).toBe(true);
  });

  it("treats release and refund as in", () => {
    expect(isOutboundPayment("release")).toBe(false);
    expect(isOutboundPayment("refund")).toBe(false);
  });
});
