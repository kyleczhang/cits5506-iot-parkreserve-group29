/**
 * Tailwind configuration — token-driven theming.
 *
 * Every colour token is sourced from a CSS custom property declared in
 * `src/index.css`. This is what lets a single `data-theme="driver"` /
 * `data-theme="ops"` swap on the `<html>` element re-skin the whole app
 * without forking the stylesheet — see
 * doc/frontend/frontend-implementation-plan.md §3.1.
 */
import type { Config } from "tailwindcss";

const cssVar = (name: string) => `rgb(var(--${name}) / <alpha-value>)`;

const config: Config = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: ["selector", '[data-theme="ops"]'],
  theme: {
    extend: {
      colors: {
        bg: cssVar("bg"),
        surface: cssVar("surface"),
        "surface-2": cssVar("surface-2"),
        border: cssVar("border"),
        text: cssVar("text"),
        "text-muted": cssVar("text-muted"),
        brand: cssVar("brand"),
        accent: cssVar("accent"),
        // Status palette is identical across themes — it matches the LED
        // colour scheme defined in proposal.md §5.1 step 2.
        state: {
          available: cssVar("state-available"),
          reserved: cssVar("state-reserved"),
          pending: cssVar("state-pending"),
          occupied: cssVar("state-occupied"),
          conflict: cssVar("state-conflict"),
          offline: cssVar("state-offline"),
        },
        // Banner palette (warning / danger / success) — independent of
        // bay-state palette, used for toasts and mock-payment banner.
        warn: cssVar("warn"),
        danger: cssVar("danger"),
        success: cssVar("success"),
      },
      fontFamily: {
        sans: ["Fira Sans", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["Fira Code", "ui-monospace", "SFMono-Regular", "monospace"],
      },
      fontSize: {
        // Body 16px baseline (rubric: readable-font-size).
        base: ["1rem", { lineHeight: "1.5" }],
        // Data-dense table rows.
        compact: ["0.875rem", { lineHeight: "1.45" }],
      },
      borderRadius: {
        lg: "0.75rem",
        xl: "1rem",
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(0 0 0 / 0.04), 0 1px 4px -1px rgb(0 0 0 / 0.06)",
        "card-hover":
          "0 4px 12px -2px rgb(0 0 0 / 0.08), 0 2px 6px -2px rgb(0 0 0 / 0.10)",
        glow: "0 0 0 1px rgb(var(--accent) / 0.5), 0 0 12px rgb(var(--accent) / 0.25)",
      },
      keyframes: {
        // Status-pulse for `pending_check_in` and `conflict` tiles.
        pulse: {
          "0%, 100%": { opacity: "1" },
          "50%": { opacity: "0.55" },
        },
        "fade-in": {
          from: { opacity: "0", transform: "translateY(-4px)" },
          to: { opacity: "1", transform: "translateY(0)" },
        },
        "slide-in-right": {
          from: { opacity: "0", transform: "translateX(8px)" },
          to: { opacity: "1", transform: "translateX(0)" },
        },
      },
      animation: {
        pulse: "pulse 2s cubic-bezier(0.4, 0, 0.6, 1) infinite",
        "fade-in": "fade-in 150ms ease-out",
        "slide-in-right": "slide-in-right 180ms ease-out",
      },
    },
  },
  plugins: [],
};

export default config;
