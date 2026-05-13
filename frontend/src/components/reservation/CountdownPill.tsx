/**
 * Countdown pill — renders `mm:ss` (or `-mm:ss`) against a target ISO
 * timestamp, rebasing on a 1 s interval.
 *
 * When the countdown crosses zero (any time `seconds` flips from
 * positive to negative), `onExpire` fires exactly once per mount.
 * The cockpit uses this to trigger a refetch and confirm the
 * server-side transition (no-show, grace expiry, etc.).
 */
import { useEffect, useRef, useState } from "react";
import { cn } from "@/lib/cn";
import { formatMmSs, secondsUntil } from "@/lib/time";

interface Props {
  /** ISO-8601 target timestamp. */
  target: string | null | undefined;
  /** Label suffix shown next to the timer ("until arrival", "grace left"). */
  label?: string;
  /**
   * Called once when the countdown crosses from positive to negative.
   * Useful for triggering a refetch when the grace expires.
   */
  onExpire?: () => void;
  className?: string;
}

export function CountdownPill({ target, label, onExpire, className }: Props) {
  const [seconds, setSeconds] = useState<number>(() => secondsUntil(target));
  const expiredRef = useRef(false);

  useEffect(() => {
    setSeconds(secondsUntil(target));
    expiredRef.current = false;
  }, [target]);

  useEffect(() => {
    if (!target) return;
    const tick = () => {
      const next = secondsUntil(target);
      setSeconds(next);
      if (!expiredRef.current && next <= 0 && Number.isFinite(next)) {
        expiredRef.current = true;
        onExpire?.();
      }
    };
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, [target, onExpire]);

  if (!Number.isFinite(seconds)) {
    return null;
  }

  const expired = seconds <= 0;
  return (
    <span
      className={cn(
        "inline-flex items-baseline gap-2 rounded-full border px-3 py-1 font-mono text-sm",
        expired
          ? "border-danger/40 bg-danger/10 text-danger"
          : "border-border bg-surface-2 text-text",
        className,
      )}
      aria-live="polite"
    >
      <span className="tabular-nums">{formatMmSs(seconds)}</span>
      {label ? (
        <span className="font-sans text-xs text-text-muted">{label}</span>
      ) : null}
    </span>
  );
}
