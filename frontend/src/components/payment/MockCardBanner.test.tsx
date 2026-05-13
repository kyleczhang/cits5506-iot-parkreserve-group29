/**
 * Asserts the rubric-mandated wording for the mock-payment banner.
 *
 * Mirrors plan §6.3 ("MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS")
 * — any future edit to the banner copy must update this assertion too.
 */
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { MOCK_PAYMENT_BANNER_TEXT, MockCardBanner } from "./MockCardBanner";

describe("MockCardBanner", () => {
  it("renders the rubric-mandated wording verbatim", () => {
    render(<MockCardBanner />);
    expect(screen.getByText(MOCK_PAYMENT_BANNER_TEXT)).toBeInTheDocument();
  });
  it("uses role='alert' so screen readers announce it", () => {
    render(<MockCardBanner />);
    expect(screen.getByRole("alert")).toBeInTheDocument();
  });
  it("locks the exact banner string at module level", () => {
    expect(MOCK_PAYMENT_BANNER_TEXT).toBe(
      "MOCK PAYMENT — DO NOT ENTER REAL CARD DETAILS",
    );
  });
});
