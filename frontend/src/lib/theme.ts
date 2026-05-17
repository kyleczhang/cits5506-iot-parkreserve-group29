/**
 * Design-token export.
 *
 * Mirror of the CSS custom properties declared in `src/index.css`. We
 * duplicate the values here (instead of reading `getComputedStyle`) so
 * that pure-JS code paths — Recharts series colours, dynamically
 * generated SVG, tests asserting contrast ratios — can resolve a token
 * without a DOM. The two surfaces are kept in sync by
 * `lib/theme.test.ts` which loads both and diffs them.
 *
 * Token reference: doc/frontend/frontend-implementation-plan.md §3.1.
 */

export type ThemeName = "driver" | "ops";

export interface ThemePalette {
  /** Page background. */
  bg: string;
  /** Card / panel surface. */
  surface: string;
  /** Inset / hover surface. */
  surface2: string;
  /** Default border / divider. */
  border: string;
  /** Primary text colour (≥ 7 : 1 against `bg`). */
  text: string;
  /** Muted text (≥ 4.5 : 1 against `bg`). */
  textMuted: string;
  /** Brand colour. */
  brand: string;
  /** Accent (focus rings, hyperlinks, KPI sparklines). */
  accent: string;
}

/** Shared status palette — identical across themes, mirrors the LED scheme. */
export const STATE_PALETTE = {
  available: "#22C55E",
  reserved: "#EAB308",
  pending: "#EAB308",
  occupied: "#EF4444",
  conflict: "#DC2626",
  offline: "#64748B",
} as const;

export type BayStateName = keyof typeof STATE_PALETTE;

export const DRIVER_PALETTE: ThemePalette = {
  bg: "#F8FAFC",
  surface: "#FFFFFF",
  surface2: "#F1F5F9",
  border: "#E2E8F0",
  text: "#0F172A",
  textMuted: "#475569",
  brand: "#0F766E",
  accent: "#0EA5E9",
};

export const OPS_PALETTE: ThemePalette = {
  bg: "#0B1220",
  surface: "#111A2E",
  surface2: "#16223A",
  border: "#1F2A44",
  text: "#F8FAFC",
  textMuted: "#94A3B8",
  brand: "#2DD4BF",
  accent: "#38BDF8",
};

/** Swap the document's `data-theme` attribute (idempotent). */
export function applyTheme(theme: ThemeName): void {
  if (typeof document === "undefined") return;
  document.documentElement.dataset["theme"] = theme;
}

/** Cheap, in-place palette lookup for non-React code. */
export function paletteFor(theme: ThemeName): ThemePalette {
  return theme === "ops" ? OPS_PALETTE : DRIVER_PALETTE;
}
