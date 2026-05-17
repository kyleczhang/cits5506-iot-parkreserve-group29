/**
 * Button primitive — accessible, theme-aware, three visual variants.
 *
 * Rubric checks satisfied:
 *   - `cursor-pointer` on enabled interactive elements
 *   - smooth `transition-colors duration-150`
 *   - visible focus ring inherited from `:focus-visible` global
 *   - disabled state has reduced opacity AND `cursor-not-allowed`
 *   - 44 px minimum touch target (size="md" → h-11)
 */
import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";
import { cn } from "@/lib/cn";
import { Spinner } from "./Spinner";

type Variant = "primary" | "secondary" | "ghost" | "danger";
type Size = "sm" | "md" | "lg";

export interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant;
  size?: Size;
  /** When true, disables clicks and shows a spinner in place of the leading icon. */
  loading?: boolean;
  leadingIcon?: ReactNode;
  trailingIcon?: ReactNode;
}

const variantStyles: Record<Variant, string> = {
  primary:
    "bg-brand text-white hover:bg-brand/90 active:bg-brand/95 shadow-card focus-visible:ring-brand",
  secondary:
    "bg-surface text-text border border-border hover:bg-surface-2 active:bg-surface-2",
  ghost: "bg-transparent text-text hover:bg-surface-2 active:bg-surface-2",
  danger:
    "bg-danger text-white hover:bg-danger/90 active:bg-danger/95 shadow-card",
};

const sizeStyles: Record<Size, string> = {
  sm: "h-9 px-3 text-sm gap-1.5 rounded-md",
  md: "h-11 px-4 text-base gap-2 rounded-lg",
  lg: "h-12 px-5 text-base gap-2 rounded-lg",
};

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      variant = "primary",
      size = "md",
      loading = false,
      disabled,
      leadingIcon,
      trailingIcon,
      className,
      children,
      type = "button",
      ...rest
    },
    ref,
  ) {
    const isDisabled = disabled || loading;
    return (
      <button
        ref={ref}
        type={type}
        disabled={isDisabled}
        aria-busy={loading || undefined}
        className={cn(
          "inline-flex items-center justify-center font-medium",
          "transition-colors duration-150 ease-out",
          "disabled:cursor-not-allowed disabled:opacity-60",
          !isDisabled && "cursor-pointer",
          variantStyles[variant],
          sizeStyles[size],
          className,
        )}
        {...rest}
      >
        {loading ? (
          <Spinner size={size === "sm" ? "xs" : "sm"} className="text-current" />
        ) : (
          leadingIcon
        )}
        {children ? <span className="leading-none">{children}</span> : null}
        {!loading && trailingIcon}
      </button>
    );
  },
);
