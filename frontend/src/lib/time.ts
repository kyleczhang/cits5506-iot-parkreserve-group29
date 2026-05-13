/**
 * Time helpers.
 *
 * Backend timestamps are ISO-8601 UTC strings (see
 * backend/app/utils/time.py). The frontend NEVER stores naive local
 * times — it parses ISO into `Date` objects (which are UTC instants
 * internally) and formats at the leaf using `date-fns` / `date-fns-tz`.
 *
 * Why both libraries? `date-fns` covers relative formatting and basic
 * date math; `date-fns-tz` adds zone-aware formatting for the rare
 * case where we want to pin a render to a specific facility timezone.
 * Both tree-shake cleanly.
 */
import { differenceInSeconds, formatDistanceToNowStrict, parseISO } from "date-fns";

/**
 * Parse an ISO-8601 string (or `null` / `undefined`) into a `Date`.
 * Returns `null` for nullish input, easing UI render logic that just
 * needs to do `time ?? "—"`.
 */
export function parseIso(value: string | null | undefined): Date | null {
  if (!value) return null;
  const d = parseISO(value);
  return Number.isNaN(d.getTime()) ? null : d;
}

/**
 * `"3 minutes ago"`, `"in 8 minutes"` — for relative timestamps in
 * audit logs and bay tiles.
 */
export function formatRelative(value: string | Date | null | undefined): string {
  const d = typeof value === "string" ? parseIso(value) : (value ?? null);
  if (!d) return "—";
  return formatDistanceToNowStrict(d, { addSuffix: true });
}

/**
 * Localised absolute timestamp — used in detail views where the
 * relative format would lose precision (e.g. payment receipt
 * "2026-05-12 14:08:33").
 */
export function formatAbsolute(value: string | Date | null | undefined): string {
  const d = typeof value === "string" ? parseIso(value) : (value ?? null);
  if (!d) return "—";
  return d.toLocaleString();
}

/**
 * Seconds remaining until `target`. Negative when `target` is in the past.
 * Drives the cockpit's `CountdownPill`.
 */
export function secondsUntil(target: string | Date | null | undefined): number {
  const d = typeof target === "string" ? parseIso(target) : (target ?? null);
  if (!d) return Number.NaN;
  return differenceInSeconds(d, new Date());
}

/**
 * Format a `mm:ss` (or `-mm:ss`) countdown string from a seconds value.
 * Negative values render with a leading minus, which the cockpit uses
 * to communicate "your grace period has expired by X".
 */
export function formatMmSs(seconds: number): string {
  if (!Number.isFinite(seconds)) return "—:—";
  const sign = seconds < 0 ? "-" : "";
  const abs = Math.abs(Math.trunc(seconds));
  const mm = Math.floor(abs / 60)
    .toString()
    .padStart(2, "0");
  const ss = (abs % 60).toString().padStart(2, "0");
  return `${sign}${mm}:${ss}`;
}
