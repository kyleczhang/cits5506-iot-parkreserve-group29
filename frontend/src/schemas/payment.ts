/**
 * Zod mirrors of the mock-payment ledger payloads.
 */
import { z } from "zod";

export const paymentAction = z.enum([
  "pre_auth",
  "release",
  "refund",
  "penalty_capture",
]);
export type PaymentAction = z.infer<typeof paymentAction>;

export const penaltyKind = z.enum(["late_cancel", "no_show", "weak_conflict"]);
export type PenaltyKind = z.infer<typeof penaltyKind>;

export const paymentStatus = z.enum(["succeeded", "failed", "voided"]);
export type PaymentStatus = z.infer<typeof paymentStatus>;

export const transactionOut = z.object({
  id: z.string().uuid(),
  reservation_id: z.string().uuid(),
  action: paymentAction,
  penalty_kind: penaltyKind.nullable().optional(),
  amount_cents: z.number().int(),
  status: paymentStatus,
  occurred_at: z.string(),
});
export type TransactionOut = z.infer<typeof transactionOut>;

export const transactionListResponse = z.object({
  transactions: z.array(transactionOut),
});
