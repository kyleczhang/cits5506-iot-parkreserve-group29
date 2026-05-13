/**
 * Theme-token contrast assertions.
 *
 * Locks the driver/ops palettes to WCAG AA (4.5 : 1) for body text and
 * AAA (7 : 1) for primary text — any token edit that breaks this fails CI.
 */
import { describe, expect, it } from "vitest";
import { contrastRatio } from "./contrast";
import { DRIVER_PALETTE, OPS_PALETTE, STATE_PALETTE } from "./theme";

describe("driver palette contrast", () => {
  it("text on bg meets WCAG AAA (≥ 7:1)", () => {
    const ratio = contrastRatio(DRIVER_PALETTE.text, DRIVER_PALETTE.bg);
    expect(ratio).toBeGreaterThanOrEqual(7);
  });
  it("muted text on bg meets WCAG AA (≥ 4.5:1)", () => {
    const ratio = contrastRatio(DRIVER_PALETTE.textMuted, DRIVER_PALETTE.bg);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });
});

describe("ops palette contrast", () => {
  it("text on bg meets WCAG AAA (≥ 7:1)", () => {
    const ratio = contrastRatio(OPS_PALETTE.text, OPS_PALETTE.bg);
    expect(ratio).toBeGreaterThanOrEqual(7);
  });
  it("muted text on bg meets WCAG AA (≥ 4.5:1)", () => {
    const ratio = contrastRatio(OPS_PALETTE.textMuted, OPS_PALETTE.bg);
    expect(ratio).toBeGreaterThanOrEqual(4.5);
  });
});

describe("status palette completeness", () => {
  it("has every state name the BayState enum carries", () => {
    expect(Object.keys(STATE_PALETTE).sort()).toEqual(
      ["available", "conflict", "occupied", "offline", "pending", "reserved"].sort(),
    );
  });
});
