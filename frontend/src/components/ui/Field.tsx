/**
 * Form field primitive — label + input + helper + error, wired for a11y.
 *
 * Every input has an explicit `<label for>` (rubric: form-labels).
 * Errors render in a `role="alert"` region adjacent to the input
 * (rubric: error-feedback "near problem").
 */
import {
  forwardRef,
  useId,
  type InputHTMLAttributes,
  type ReactNode,
} from "react";
import { cn } from "@/lib/cn";

export interface FieldProps extends InputHTMLAttributes<HTMLInputElement> {
  label: string;
  /** Inline error message — when set, the input gets `aria-invalid`. */
  error?: string | null | undefined;
  /** Optional helper text shown when no error is set. */
  helper?: string;
  /** Icon rendered inside the input on the leading edge. */
  leadingIcon?: ReactNode;
  /** Icon rendered inside the input on the trailing edge. */
  trailingIcon?: ReactNode;
}

export const Field = forwardRef<HTMLInputElement, FieldProps>(function Field(
  {
    id,
    label,
    error,
    helper,
    className,
    leadingIcon,
    trailingIcon,
    required,
    ...rest
  },
  ref,
) {
  const autoId = useId();
  const inputId = id ?? `f-${autoId}`;
  const helperId = helper ? `${inputId}-helper` : undefined;
  const errorId = error ? `${inputId}-error` : undefined;
  const describedBy = [helperId, errorId].filter(Boolean).join(" ") || undefined;

  return (
    <div className="flex flex-col gap-1.5">
      <label
        htmlFor={inputId}
        className="text-sm font-medium text-text leading-none"
      >
        {label}
        {required ? <span className="text-danger"> *</span> : null}
      </label>
      <div className="relative flex items-center">
        {leadingIcon ? (
          <span
            className="pointer-events-none absolute left-3 text-text-muted"
            aria-hidden="true"
          >
            {leadingIcon}
          </span>
        ) : null}
        <input
          ref={ref}
          id={inputId}
          required={required}
          aria-invalid={error ? "true" : undefined}
          aria-describedby={describedBy}
          className={cn(
            "h-11 w-full rounded-lg border border-border bg-surface px-3",
            "text-base text-text placeholder:text-text-muted",
            "transition-shadow duration-150 ease-out",
            "focus:outline-none focus:ring-2 focus:ring-accent",
            leadingIcon && "pl-9",
            trailingIcon && "pr-9",
            error && "border-danger focus:ring-danger",
            className,
          )}
          {...rest}
        />
        {trailingIcon ? (
          <span className="absolute right-3 text-text-muted">{trailingIcon}</span>
        ) : null}
      </div>
      {error ? (
        <p
          id={errorId}
          role="alert"
          className="text-sm text-danger leading-tight"
        >
          {error}
        </p>
      ) : helper ? (
        <p id={helperId} className="text-sm text-text-muted leading-tight">
          {helper}
        </p>
      ) : null}
    </div>
  );
});
