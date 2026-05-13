/**
 * Money helpers.
 *
 * The backend stores money as integer cents — see `amount_cents` and
 * `deposit_cents` in doc/backend/openapi.yaml. The dashboard NEVER holds a
 * `number` representing dollars; it carries cents end-to-end and formats
 * only at the leaf. This keeps us out of the float-rounding minefield.
 */

const FORMATTER = new Intl.NumberFormat("en-AU", {
  style: "currency",
  currency: "AUD",
  minimumFractionDigits: 2,
});

/**
 * Format integer cents as a localised currency string.
 *
 * @example formatCents(1000)  // "$10.00"
 * @example formatCents(-500)  // "-$5.00"
 */
export function formatCents(cents: number): string {
  if (!Number.isFinite(cents)) return "—";
  return FORMATTER.format(cents / 100);
}

/**
 * Whether a payment action is, from the user's wallet perspective,
 * money leaving the user (true) or money returning (false).
 *
 * Used by the ledger row to choose colour: out → danger, in → success.
 * Note that `pre_auth` is a *hold*, not a charge — we show it as out so
 * the user sees their available balance reflect what's held, but the
 * ledger row labels it "held" rather than "paid".
 */
export function isOutboundPayment(
  action: "pre_auth" | "release" | "refund" | "penalty_capture",
): boolean {
  return action === "pre_auth" || action === "penalty_capture";
}
