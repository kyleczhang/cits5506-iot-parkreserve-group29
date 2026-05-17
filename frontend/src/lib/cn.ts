/**
 * Conditional className composer.
 *
 * A thin wrapper around `clsx` so every component imports from one place
 * (matters when we later add `tailwind-merge` to dedupe conflicting
 * utilities — call sites won't change).
 */
import clsx, { type ClassValue } from "clsx";

export function cn(...classes: ClassValue[]): string {
  return clsx(classes);
}
