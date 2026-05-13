/**
 * Top-bar widget that reflects the live socket connection state.
 *
 * Green = connected, amber pulse = reconnecting, red = disconnected.
 * The dot is paired with a textual label for colour-blind safety
 * (plan §3.4 "status conveyed by colour + shape + text").
 */
import { cn } from "@/lib/cn";
import type { ConnectionState } from "@/realtime/useRealtime";

const LABEL: Record<ConnectionState, string> = {
  connected: "Live",
  connecting: "Reconnecting",
  disconnected: "Offline",
};

const DOT_COLOUR: Record<ConnectionState, string> = {
  connected: "bg-success",
  connecting: "bg-warn animate-pulse",
  disconnected: "bg-danger",
};

export function ConnectionStatusDot({ state }: { state: ConnectionState }) {
  return (
    <span
      className="inline-flex items-center gap-2 text-sm text-text-muted"
      aria-live="polite"
    >
      <span
        aria-hidden="true"
        className={cn("h-2.5 w-2.5 rounded-full", DOT_COLOUR[state])}
      />
      <span>{LABEL[state]}</span>
    </span>
  );
}
