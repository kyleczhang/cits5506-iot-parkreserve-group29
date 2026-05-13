/**
 * Smoke tests for the reservation-status badge.
 *
 * Mirrors `BayStateBadge.test.tsx`: the colour-blind-safe requirement
 * is that every status has a distinct textual label, so we assert the
 * label is rendered for every member of `ReservationStatus`. This is
 * also the regression net for the original "no-show shows up as
 * Offline" bug — `expired_no_show` used to fall through the
 * BayStateBadge default branch.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { ReservationStatusBadge } from "./ReservationStatusBadge";
import type { ReservationStatus } from "@/schemas/reservation";

const CASES: ReadonlyArray<[ReservationStatus, string]> = [
  ["active", "reserved"],
  ["pending_check_in", "pending check-in"],
  ["checked_in", "checked in"],
  ["in_conflict", "conflict"],
  ["completed", "completed"],
  ["cancelled", "cancelled"],
  ["cancelled_late", "cancelled \\(late\\)"],
  ["expired_no_show", "no-show"],
];

describe("ReservationStatusBadge", () => {
  CASES.forEach(([status, label]) => {
    it(`renders the label for status '${status}'`, () => {
      render(<ReservationStatusBadge status={status} />);
      expect(screen.getByText(new RegExp(label, "i"))).toBeInTheDocument();
    });
  });

  it("never renders the literal 'Offline' (the original bug)", () => {
    // The whole point of this component is that terminal reservation
    // statuses no longer reuse the bay-state `offline` fallback.
    for (const [status] of CASES) {
      const { unmount } = render(<ReservationStatusBadge status={status} />);
      expect(screen.queryByText(/offline/i)).not.toBeInTheDocument();
      unmount();
    }
  });

  it("exposes an aria-label so the status is announced", () => {
    render(<ReservationStatusBadge status="expired_no_show" />);
    expect(
      screen.getByRole("status", { name: /Reservation status: No-show/i }),
    ).toBeInTheDocument();
  });
});
