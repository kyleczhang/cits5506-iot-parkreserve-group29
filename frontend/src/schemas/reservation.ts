/**
 * Zod mirrors of the reservation + card payloads.
 *
 * Card schema follows the `CardDetails` block in doc/backend/openapi.yaml
 * — verified field-for-field. Mutating the regexes here without updating
 * the backend will break the `POST /reservations` round-trip; do not
 * tighten without a corresponding backend change.
 */
import { z } from "zod";

export const reservationStatus = z.enum([
  "active",
  "pending_check_in",
  "checked_in",
  "completed",
  "cancelled",
  "cancelled_late",
  "expired_no_show",
  "in_conflict",
]);
export type ReservationStatus = z.infer<typeof reservationStatus>;

export const checkInMechanism = z.enum(["auto_lpr", "qr", "manual"]);
export type CheckInMechanism = z.infer<typeof checkInMechanism>;

export const cardDetails = z.object({
  number: z.string().regex(/^[0-9]{13,19}$/, "13–19 digits"),
  cvv: z.string().regex(/^[0-9]{3,4}$/, "3–4 digits"),
  expiry_month: z.number().int().min(1).max(12),
  expiry_year: z.number().int().min(2024).max(2099),
  holder_name: z.string().min(1).max(120),
});
export type CardDetails = z.infer<typeof cardDetails>;

export const reservationCreateRequest = z.object({
  bay_code: z.string().min(1).max(16),
  expected_arrival_time: z.string(),
  card: cardDetails,
});
export type ReservationCreateRequest = z.infer<typeof reservationCreateRequest>;

export const reservationCheckInRequest = z.object({
  bay_code: z.string().min(1).max(16),
  source: z.enum(["qr", "manual"]),
});
export type ReservationCheckInRequest = z.infer<typeof reservationCheckInRequest>;

export const reservationDepositInfo = z.object({
  deposit_cents: z.number().int(),
});

export const reservationOut = z.object({
  id: z.string().uuid(),
  bay_code: z.string(),
  user_id: z.string().uuid(),
  status: reservationStatus,
  expected_arrival_time: z.string(),
  booked_at: z.string(),
  check_in_grace_expires_at: z.string().nullable().optional(),
  checked_in_at: z.string().nullable().optional(),
  check_in_mechanism: checkInMechanism.nullable().optional(),
  cancelled_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
  payment: reservationDepositInfo.nullable().optional(),
});
export type ReservationOut = z.infer<typeof reservationOut>;
