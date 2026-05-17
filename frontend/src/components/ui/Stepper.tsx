/**
 * Stepper progress indicator.
 *
 * Visual + accessible breadcrumb for the booking wizard. Steps render
 * as a horizontal list with a numbered dot and a connector. The
 * current step is highlighted; completed steps render a check icon.
 */
import { Check } from "lucide-react";
import { cn } from "@/lib/cn";

export interface Step {
  id: string;
  label: string;
}

interface Props {
  steps: ReadonlyArray<Step>;
  /** Index of the current step (0-based). */
  current: number;
  className?: string;
}

export function Stepper({ steps, current, className }: Props) {
  return (
    <ol
      className={cn("flex w-full items-center", className)}
      aria-label="Booking progress"
    >
      {steps.map((step, idx) => {
        const completed = idx < current;
        const active = idx === current;
        return (
          <li
            key={step.id}
            className="flex flex-1 items-center last:flex-initial"
          >
            <div className="flex items-center gap-2">
              <span
                aria-current={active ? "step" : undefined}
                className={cn(
                  "grid h-7 w-7 place-items-center rounded-full text-xs font-semibold",
                  active &&
                    "bg-brand text-white ring-4 ring-brand/20",
                  completed && "bg-brand text-white",
                  !active && !completed &&
                    "bg-surface-2 text-text-muted border border-border",
                )}
              >
                {completed ? (
                  <Check className="h-4 w-4" aria-hidden="true" />
                ) : (
                  idx + 1
                )}
              </span>
              <span
                className={cn(
                  "text-sm",
                  active ? "font-semibold text-text" : "text-text-muted",
                )}
              >
                {step.label}
              </span>
            </div>
            {idx < steps.length - 1 ? (
              <span
                aria-hidden="true"
                className={cn(
                  "mx-3 h-px flex-1",
                  completed ? "bg-brand" : "bg-border",
                )}
              />
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}
