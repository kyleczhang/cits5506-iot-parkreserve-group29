/**
 * Spinner primitive — pure SVG, respects `prefers-reduced-motion`.
 *
 * Always pair with a textual label (`label` prop renders a visually
 * hidden span) so screen readers announce loading state.
 */
import { cn } from "@/lib/cn";

interface Props {
  size?: "xs" | "sm" | "md" | "lg";
  className?: string;
  label?: string;
}

const sizes: Record<NonNullable<Props["size"]>, string> = {
  xs: "h-3 w-3",
  sm: "h-4 w-4",
  md: "h-6 w-6",
  lg: "h-8 w-8",
};

export function Spinner({ size = "md", className, label = "Loading" }: Props) {
  return (
    <span role="status" className={cn("inline-flex items-center", className)}>
      <svg
        className={cn("animate-spin", sizes[size])}
        viewBox="0 0 24 24"
        fill="none"
        aria-hidden="true"
      >
        <circle
          cx="12"
          cy="12"
          r="10"
          stroke="currentColor"
          strokeWidth="3"
          className="opacity-25"
        />
        <path
          d="M22 12a10 10 0 0 1-10 10"
          stroke="currentColor"
          strokeWidth="3"
          strokeLinecap="round"
        />
      </svg>
      <span className="sr-only">{label}</span>
    </span>
  );
}
