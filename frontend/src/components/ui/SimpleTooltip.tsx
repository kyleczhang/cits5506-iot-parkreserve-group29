/**
 * Tiny wrapper around Radix Tooltip with sensible defaults
 * (delay, dark surface, light text). Re-exports the parts the chart
 * components need.
 */
import * as RadixTooltip from "@radix-ui/react-tooltip";
import { type ReactNode } from "react";
import { cn } from "@/lib/cn";

export const TooltipProvider = ({ children }: { children: ReactNode }) => (
  <RadixTooltip.Provider delayDuration={150}>{children}</RadixTooltip.Provider>
);

export const Tooltip = RadixTooltip.Root;

export const TooltipTrigger = ({ children }: { children: ReactNode }) => (
  <RadixTooltip.Trigger asChild>{children}</RadixTooltip.Trigger>
);

export const TooltipContent = ({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) => (
  <RadixTooltip.Portal>
    <RadixTooltip.Content
      sideOffset={6}
      className={cn(
        "z-50 rounded-md border border-border bg-surface-2 px-2 py-1 text-xs text-text shadow-card",
        "data-[state=delayed-open]:animate-fade-in",
        className,
      )}
    >
      {children}
      <RadixTooltip.Arrow className="fill-[rgb(var(--surface-2))]" />
    </RadixTooltip.Content>
  </RadixTooltip.Portal>
);
