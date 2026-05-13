/**
 * Zod mirrors of the admin conflicts payload.
 *
 * `user_arrived_and_checked_in` is intentionally NOT included in the
 * resolution enum we accept on the UI — the backend sets that value
 * itself on the weak-conflict fallback check-in path (see plan §5.10
 * and openapi.yaml). The admin form only offers `vehicle_left` and
 * `admin_resolved`.
 */
import { z } from "zod";

export const conflictKind = z.enum(["strong", "weak"]);
export type ConflictKind = z.infer<typeof conflictKind>;

export const conflictResolution = z.enum([
  "vehicle_left",
  "admin_resolved",
  "user_arrived_and_checked_in",
]);
export type ConflictResolution = z.infer<typeof conflictResolution>;

export const conflictOut = z.object({
  id: z.string().uuid(),
  bay_code: z.string(),
  kind: conflictKind,
  reservation_id: z.string().uuid().nullable().optional(),
  recognised_plate: z.string().nullable().optional(),
  lpr_confidence: z.number().nullable().optional(),
  evidence_image_url: z.string().nullable().optional(),
  image_purge_at: z.string().nullable().optional(),
  detected_at: z.string(),
  resolved_at: z.string().nullable().optional(),
  resolution: conflictResolution.nullable().optional(),
});
export type ConflictOut = z.infer<typeof conflictOut>;

export const adminResolution = z.enum(["vehicle_left", "admin_resolved"]);
export const conflictResolveRequest = z.object({
  resolution: adminResolution,
});
export type ConflictResolveRequest = z.infer<typeof conflictResolveRequest>;
