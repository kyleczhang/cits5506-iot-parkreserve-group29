/**
 * Bay-state badge — dot + glyph + label.
 *
 * Triple-coded by design (colour-blind safe — see plan §3.4): the
 * coloured dot, the icon glyph, and the textual label all carry the
 * same information independently.
 */
import {
  Activity,
  AlertOctagon,
  AlertTriangle,
  Car,
  CircleSlash,
  Hourglass,
  ShieldCheck,
} from "lucide-react";

import { cn } from "@/lib/cn";
import type { BayState } from "@/schemas/bay";

interface Props {
  state: BayState;
  /** Compact = dot + short label only. Default = dot + glyph + label. */
  variant?: "default" | "compact";
  className?: string;
}

const META: Record<
  BayState,
  {
    label: string;
    Icon: React.ComponentType<{ className?: string }>;
    pillBg: string;
    pillText: string;
    dot: string;
    pulse: boolean;
  }
> = {
  available: {
    label: "Available",
    Icon: ShieldCheck,
    pillBg: "bg-state-available/15",
    pillText: "text-state-available",
    dot: "bg-state-available",
    pulse: false,
  },
  reserved: {
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
  reserved_checked_in: {
    label: "Checked in",
    Icon: Car,
    pillBg: "bg-state-occupied/15",
    pillText: "text-state-occupied",
    dot: "bg-state-occupied",
    pulse: false,
  },
  occupied: {
    label: "Occupied",
    Icon: Car,
    pillBg: "bg-state-occupied/15",
    pillText: "text-state-occupied",
    dot: "bg-state-occupied",
    pulse: false,
  },
  conflict: {
    label: "Conflict",
    Icon: AlertOctagon,
    pillBg: "bg-state-conflict/15",
    pillText: "text-state-conflict",
    dot: "bg-state-conflict",
    pulse: true,
  },
  offline: {
    label: "Offline",
    Icon: CircleSlash,
    pillBg: "bg-state-offline/15",
    pillText: "text-state-offline",
    dot: "bg-state-offline",
    pulse: false,
  },
};

export function BayStateBadge({ state, variant = "default", className }: Props) {
  const meta = META[state] ?? META.offline;
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
      aria-label={`Bay state: ${meta.label}`}
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
