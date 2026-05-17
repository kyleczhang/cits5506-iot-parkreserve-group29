/**
 * Zod mirrors of Socket.IO `/ws` event payloads.
 *
 * Verified against backend/app/sockets/events.py. Invalid payloads
 * are logged & dropped by `realtime/bus.ts` rather than crashing a
 * handler — this is the contract drift guard that plan §8 calls out.
 */
import { z } from "zod";
import { bayState } from "./bay";
import { reservationStatus, checkInMechanism } from "./reservation";
import { penaltyKind } from "./payment";
import { conflictKind, conflictResolution } from "./conflict";

export const wsBayUpdated = z.object({
  code: z.string(),
  label: z.string(),
  state: bayState,
  last_distance_cm: z.number().nullable().optional(),
  sensor_last_seen_at: z.string().nullable().optional(),
  current_reservation_id: z.string().uuid().nullable().optional(),
  updated_at: z.string().nullable().optional(),
});
export type WsBayUpdated = z.infer<typeof wsBayUpdated>;

export const wsReservationUpdated = z.object({
  id: z.string().uuid(),
  bay_code: z.string(),
  user_id: z.string().uuid(),
  status: reservationStatus,
  expected_arrival_time: z.string().nullable().optional(),
  booked_at: z.string().nullable().optional(),
  check_in_grace_expires_at: z.string().nullable().optional(),
  checked_in_at: z.string().nullable().optional(),
  check_in_mechanism: checkInMechanism.nullable().optional(),
  cancelled_at: z.string().nullable().optional(),
  completed_at: z.string().nullable().optional(),
});
export type WsReservationUpdated = z.infer<typeof wsReservationUpdated>;

export const wsReservationPendingCheckIn = z.object({
  id: z.string().uuid(),
  bay_code: z.string(),
  user_id: z.string().uuid(),
  detected_at: z.string().nullable().optional(),
  check_in_grace_expires_at: z.string().nullable().optional(),
});
export type WsReservationPendingCheckIn = z.infer<typeof wsReservationPendingCheckIn>;

/**
 * `reservation.auto_checked_in` is a superset of `WsReservationUpdated`
 * — the additional fields are what unlocks the §4 setQueryData exception.
 */
export const wsReservationAutoCheckedIn = wsReservationUpdated.extend({
  recognised_plate: z.string(),
  checked_in_at: z.string().nullable().optional(),
});
export type WsReservationAutoCheckedIn = z.infer<typeof wsReservationAutoCheckedIn>;

export const wsPlateUpdated = z.object({
  user_id: z.string().uuid(),
  plates: z.array(z.object({ plate: z.string(), label: z.string().nullable() })),
});
export type WsPlateUpdated = z.infer<typeof wsPlateUpdated>;

export const wsConflict = z.object({
  id: z.string().uuid(),
  bay_code: z.string(),
  kind: conflictKind,
  recognised_plate: z.string().nullable().optional(),
  detected_at: z.string().nullable().optional(),
  resolved_at: z.string().nullable().optional(),
  resolution: conflictResolution.nullable().optional(),
});
export type WsConflict = z.infer<typeof wsConflict>;

export const wsPaymentDepositReleased = z.object({
  reservation_id: z.string().uuid(),
  user_id: z.string().uuid(),
  amount_cents: z.number().int(),
  reason: z.string(),
});
export const wsPaymentRefunded = z.object({
  reservation_id: z.string().uuid(),
  user_id: z.string().uuid(),
  amount_cents: z.number().int(),
  reason: z.string(),
});
export const wsPaymentPenaltyCaptured = z.object({
  reservation_id: z.string().uuid(),
  user_id: z.string().uuid(),
  penalty_kind: penaltyKind,
  amount_cents: z.number().int(),
});
