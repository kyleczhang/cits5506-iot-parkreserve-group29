/**
 * Smoke tests for the bay-state badge.
 *
 * The plan §3.4 triple-coding rule (colour + glyph + label) is the
 * accessibility-critical part — these tests assert that the
 * **textual label** appears for every state, which is the part a
 * colour-blind user depends on.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { BayStateBadge } from "./BayStateBadge";
import type { BayState } from "@/schemas/bay";

const CASES: ReadonlyArray<[BayState, string]> = [
  ["available", /available/i],
  ["reserved", /reserved/i],
  ["pending_check_in", /pending check-in/i],
  ["reserved_checked_in", /checked in/i],
  ["occupied", /occupied/i],
  ["conflict", /conflict/i],
  ["offline", /offline/i],
].map(([s, label]) => [s as BayState, label.source]);

describe("BayStateBadge", () => {
  CASES.forEach(([state, label]) => {
    it(`renders the label for state '${state}'`, () => {
      render(<BayStateBadge state={state} />);
      expect(screen.getByText(new RegExp(label, "i"))).toBeInTheDocument();
    });
  });

  it("exposes an aria-label so the state is announced", () => {
    render(<BayStateBadge state="conflict" />);
    expect(
      screen.getByRole("status", { name: /Bay state: Conflict/i }),
    ).toBeInTheDocument();
  });
});
