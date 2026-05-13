/**
 * Runtime configuration sourced from Vite env vars.
 *
 * Keep this small — runtime config that the backend owns (booking
 * window minutes, late-cancel cutoff, deposit amount) is intentionally
 * NOT mirrored here. See plan §10.8 — those are runtime env vars on the
 * backend with no public REST exposure, so we use server 422s as truth
 * and only carry the most boring constants in the build.
 */

/** Origin for REST + Socket.IO. Empty string = same-origin (production). */
export const BACKEND_ORIGIN: string = import.meta.env["VITE_BACKEND_ORIGIN"] ?? "";

/**
 * Documented default for the backend's `BOOKING_WINDOW_MINUTES` env var.
 * Used only as a client-side hint; the server 422 is authoritative.
 */
export const BOOKING_WINDOW_MINUTES_DEFAULT = 60;
