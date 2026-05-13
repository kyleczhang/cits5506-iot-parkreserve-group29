/**
 * Global toast viewport.
 *
 * Wraps Radix `<Toast>` so we get ARIA live regions, focus management,
 * and swipe-to-dismiss for free. Tone styling is theme-aware.
 */
import { useEffect, useState } from "react";
import * as Toast from "@radix-ui/react-toast";
import { CheckCircle2, AlertCircle, AlertTriangle, Info, X } from "lucide-react";

import { cn } from "@/lib/cn";
import {
  dismissToast,
  subscribeToasts,
  type ToastItem,
  type ToastTone,
} from "./toastStore";

const TONE_ICON: Record<ToastTone, React.ComponentType<{ className?: string }>> = {
  info: Info,
  success: CheckCircle2,
  warn: AlertTriangle,
  danger: AlertCircle,
};

const TONE_CLASSES: Record<ToastTone, string> = {
  info: "border-accent/30 bg-surface",
  success: "border-success/40 bg-surface",
  warn: "border-warn/50 bg-surface",
  danger: "border-danger/60 bg-surface shadow-[0_0_0_1px_rgb(var(--danger)/0.4)]",
};

const TONE_ICON_CLASSES: Record<ToastTone, string> = {
  info: "text-accent",
  success: "text-success",
  warn: "text-warn",
  danger: "text-danger",
};

export function Toaster() {
  const [items, setItems] = useState<ToastItem[]>([]);

  useEffect(() => subscribeToasts(setItems), []);

  return (
    <Toast.Provider swipeDirection="right">
      {items.map((t) => {
        const Icon = TONE_ICON[t.tone];
        return (
          <Toast.Root
            key={t.id}
            duration={t.durationMs}
            onOpenChange={(open) => {
              if (!open) dismissToast(t.id);
            }}
            type={t.ariaLive === "assertive" ? "foreground" : "background"}
            className={cn(
              "pointer-events-auto grid grid-cols-[auto_1fr_auto] items-start gap-3",
              "rounded-lg border p-4 shadow-card-hover",
              "data-[state=open]:animate-slide-in-right",
              "data-[state=closed]:opacity-0",
              TONE_CLASSES[t.tone],
            )}
          >
            <Icon className={cn("mt-0.5 h-5 w-5", TONE_ICON_CLASSES[t.tone])} />
            <div className="min-w-0">
              <Toast.Title className="text-sm font-semibold text-text">
                {t.title}
              </Toast.Title>
              {t.description ? (
                <Toast.Description className="mt-0.5 text-sm text-text-muted">
                  {t.description}
                </Toast.Description>
              ) : null}
            </div>
            <Toast.Close
              aria-label="Dismiss notification"
              className="rounded p-1 text-text-muted hover:bg-surface-2 hover:text-text focus-visible:bg-surface-2"
            >
              <X className="h-4 w-4" />
            </Toast.Close>
          </Toast.Root>
        );
      })}
      <Toast.Viewport
        className={cn(
          "pointer-events-none fixed right-4 top-4 z-[60]",
          "flex max-h-screen w-[min(420px,calc(100vw-2rem))] flex-col gap-2",
          "outline-none",
        )}
      />
    </Toast.Provider>
  );
}
