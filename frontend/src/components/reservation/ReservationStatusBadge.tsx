/**
 * Reservation-status badge — dot + glyph + label.
 *
 * Keyed on `ReservationStatus` (the driver-visible lifecycle), NOT on
 * `BayState`. The two enums share some visual cues (e.g. yellow for
 * "reserved", red-pulse for "conflict") but the reservation lifecycle
 * has terminal states (`completed`, `cancelled`, `cancelled_late`,
 * `expired_no_show`) that have no bay-state cognate — reusing
 * `BayStateBadge` for those caused them all to fall through to
 * `"offline"`, which is wrong semantically (a no-show reservation is
 * not an offline bay).
 *
 * Triple-coded per plan §3.4: colour, glyph, and textual label each
 * carry the state independently.
 */
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Ban,
  Car,
  Hourglass,
  ShieldCheck,
} from "lucide-react";

import { cn } from "@/lib/cn";
import type { ReservationStatus } from "@/schemas/reservation";

interface Props {
  status: ReservationStatus;
  /** Compact = dot + short label only. Default = dot + glyph + label. */
  variant?: "default" | "compact";
  className?: string;
}

const META: Record<
  ReservationStatus,
  {
    label: string;
    Icon: React.ComponentType<{ className?: string }>;
    pillBg: string;
    pillText: string;
    dot: string;
    pulse: boolean;
  }
> = {
  active: {
    label: "Reserved",
    Icon: Hourglass,
    pillBg: "bg-state-reserved/15",
    pillText: "text-state-reserved",
    dot: "bg-state-reserved",
    pulse: false,
  },
  pending_check_in: {
    label: "Pending check-in",
    Icon: Activity,
    pillBg: "bg-state-pending/15",
    pillText: "text-state-pending",
    dot: "bg-state-pending",
    pulse: true,
  },
  checked_in: {
    label: "Checked in",
    Icon: Car,
    // Brand-teal on the driver surface: this is the driver's own
    // positive confirmation. (The ops console still sees the bay as
    // red `occupied` via `BayStateBadge` — that's a different lens.)
    pillBg: "bg-brand/15",
    pillText: "text-brand",
    dot: "bg-brand",
    pulse: false,
  },
  in_conflict: {
    label: "Conflict",
    Icon: AlertOctagon,
    pillBg: "bg-state-conflict/15",
    pillText: "text-state-conflict",
    dot: "bg-state-conflict",
    pulse: true,
  },
  completed: {
    label: "Completed",
    Icon: ShieldCheck,
    pillBg: "bg-success/15",
    pillText: "text-success",
    dot: "bg-success",
    pulse: false,
  },
  cancelled: {
    label: "Cancelled",
    Icon: Ban,
    pillBg: "bg-text-muted/15",
    pillText: "text-text-muted",
    dot: "bg-text-muted",
    pulse: false,
  },
  cancelled_late: {
    label: "Cancelled (late)",
    Icon: Ban,
    // Amber `warn` signals "terminal but a penalty was captured" —
    // distinct from the neutral grey of an on-time cancel.
    pillBg: "bg-warn/15",
    pillText: "text-warn",
    dot: "bg-warn",
    pulse: false,
  },
  expired_no_show: {
    label: "No-show",
    Icon: AlertTriangle,
    pillBg: "bg-danger/15",
    pillText: "text-danger",
    dot: "bg-danger",
    pulse: false,
  },
};

export function ReservationStatusBadge({
  status,
  variant = "default",
  className,
}: Props) {
  const meta = META[status] ?? META.cancelled;
  const FallbackIcon = AlertTriangle;
  const Icon = meta.Icon ?? FallbackIcon;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-2.5 py-1 text-xs font-medium",
        meta.pillBg,
        meta.pillText,
        className,
      )}
      role="status"
      aria-label={`Reservation status: ${meta.label}`}
    >
      <span
        aria-hidden="true"
        className={cn(
          "h-2 w-2 rounded-full",
          meta.dot,
          meta.pulse && "animate-pulse",
        )}
      />
      {variant === "default" ? (
        <Icon aria-hidden="true" className="h-3.5 w-3.5" />
      ) : null}
      <span>{meta.label}</span>
    </span>
  );
}
