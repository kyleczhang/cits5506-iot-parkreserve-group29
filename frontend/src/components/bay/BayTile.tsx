/**
 * Bay tile — the single most-rendered card in the app.
 *
 * Two variants:
 *   - "compact": used on the public landing strip + driver home.
 *   - "ops": used on the admin grid (denser, with sensor data).
 *
 * The "book this bay" CTA is rendered only when both
 *   (a) `onBook` is supplied (caller controls navigation), and
 *   (b) the bay is `available`.
 */
import { ArrowRight, Ruler, Timer } from "lucide-react";
import { cn } from "@/lib/cn";
import { formatRelative } from "@/lib/time";
import type { BayOut } from "@/schemas/bay";

import { Card } from "@/components/ui/Card";
import { BayStateBadge } from "./BayStateBadge";

interface Props {
  bay: BayOut;
  variant?: "compact" | "ops";
  /** Click handler for the "Book" CTA (compact variant only). */
  onBook?: (code: string) => void;
  /** Click handler for the whole tile (ops variant — drill-down). */
  onSelect?: (code: string) => void;
  className?: string;
}

export function BayTile({
  bay,
  variant = "compact",
  onBook,
  onSelect,
  className,
}: Props) {
  const interactive = variant === "ops" && Boolean(onSelect);
  const ringClass =
    bay.state === "conflict"
      ? "ring-1 ring-state-conflict/60"
      : bay.state === "pending_check_in"
        ? "ring-1 ring-state-pending/60"
        : "";

  return (
    <Card
      interactive={interactive}
      onClick={interactive ? () => onSelect?.(bay.code) : undefined}
      onKeyDown={
        interactive
          ? (event) => {
              if (event.key === "Enter" || event.key === " ") {
                event.preventDefault();
                onSelect?.(bay.code);
              }
            }
          : undefined
      }
      tabIndex={interactive ? 0 : undefined}
      role={interactive ? "button" : undefined}
      aria-label={interactive ? `Open bay ${bay.code}` : undefined}
      className={cn("p-4", ringClass, className)}
    >
      <header className="flex items-start justify-between gap-3">
        <div>
          <p className="font-mono text-2xl font-semibold leading-none text-text">
            {bay.code}
          </p>
          <p className="mt-1 text-sm text-text-muted">{bay.label}</p>
        </div>
        <BayStateBadge state={bay.state} variant="compact" />
      </header>

      {variant === "ops" ? (
        <dl className="mt-4 grid grid-cols-2 gap-y-2 text-xs">
          <dt className="flex items-center gap-1.5 text-text-muted">
            <Ruler aria-hidden="true" className="h-3.5 w-3.5" /> Distance
          </dt>
          <dd className="text-right font-mono text-text">
            {bay.last_distance_cm !== null && bay.last_distance_cm !== undefined
              ? `${bay.last_distance_cm.toFixed(1)} cm`
              : "—"}
          </dd>
          <dt className="flex items-center gap-1.5 text-text-muted">
            <Timer aria-hidden="true" className="h-3.5 w-3.5" /> Last seen
          </dt>
          <dd className="text-right text-text">
            {formatRelative(bay.sensor_last_seen_at)}
          </dd>
        </dl>
      ) : null}

      {variant === "compact" && bay.state === "available" && onBook ? (
        <button
          type="button"
          onClick={() => onBook(bay.code)}
          className={cn(
            "mt-4 inline-flex w-full items-center justify-center gap-1.5 rounded-lg",
            "h-10 bg-brand text-white text-sm font-medium",
            "transition-colors duration-150 hover:bg-brand/90 cursor-pointer",
            "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent",
          )}
        >
          Book this bay
          <ArrowRight aria-hidden="true" className="h-4 w-4" />
        </button>
      ) : null}

      {variant === "compact" && bay.state !== "available" ? (
        <p className="mt-4 rounded-lg bg-surface-2 px-3 py-2 text-xs text-text-muted">
          Not bookable right now — wait for it to become available, or pick
          another bay.
        </p>
      ) : null}
    </Card>
  );
}
