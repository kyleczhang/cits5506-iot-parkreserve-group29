/**
 * Zod mirrors of `/api/v1/users/me/plates` payloads.
 *
 * Client-side, plates are uppercased + space-stripped before submission.
 * The backend does the same normalisation — this is purely a UX preview
 * so the user sees the canonical form before round-tripping.
 */
import { z } from "zod";

/** Normalise a plate string to upper-case-no-spaces. */
export function normalisePlate(value: string): string {
  return value.replace(/\s+/g, "").toUpperCase();
}

export const plateAddRequest = z.object({
  plate: z
    .string()
    .min(1, "plate required")
    .max(16, "at most 16 characters")
    .transform(normalisePlate),
  label: z.string().max(64).optional().nullable(),
});
export type PlateAddRequest = z.infer<typeof plateAddRequest>;

export const plateOut = z.object({
  id: z.string().uuid(),
  plate: z.string(),
  label: z.string().nullable().optional(),
  created_at: z.string(),
});
export type PlateOut = z.infer<typeof plateOut>;
