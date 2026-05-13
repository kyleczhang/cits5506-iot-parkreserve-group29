/**
 * Zod mirrors of the `BayOut` / `BayEventOut` schemas from
 * doc/backend/openapi.yaml. The `bayState` enum order intentionally
 * matches the backend's enum so a `<select>` will render in a sensible
 * priority order.
 */
import { z } from "zod";

export const bayState = z.enum([
  "available",
  "reserved",
  "occupied",
  "pending_check_in",
  "reserved_checked_in",
  "conflict",
  "offline",
]);
export type BayState = z.infer<typeof bayState>;

const nullableNumberLike = z.preprocess((value) => {
  if (value === null || value === undefined || value === "") return value;
  if (typeof value === "string") {
    const parsed = Number(value);
    return Number.isNaN(parsed) ? value : parsed;
  }
  return value;
}, z.number().nullable().optional());

export const bayOut = z.object({
  code: z.string(),
  label: z.string(),
  state: bayState,
  last_distance_cm: nullableNumberLike,
  sensor_last_seen_at: z.string().nullable().optional(),
  current_reservation_id: z.string().uuid().nullable().optional(),
  current_reservation_arrival: z.string().nullable().optional(),
  check_in_grace_expires_at: z.string().nullable().optional(),
});
export type BayOut = z.infer<typeof bayOut>;

export const bayEventKind = z.enum([
  "state_changed",
  "sensor_online",
  "sensor_offline",
  "pending_check_in",
  "auto_check_in",
  "check_in_confirmed",
  "conflict_strong",
  "conflict_weak",
  "conflict_resolved",
  "no_show",
  "reservation_created",
  "reservation_cancelled",
  "reservation_completed",
  "plates_updated",
]);
export type BayEventKind = z.infer<typeof bayEventKind>;

export const bayEventOut = z.object({
  id: z.number(),
  kind: bayEventKind,
  from_state: bayState.nullable().optional(),
  to_state: bayState.nullable().optional(),
  reservation_id: z.string().uuid().nullable().optional(),
  payload: z.record(z.unknown()),
  created_at: z.string(),
});
export type BayEventOut = z.infer<typeof bayEventOut>;
