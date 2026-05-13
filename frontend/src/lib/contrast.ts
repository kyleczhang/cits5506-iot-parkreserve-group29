/**
 * WCAG contrast-ratio helper.
 *
 * Pure-JS implementation of the WCAG 2.1 relative-luminance formula. We
 * carry our own to (a) test design tokens without a browser and (b)
 * keep the dependency surface tight.
 *
 * Reference: https://www.w3.org/WAI/WCAG21/Techniques/general/G18.html
 */

function srgbToLinear(channel: number): number {
  const c = channel / 255;
  return c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
}

function relativeLuminance(hex: string): number {
  const parsed = parseHex(hex);
  if (!parsed) return Number.NaN;
  const [r, g, b] = parsed;
  return (
    0.2126 * srgbToLinear(r) +
    0.7152 * srgbToLinear(g) +
    0.0722 * srgbToLinear(b)
  );
}

function parseHex(hex: string): [number, number, number] | null {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex.trim());
  if (!m || !m[1]) return null;
  const raw = m[1];
  return [
    parseInt(raw.slice(0, 2), 16),
    parseInt(raw.slice(2, 4), 16),
    parseInt(raw.slice(4, 6), 16),
  ];
}

/** Contrast ratio in the range [1, 21] (higher is more readable). */
export function contrastRatio(fg: string, bg: string): number {
  const lf = relativeLuminance(fg);
  const lb = relativeLuminance(bg);
  if (Number.isNaN(lf) || Number.isNaN(lb)) return Number.NaN;
  const [light, dark] = lf > lb ? [lf, lb] : [lb, lf];
  return (light + 0.05) / (dark + 0.05);
}
