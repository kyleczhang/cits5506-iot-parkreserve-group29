/**
 * Card primitive — surface + border + shadow with consistent radii.
 *
 * `interactive` adds hover/focus affordances and a `cursor-pointer`
 * for clickable variants (e.g. reservation card, conflict row).
 */
import { forwardRef, type HTMLAttributes } from "react";
import { cn } from "@/lib/cn";

interface Props extends HTMLAttributes<HTMLDivElement> {
  interactive?: boolean;
}

export const Card = forwardRef<HTMLDivElement, Props>(function Card(
  { className, interactive = false, ...rest },
  ref,
) {
  return (
    <div
      ref={ref}
      className={cn(
        "rounded-xl border border-border bg-surface text-text shadow-card",
        "transition-shadow duration-150 ease-out",
        interactive &&
          "cursor-pointer hover:shadow-card-hover focus-visible:shadow-card-hover",
        className,
      )}
      {...rest}
    />
  );
});
