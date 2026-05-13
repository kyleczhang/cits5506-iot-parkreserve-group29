/**
 * Query-key helper — single source of truth for TanStack Query cache keys.
 *
 * **Convention (binding rule).** First segment is the *plural* resource
 * exactly as it appears in the REST path: `reservations`, `bays`,
 * `payments`, `plates`, `conflicts`. No singular forms anywhere
 * (`['reservation', id]` is a bug, NOT a synonym).
 *
 * See doc/frontend/frontend-implementation-plan.md §4. Routing every
 * `useQuery` / `invalidateQueries` / `setQueryData` call through this
 * helper prevents the singular/plural drift that bit us before.
 */
export const qk = {
  auth: {
    me: () => ["auth", "me"] as const,
  },
  bays: {
    list: () => ["bays"] as const,
    detail: (code: string) => ["bays", code] as const,
    events: (code: string, slice = "default") =>
      ["bays", code, "events", slice] as const,
  },
  plates: {
    list: () => ["plates"] as const,
  },
  reservations: {
    list: () => ["reservations"] as const,
    detail: (id: string) => ["reservations", id] as const,
  },
  payments: {
    list: () => ["payments"] as const,
    detail: (id: string) => ["payments", id] as const,
  },
  conflicts: {
    open: () => ["conflicts", "open"] as const,
  },
} as const;
